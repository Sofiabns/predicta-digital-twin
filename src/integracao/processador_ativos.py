"""Etapa central da automação: avalia cada ativo e mantém tudo sincronizado.

Para cada ativo com leitura nova:
    leitura -> classificação -> evento -> status -> recomendação -> OS -> notificação
As escritas de um ativo acontecem em uma única transação: ou o status, o
evento, o histórico e a auditoria são gravados juntos, ou nada é gravado.
"""

from __future__ import annotations

import logging
from typing import Any

from src.automacao.notificacao_service import enviar_alerta_html
from src.integracao import ciclo_vida_eventos as cv
from src.integracao.avaliacao import ORDEM, avaliar_leitura
from src.integracao.config import Config
from src.integracao.limites import resolver_limites_todos
from src.integracao.log_estruturado import LogEstruturado
from src.integracao.suporte_operacional import SuporteOperacional
from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)

SQL_ATIVOS = """
SELECT a.motor_id, a.tag, a.status_operacional, a.ultima_leitura_avaliada_id,
       m.codigo AS codigo_motor, m.modelo AS modelo_motor,
       ul.leitura_id, ul.timestamp, ul.temperatura, ul.vibracao, ul.corrente, ul.tensao, ul.rpm,
       dp.corrente_nominal, dp.tensao_nominal
FROM associacoes_ativos a
JOIN motores m ON m.id = a.motor_id
LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id = a.motor_id
LEFT JOIN dados_placa_motor dp ON dp.motor_id = a.motor_id
ORDER BY a.tag
"""


def avaliar_ativos(cfg: Config, log: LogEstruturado, run_id: str, suporte: SuporteOperacional) -> dict[str, Any]:
    with get_connection() as conn:
        ativos = [dict(r) for r in conn.execute(SQL_ATIVOS).fetchall()]
        limites = resolver_limites_todos(conn)

    resumo: dict[str, Any] = {"avaliados": 0, "sem_leitura_nova": 0, "eventos_abertos": 0, "escalonados": 0,
                              "resolvidos": 0, "status_alterados": 0, "falhas": 0, "notificacoes": 0,
                              "acoes": [], "degradado": False}
    for ativo in ativos:
        tag = ativo["tag"]
        if ativo["leitura_id"] is None or ativo["leitura_id"] == ativo["ultima_leitura_avaliada_id"]:
            resumo["sem_leitura_nova"] += 1
            log.aviso("avaliacao", "sem_leitura_nova", "Nenhuma leitura nova; ativo mantido como está", ativo=tag)
            continue
        try:
            acao = _processar_ativo(ativo, limites[ativo["motor_id"]], cfg, log, run_id, suporte, resumo)
            resumo["avaliados"] += 1
            resumo["acoes"].append({"tag": tag, "acao": acao})
        except Exception as exc:  # noqa: BLE001 - falha em um ativo não pode parar os demais
            resumo["falhas"] += 1
            resumo["degradado"] = True
            log.erro("avaliacao", "falha_ativo", f"Falha ao processar {tag}: {exc}", ativo=tag)
    return resumo


def _processar_ativo(ativo, lim, cfg, log, run_id, suporte, resumo) -> str:
    tag, motor_id = ativo["tag"], ativo["motor_id"]
    leitura = {k: ativo[k] for k in ("temperatura", "vibracao", "corrente", "tensao")}
    av = avaliar_leitura(leitura, temp_max=lim.temp_max, vib_max=lim.vib_max,
                         corrente_nominal=ativo["corrente_nominal"],
                         tensao_nominal=ativo["tensao_nominal"] or cfg.tensao_nominal_padrao, cfg=cfg)
    log.info("avaliacao", "leitura_classificada",
             f"{av.severidade}: {av.descricao}", ativo=tag, leitura_id=ativo["leitura_id"],
             temperatura=ativo["temperatura"], vibracao=ativo["vibracao"], corrente=ativo["corrente"],
             tensao=ativo["tensao"], limites_fonte=lim.fonte, temp_max=lim.temp_max, vib_max=lim.vib_max)

    with get_connection() as conn:
        evento = cv.buscar_evento_aberto(conn, tag)
        status_atual = conn.execute("SELECT status_operacional FROM associacoes_ativos WHERE motor_id = ?",
                                    (motor_id,)).fetchone()[0]

    alvo = cv.MAPA_STATUS[av.severidade]
    preservado = status_atual in cv.STATUS_PRESERVADOS
    rec = None
    if av.severidade != "NORMAL" and (evento is None or ORDEM[av.severidade] > ORDEM[evento["severidade"]]):
        rec = suporte.recomendar(av, tag=tag, modelo=ativo["modelo_motor"], limites_fonte=lim.fonte,
                                 guia_catalogo=lim.guia_troubleshooting)
        log.info("suporte", "recomendacao_gerada", f"Recomendação gerada ({rec.origem})", ativo=tag,
                 origem=rec.origem, prioridade=rec.prioridade, passos=len(rec.procedimentos),
                 referencias=len(rec.referencias))

    notificar: tuple | None = None
    with get_connection() as conn:                       # transação única do ativo
        def mudar_status(novo: str, motivo: str, origem: str = cv.ATOR_RPA):
            if preservado or novo == status_atual:
                return (None, None)
            ant = cv.atualizar_status_ativo(conn, motor_id, tag, novo, origem, motivo, run_id)
            if ant:
                resumo["status_alterados"] += 1
                log.info("status", "status_atualizado", f"{ant} -> {novo}", ativo=tag, de=ant, para=novo, motivo=motivo)
            return (ant, novo) if ant else (None, None)

        if av.severidade == "NORMAL" and evento is None:
            mudanca = mudar_status("operacional", "Sincronização: leitura dentro dos limites", "RPA_SINCRONIZACAO")
            acao = "status_sincronizado" if mudanca[0] else ("preservado" if preservado else "sem_alteracao")

        elif av.severidade == "NORMAL":
            n = cv.contar_normalidade(conn, evento["id"])
            if n >= cfg.ciclos_para_resolver and evento["status_resolucao"] != "em_atendimento":
                mudanca = mudar_status("operacional", "Normalização confirmada")
                cv.resolver_evento(conn, evento,
                                   f"Normalizado automaticamente após {n} leituras consecutivas dentro dos limites",
                                   cv.ATOR_RPA, mudanca, run_id)
                resumo["resolvidos"] += 1
                log.info("evento", "evento_resolvido", f"Evento #{evento['id']} encerrado automaticamente",
                         ativo=tag, evento_id=evento["id"], leituras_normais=n)
                acao = "evento_resolvido"
            else:
                acao = f"normal_{n}_de_{cfg.ciclos_para_resolver}"

        elif evento is None:
            mudanca = mudar_status(alvo, f"Anomalia {av.severidade}")
            evento_id = cv.abrir_evento(conn, tag=tag, codigo_motor=ativo["codigo_motor"], severidade=av.severidade,
                                        descricao=av.descricao, rec=rec, leitura_id=ativo["leitura_id"], run_id=run_id,
                                        status_ativo=mudanca)
            os_id = cv.abrir_ordem_manutencao(conn, motor_id, evento_id, av.severidade, rec)
            cv.encaminhar_evento(conn, evento_id, os_id, "Equipe de Manutenção", run_id)
            resumo["eventos_abertos"] += 1
            log.info("evento", "evento_aberto", f"Evento #{evento_id} aberto e encaminhado (OS #{os_id})", ativo=tag,
                     evento_id=evento_id, manutencao_id=os_id, severidade=av.severidade)
            acao = "evento_aberto"
            if av.severidade == "CRITICO":
                notificar = (av.severidade, rec)

        elif ORDEM[av.severidade] > ORDEM[evento["severidade"]]:
            mudanca = mudar_status(alvo, "Escalonamento de severidade")
            cv.escalar_evento(conn, evento, av.severidade, av.descricao, rec, ativo["leitura_id"], run_id, mudanca)
            if evento["manutencao_id"]:
                conn.execute("UPDATE manutencoes SET tipo = 'corretiva', prioridade = ?, descricao = ?, "
                             "atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
                             (rec.prioridade, f"{rec.acao_recomendada} (origem: {rec.origem}; evento #{evento['id']})",
                              evento["manutencao_id"]))
            resumo["escalonados"] += 1
            log.aviso("evento", "evento_escalonado", f"Evento #{evento['id']}: {evento['severidade']} -> {av.severidade}",
                      ativo=tag, evento_id=evento["id"])
            acao = "evento_escalonado"
            notificar = (av.severidade, rec)

        elif av.severidade != evento["severidade"]:
            mudanca = mudar_status(alvo, "Reclassificação de severidade")
            cv.reclassificar_evento(conn, evento, av.severidade, av.descricao, ativo["leitura_id"], run_id, mudanca)
            acao = "evento_reclassificado"

        else:
            mudar_status(alvo, "Anomalia persistente")
            cv.registrar_recorrencia(conn, evento["id"])
            acao = "ocorrencia_repetida"

        conn.execute("UPDATE associacoes_ativos SET ultima_leitura_avaliada_id = ?, "
                     "ultima_avaliacao_em = CURRENT_TIMESTAMP WHERE motor_id = ?", (ativo["leitura_id"], motor_id))

    if notificar:                                          # fora da transação: falha de e-mail não desfaz o registro
        try:
            arq = enviar_alerta_html(tag, notificar[0], notificar[1].diagnostico, notificar[1].acao_recomendada,
                                     notificar[1].procedimentos, cfg.notificacoes_dir)
            resumo["notificacoes"] += 1
            log.info("notificacao", "alerta_enviado", "Alerta enviado à equipe", ativo=tag,
                     arquivo=str(arq.name) if arq else None)
        except Exception as exc:  # noqa: BLE001
            resumo["degradado"] = True
            log.erro("notificacao", "falha_envio", f"Falha ao notificar: {exc}", ativo=tag)
    return acao

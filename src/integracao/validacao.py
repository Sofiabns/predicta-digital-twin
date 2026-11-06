"""Verificações de integridade da execução integrada (usadas em script e testes)."""

from __future__ import annotations

import json
from pathlib import Path

from src.integracao.ciclo_vida_eventos import ABERTOS, verificar_cadeia_auditoria
from src.integracao.log_estruturado import ler_log
from src.persistencia.database import get_connection


def validar_integridade(arquivo_log: Path | None = None) -> list[tuple[str, bool, str]]:
    """Devolve uma lista de (verificação, passou?, detalhe)."""
    r: list[tuple[str, bool, str]] = []
    with get_connection() as c:
        n_ev = c.execute("SELECT COUNT(*) FROM eventos_operacionais").fetchone()[0]
        r.append(("Existe ao menos um evento registrado", n_ev > 0, f"{n_ev} evento(s)"))

        sem_rec = c.execute("SELECT COUNT(*) FROM eventos_operacionais WHERE COALESCE(diagnostico_ia,'')='' "
                            "OR COALESCE(acao_recomendada,'')='' OR procedimentos_json IS NULL").fetchone()[0]
        r.append(("Todo evento tem diagnóstico, ação e procedimentos", sem_rec == 0, f"{sem_rec} sem recomendação"))

        sem_hist = c.execute("SELECT COUNT(*) FROM eventos_operacionais e WHERE NOT EXISTS "
                             "(SELECT 1 FROM historico_eventos h WHERE h.evento_id = e.id)").fetchone()[0]
        r.append(("Todo evento tem histórico de transições", sem_hist == 0, f"{sem_hist} sem histórico"))

        marcas = ",".join("?" * len(ABERTOS))
        dup = c.execute(f"SELECT COUNT(*) FROM (SELECT tag_ativo FROM eventos_operacionais "
                        f"WHERE status_resolucao IN ({marcas}) GROUP BY tag_ativo HAVING COUNT(*) > 1)", ABERTOS).fetchone()[0]
        r.append(("No máximo um evento aberto por ativo", dup == 0, f"{dup} ativo(s) com duplicidade"))

        fechados_sem_dados = c.execute("SELECT COUNT(*) FROM eventos_operacionais WHERE status_resolucao='resolvido' "
                                       "AND (encerrado_em IS NULL OR COALESCE(resolucao,'')='')").fetchone()[0]
        r.append(("Todo evento resolvido tem data e descrição de encerramento", fechados_sem_dados == 0,
                  f"{fechados_sem_dados} inconsistente(s)"))

        crit_sem_evento = c.execute(
            "SELECT COUNT(*) FROM associacoes_ativos a WHERE a.status_operacional IN ('critico','atencao') "
            "AND NOT EXISTS (SELECT 1 FROM eventos_operacionais e WHERE e.tag_ativo = a.tag "
            f"AND e.status_resolucao IN ({marcas}))", ABERTOS).fetchone()[0]
        r.append(("Nenhum ativo em 'atenção/crítico' sem evento aberto", crit_sem_evento == 0,
                  f"{crit_sem_evento} divergência(s) entre status e eventos"))

        os_dup = c.execute("SELECT COUNT(*) FROM (SELECT evento_id FROM manutencoes WHERE evento_id IS NOT NULL "
                           "GROUP BY evento_id HAVING COUNT(*) > 1)").fetchone()[0]
        r.append(("Uma ordem de manutenção por evento (sem duplicidade)", os_dup == 0, f"{os_dup} evento(s) com OS repetida"))

        ok, total, msg = verificar_cadeia_auditoria(c)
        r.append(("Cadeia de hashes da auditoria íntegra", ok, f"{total} registro(s) verificados: {msg}"))

        ciclos = c.execute("SELECT COUNT(*) FROM execucoes_pipeline").fetchone()[0]
        r.append(("Execuções de ciclo registradas no banco", ciclos > 0, f"{ciclos} ciclo(s)"))

    if arquivo_log is not None:
        regs = ler_log(arquivo_log)
        tem = {x["evento"] for x in regs}
        r.append(("Log estruturado contém o fluxo alerta → status → recomendação",
                  {"leitura_classificada", "status_atualizado", "recomendacao_gerada"} <= tem,
                  f"{len(regs)} linhas JSON"))
    return r

"""Gera as evidências de execução ponta a ponta a partir do banco e dos logs."""

from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.integracao.config import Config
from src.integracao.log_estruturado import ler_log
from src.integracao.validacao import validar_integridade
from src.persistencia.database import get_connection, get_db_path

def _local(ts):
    """O SQLite grava em UTC; nos relatórios mostramos o horário local da máquina."""
    if not ts:
        return ts
    try:
        return (datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                .astimezone().strftime("%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return ts

def _csv(caminho: Path, linhas: list[dict[str, Any]]) -> None:
    if not linhas:
        caminho.write_text("", encoding="utf-8")
        return
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


def _consultar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def montar_trilha(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Uma linha por evento: alerta -> status -> recomendação -> encaminhamento -> encerramento."""
    linhas = []
    eventos = _consultar(conn, """
        SELECT e.*, l.timestamp AS leitura_ts, l.temperatura, l.vibracao, l.corrente, l.tensao,
               m.tipo AS os_tipo, m.prioridade AS os_prioridade, m.status AS os_status
        FROM eventos_operacionais e
        LEFT JOIN leituras l ON l.id = e.leitura_id
        LEFT JOIN manutencoes m ON m.id = e.manutencao_id ORDER BY e.id""")
    for e in eventos:
        hist = _consultar(conn, "SELECT status_novo, acao, ator, criado_em FROM historico_eventos "
                                "WHERE evento_id=? ORDER BY id", (e["id"],))
        mudancas = [f"{h['status_ativo_anterior']}→{h['status_ativo_novo']}" for h in _consultar(
            conn, "SELECT status_ativo_anterior, status_ativo_novo FROM historico_eventos WHERE evento_id=? "
                  "AND status_ativo_novo IS NOT NULL AND status_ativo_anterior IS NOT NULL ORDER BY id", (e["id"],))]
        procs = json.loads(e["procedimentos_json"] or "[]")
        refs = json.loads(e["referencias_json"] or "[]")
        linhas.append({
            "evento_id": e["id"], "tag": e["tag_ativo"], "motor": e["codigo_motor"],
            "1_alerta_detectado_em": _local(e["created_at"]),
            "1_leitura_que_motivou_classificacao": f"{e['leitura_ts']} | {e['temperatura']} °C | {e['vibracao']} mm/s | "
                                 f"{e['corrente']} A | {e['tensao']} V",
            "1_descricao_alerta": e["descricao_anomalia"],
            "2_mudancas_status_ativo": "; ".join(mudancas),
            "3_recomendacao_diagnostico": e["diagnostico_ia"], "3_recomendacao_acao": e["acao_recomendada"],
            "3_origem_recomendacao": e["origem_recomendacao"], "3_qtd_procedimentos": len(procs),
            "3_qtd_referencias_manual": len(refs),
            "4_ordem_manutencao": f"#{e['manutencao_id']} ({e['os_tipo']}, {e['os_prioridade']})" if e["manutencao_id"] else "",
            "4_encaminhado_para": e["encaminhado_para"],
            "5_situacao_final": e["status_resolucao"], "5_severidade_final": e["severidade"],
            "5_ocorrencias": e["ocorrencias"], "5_encerrado_em": _local(e["encerrado_em"]),
            "5_encerrado_por": e["encerrado_por"], "5_resolucao": e["resolucao"],
            "transicoes": " > ".join(f"{h['acao']}({h['status_novo']})" for h in hist),
        })
    return linhas


def gerar_evidencias(cfg: Config | None = None, arquivo_log: Path | None = None, run_id: str | None = None) -> Path:
    cfg = cfg or Config.carregar()
    destino = cfg.evidencias_dir
    destino.mkdir(parents=True, exist_ok=True)

    with get_connection() as c:
        trilha = montar_trilha(c)
        _csv(destino / "trilha_ponta_a_ponta.csv", trilha)
        _csv(destino / "eventos_operacionais.csv", _consultar(c, "SELECT * FROM eventos_operacionais ORDER BY id"))
        _csv(destino / "historico_eventos.csv", _consultar(c, "SELECT * FROM historico_eventos ORDER BY id"))
        _csv(destino / "manutencoes.csv", _consultar(c, "SELECT * FROM manutencoes ORDER BY id"))
        _csv(destino / "auditoria_operacional.csv", _consultar(c, "SELECT * FROM auditoria_operacional ORDER BY id"))
        _csv(destino / "execucoes_etapas.csv", _consultar(c, "SELECT * FROM execucoes_etapas ORDER BY id"))
        status = _consultar(c, """SELECT a.tag, m.codigo AS motor, a.status_operacional, a.origem_atualizacao,
                                  a.data_atualizacao, ul.temperatura, ul.vibracao, ul.timestamp AS ultima_leitura
                                  FROM associacoes_ativos a JOIN motores m ON m.id=a.motor_id
                                  LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id=a.motor_id ORDER BY a.tag""")
        _csv(destino / "status_final_ativos.csv", status)
        ciclos = _consultar(c, "SELECT ciclo, status, inicio, fim, resumo_json FROM execucoes_pipeline ORDER BY id")
        etapas = _consultar(c, "SELECT ciclo, etapa, status, duracao_ms, detalhes_json, erro FROM execucoes_etapas ORDER BY id")

    # cópia consistente do banco
    snap = destino / "predicta_evidencia.db"
    if snap.exists():
        snap.unlink()
    with sqlite3.connect(str(get_db_path())) as origem, sqlite3.connect(str(snap)) as alvo:
        origem.backup(alvo)

    # logs estruturados, e-mails simulados e contexto do assistente
    if arquivo_log and Path(arquivo_log).exists() and Path(arquivo_log).resolve().parent != (destino / "logs").resolve():
        (destino / "logs").mkdir(exist_ok=True)
        shutil.copy2(arquivo_log, destino / "logs" / "execucao.jsonl")
    for nome, origem_dir, padrao in (("notificacoes", cfg.notificacoes_dir, "*.html"), ("contexto_rag", cfg.rag_dir, "*")):
        alvo_dir = destino / nome
        if alvo_dir.exists():
            shutil.rmtree(alvo_dir)
        if origem_dir.exists():
            alvo_dir.mkdir()
            for f in origem_dir.glob(padrao):
                if f.is_file():
                    shutil.copy2(f, alvo_dir / f.name)

    log_regs = ler_log(arquivo_log or (destino / "logs" / "execucao.jsonl"), run_id)
    checks = validar_integridade(arquivo_log or (destino / "logs" / "execucao.jsonl"))
    _relatorio(destino / "RELATORIO_EVIDENCIAS.md", trilha, status, ciclos, etapas, log_regs, checks)
    return destino


def _relatorio(caminho: Path, trilha, status, ciclos, etapas, log_regs, checks) -> None:
    def modo() -> list[str]:
        origens = [(x.get("dados") or {}).get("origem") for x in log_regs if x.get("evento") == "recomendacao_gerada"]
        clima = [json.loads(e["detalhes_json"] or "{}").get("clima") for e in etapas if e["etapa"] == "catalogo"]
        from src.analise.base_conhecimento import BaseConhecimento
        try:
            rag = BaseConhecimento().backend
        except Exception:  # noqa: BLE001
            rag = "indisponível"
        return [f"- Recomendações geradas: {len(origens)} ({', '.join(sorted({o for o in origens if o})) or 'nenhuma'})",
                f"- Busca na base de conhecimento: {rag}",
                f"- Contexto climático: {'indisponível, valor padrão usado' if any(clima) else 'obtido'}"]

    L = ["# Evidências de execução ponta a ponta - Sprint 4", "",
         f"Gerado em {datetime.now():%d/%m/%Y %H:%M:%S} a partir do banco `predicta_evidencia.db` e do log "
         "`logs/execucao.jsonl`.", "",
         "## 1. Resultado das verificações de integridade", "",
         "| Verificação | Resultado | Detalhe |", "|---|---|---|"]
    L += [f"| {n} | {'OK' if ok else 'FALHA'} | {d} |" for n, ok, d in checks]

    L += ["", "## 2. Fluxo alerta → status → recomendação, por evento", ""]
    for t in trilha:
        L += [f"### Evento {t['evento_id']} - {t['tag']} ({t['5_severidade_final']}, {t['5_situacao_final']})", "",
              f"1. **Alerta detectado** em {t['1_alerta_detectado_em']}. Leitura que motivou a classificação: {t['1_leitura_que_motivou_classificacao']}.",
              f"   {t['1_descricao_alerta']}",
              f"2. **Status do ativo:** {t['2_mudancas_status_ativo'] or '(sem mudança)'}.",
              f"3. **Recomendação técnica** (origem: {t['3_origem_recomendacao']}; {t['3_qtd_procedimentos']} procedimentos, "
              f"{t['3_qtd_referencias_manual']} referências):",
              f"   - Diagnóstico: {t['3_recomendacao_diagnostico']}",
              f"   - Ação: {t['3_recomendacao_acao']}",
              f"4. **Encaminhamento:** ordem {t['4_ordem_manutencao'] or '-'} para {t['4_encaminhado_para'] or '-'}.",
              f"5. **Encerramento:** {t['5_encerrado_em'] or 'ainda em aberto'}"
              + (f", por {t['5_encerrado_por']}. {str(t['5_resolucao']).rstrip('.')}" if t['5_encerrado_em'] else "") + ".",
              f"   Linha do tempo: {t['transicoes']}.", ""]

    L += ["## 3. Status final dos ativos", "", "| TAG | Motor | Status | Atualizado por | Temp. (°C) | Vibr. (mm/s) |", "|---|---|---|---|---|---|"]
    L += [f"| {s['tag']} | {s['motor']} | {s['status_operacional']} | {s['origem_atualizacao']} | "
          f"{s['temperatura']} | {s['vibracao']} |" for s in status]

    L += ["", "## 4. Ciclos executados", "", "| Ciclo | Status | Etapas com ressalva ou falha |", "|---|---|---|"]
    for c in ciclos:
        prob = [f"{e['etapa']}: {e['status']}" for e in etapas if e["ciclo"] == c["ciclo"] and e["status"] != "ok"]
        L.append(f"| {c['ciclo']} | {c['status']} | {'; '.join(prob) or '-'} |")

    erros = [x for x in log_regs if x.get("nivel") in ("ERROR",)]
    L += ["", "## 5. Tratamento de exceções observado", ""]
    if erros:
        L += [f"- Ciclo {x.get('ciclo')} / {x['etapa']}: {x['mensagem']}" for x in erros[:15]]
    avisos = [x for x in log_regs if x.get("evento") in ("arquivo_em_quarentena", "sem_leitura_nova", "clima_indisponivel")]
    L += [f"- Ciclo {x.get('ciclo')} / {x['etapa']}: {x['mensagem']}" for x in avisos[:15]]
    L += ["", "## 6. Modo de execução", ""] + modo()
    L += ["", "## 7. Arquivos desta pasta", "",
          "- `trilha_ponta_a_ponta.csv`: uma linha por evento, do alerta ao encerramento",
          "- `eventos_operacionais.csv`, `historico_eventos.csv`, `manutencoes.csv`, `auditoria_operacional.csv`",
          "- `execucoes_etapas.csv`: duração e resultado de cada etapa em cada ciclo",
          "- `status_final_ativos.csv`: estado dos motores ao final",
          "- `logs/execucao.jsonl`: log estruturado (uma linha JSON por registro)",
          "- `notificacoes/`: e-mails de alerta simulados", "- `contexto_rag/`: documentos entregues ao assistente",
          "- `predicta_evidencia.db`: cópia do banco SQLite ao final da execução", ""]
    caminho.write_text("\n".join(L), encoding="utf-8")

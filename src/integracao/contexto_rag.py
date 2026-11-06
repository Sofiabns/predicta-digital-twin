"""Fornecimento automático de dados operacionais para o assistente (RAG).

A cada ciclo, o estado atual, o histórico de eventos e as manutenções de cada
ativo são exportados como documentos de texto em ``data/rag/operacional`` e
reindexados. O assistente conversacional passa a responder com base no que
realmente aconteceu na planta, e não apenas no manual.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from src.integracao.config import Config
from src.integracao.limites import resolver_limites_todos
from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def _escrever_se_mudou(caminho: Path, conteudo: str) -> bool:
    if caminho.exists() and hashlib.sha256(caminho.read_bytes()).hexdigest() == hashlib.sha256(conteudo.encode()).hexdigest():
        return False
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(conteudo, encoding="utf-8")
    os.replace(tmp, caminho)          # troca atômica: o leitor nunca vê arquivo pela metade
    return True


def coletar_contexto() -> list[dict[str, Any]]:
    """Reúne, por ativo, perfil + estado + estatísticas + eventos + manutenções."""
    with get_connection() as conn:
        limites = resolver_limites_todos(conn)
        ativos = conn.execute(
            """SELECT o.motor_id, o.tag, o.codigo_motor, o.modelo_motor, o.fabricante_motor, o.status_operacional,
                      o.planta_nome, o.area_nome, o.linha_nome, o.localizacao_descricao,
                      dp.potencia, dp.tensao_nominal, dp.corrente_nominal, dp.rpm_nominal,
                      ul.timestamp AS ultima_ts, ul.temperatura, ul.vibracao, ul.corrente, ul.tensao, ul.rpm
               FROM vw_ativos_operacionais o
               LEFT JOIN dados_placa_motor dp ON dp.motor_id = o.motor_id
               LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id = o.motor_id
               WHERE o.tag IS NOT NULL ORDER BY o.tag""").fetchall()
        saida: list[dict[str, Any]] = []
        for a in ativos:
            est = conn.execute(
                """SELECT COUNT(*) n, ROUND(AVG(temperatura),1) t_med, ROUND(MAX(temperatura),1) t_max,
                          ROUND(AVG(vibracao),2) v_med, ROUND(MAX(vibracao),2) v_max
                   FROM (SELECT temperatura, vibracao FROM leituras WHERE motor_id = ?
                         ORDER BY timestamp DESC, id DESC LIMIT 100)""", (a["motor_id"],)).fetchone()
            eventos = conn.execute(
                """SELECT id, severidade, status_resolucao, descricao_anomalia, diagnostico_ia, acao_recomendada,
                          origem_recomendacao, ocorrencias, created_at, encerrado_em, resolucao
                   FROM eventos_operacionais WHERE tag_ativo = ? ORDER BY id DESC LIMIT 5""", (a["tag"],)).fetchall()
            manut = conn.execute(
                """SELECT id, tipo, status, prioridade, descricao, data_prevista, data_conclusao, tecnico
                   FROM manutencoes WHERE motor_id = ? ORDER BY id DESC LIMIT 5""", (a["motor_id"],)).fetchall()
            lim = limites.get(a["motor_id"])
            saida.append({
                "perfil": dict(a) | {"limites": {"temp_max": lim.temp_max, "vib_max": lim.vib_max, "fonte": lim.fonte}},
                "estatisticas": dict(est),
                "eventos": [dict(e) for e in eventos],
                "manutencoes": [dict(m) for m in manut],
            })
    return saida


def _nome_motor(p: dict[str, Any]) -> str:
    fab, mod = p["fabricante_motor"] or "", p["modelo_motor"] or ""
    return mod if fab and mod.lower().startswith(fab.lower()) else f"{fab} {mod}".strip()


def _documento_ativo(c: dict[str, Any]) -> str:
    p, e = c["perfil"], c["estatisticas"]
    L = [f"# Ativo {p['tag']} ({p['codigo_motor']})", "",
         "## Perfil",
         f"Motor {_nome_motor(p)} na {p['planta_nome']}, {p['area_nome']}, "
         f"{p['linha_nome']} ({p['localizacao_descricao']}).",
         f"Placa: potência {p['potencia']} kW, tensão nominal {p['tensao_nominal']} V, "
         f"corrente nominal {p['corrente_nominal']} A, {p['rpm_nominal']} rpm.",
         f"Limites usados: temperatura máxima {p['limites']['temp_max']:g} °C e vibração máxima "
         f"{p['limites']['vib_max']:g} mm/s (fonte: {p['limites']['fonte']}).", "",
         "## Estado atual",
         f"Status operacional: {p['status_operacional']}.",
         f"Última leitura ({p['ultima_ts']}): temperatura {p['temperatura']} °C, vibração {p['vibracao']} mm/s, "
         f"corrente {p['corrente']} A, tensão {p['tensao']} V, {p['rpm']} rpm.",
         f"Últimas {e['n']} leituras: temperatura média {e['t_med']} °C (máx. {e['t_max']}), "
         f"vibração média {e['v_med']} mm/s (máx. {e['v_max']}).", "",
         "## Histórico de eventos"]
    if not c["eventos"]:
        L.append("Nenhum evento registrado para este ativo.")
    for ev in c["eventos"]:
        fim = f" Encerrado em {ev['encerrado_em']}: {ev['resolucao']}" if ev["encerrado_em"] else ""
        L += [f"Evento {ev['id']} ({ev['created_at']}) - {ev['severidade']}, situação {ev['status_resolucao']}, "
              f"{ev['ocorrencias']} ocorrência(s). {ev['descricao_anomalia']}",
              f"Diagnóstico: {ev['diagnostico_ia']}", f"Ação recomendada: {ev['acao_recomendada']}.{fim}", ""]
    L.append("## Manutenções")
    if not c["manutencoes"]:
        L.append("Nenhuma ordem de manutenção registrada.")
    for m in c["manutencoes"]:
        L.append(f"Ordem {m['id']}: {m['tipo']}, {m['status']}, prioridade {m['prioridade']}, prevista para "
                 f"{m['data_prevista']}" + (f", técnico {m['tecnico']}" if m["tecnico"] else "") + ".")
    return "\n".join(L) + "\n"


def _resumo_planta(contextos: list[dict[str, Any]]) -> str:
    L = ["# Resumo da planta", "", "## Situação dos ativos"]
    for c in contextos:
        p = c["perfil"]
        abertos = [e for e in c["eventos"] if e["status_resolucao"] in ("pendente", "encaminhado", "em_atendimento")]
        L.append(f"{p['tag']}: status {p['status_operacional']}, temperatura {p['temperatura']} °C, "
                 f"vibração {p['vibracao']} mm/s, {len(abertos)} evento(s) em aberto.")
    return "\n".join(L) + "\n"


def exportar_contexto(cfg: Config | None = None) -> dict[str, Any]:
    """Gera os documentos e o arquivo .jsonl. Devolve quantos mudaram."""
    cfg = cfg or Config.carregar()
    cfg.rag_dir.mkdir(parents=True, exist_ok=True)
    contextos = coletar_contexto()
    alterados = 0
    nomes = set()
    for c in contextos:
        nome = f"{c['perfil']['tag']}.md"
        nomes.add(nome)
        alterados += _escrever_se_mudou(cfg.rag_dir / nome, _documento_ativo(c))
    nomes.add("resumo_planta.md")
    alterados += _escrever_se_mudou(cfg.rag_dir / "resumo_planta.md", _resumo_planta(contextos))
    jsonl = "\n".join(json.dumps(c, ensure_ascii=False, default=str) for c in contextos) + "\n"
    _escrever_se_mudou(cfg.rag_dir / "contexto_operacional.jsonl", jsonl)
    for antigo in cfg.rag_dir.glob("*.md"):          # remove documentos de ativos que não existem mais
        if antigo.name not in nomes:
            antigo.unlink()
    return {"ativos": len(contextos), "documentos_alterados": alterados, "diretorio": str(cfg.rag_dir)}


def montar_contexto_assistente(pergunta: str, top_k: int = 4) -> str:
    """Texto de contexto para o assistente: ativo citado (se houver) + trechos recuperados."""
    from src.analise.base_conhecimento import BaseConhecimento

    cfg = Config.carregar()
    partes: list[str] = []
    citados = {m.upper() for m in re.findall(r"(MTR-[A-Za-z0-9-]+)", pergunta, flags=re.I)}
    codigos = {m.upper() for m in re.findall(r"(MTR-\d{3})", pergunta, flags=re.I)}
    try:
        for doc in sorted(cfg.rag_dir.glob("MTR-*.md")):
            texto = doc.read_text(encoding="utf-8")
            cab = texto.splitlines()[0].upper() if texto else ""
            if doc.stem.upper() in citados or any(cod in cab for cod in codigos):
                partes.append(texto)
        if not partes and (cfg.rag_dir / "resumo_planta.md").exists():
            partes.append((cfg.rag_dir / "resumo_planta.md").read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("Contexto operacional indisponível: %s", exc)
    try:
        for t in BaseConhecimento().buscar_trechos(pergunta, top_k=top_k):
            partes.append(f"[{t.referencia()}]\n{t.texto}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Busca na base de conhecimento falhou: %s", exc)
    return "\n\n".join(partes)

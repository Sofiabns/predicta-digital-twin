"""
MCP (Model Context Protocol) Server.
Expõe ferramentas do Predicta Digital Twin para agentes LLM externos via STDIO.
"""

import sys
from pathlib import Path

# Configura path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from src.persistencia.database import get_connection

mcp = FastMCP("Predicta_CS03_MCP")

@mcp.tool()
def consultar_saude_motor(tag_ativo: str) -> str:
    """Retorna o status de saúde e as últimas leituras de um motor específico pelo TAG."""
    query = """
    SELECT status_operacional, ultima_temperatura, ultima_vibracao 
    FROM vw_digital_twin_ativos 
    WHERE tag = ?
    """
    with get_connection() as conn:
        cursor = conn.execute(query, (tag_ativo,))
        row = cursor.fetchone()
        if not row:
            return f"Motor com TAG {tag_ativo} não encontrado."
        return f"Status: {row['status_operacional']}, Temp: {row['ultima_temperatura']}°C, Vibração: {row['ultima_vibracao']} mm/s"

@mcp.tool()
def buscar_catalogo_normativo(fabricante: str, modelo: str) -> str:
    """Busca os limites normativos de um motor no catálogo."""
    query = "SELECT temp_max_tolerada, vibracao_limite_rms FROM catalogo_especificacoes_externas WHERE fabricante=? AND modelo_motor=?"
    with get_connection() as conn:
        cursor = conn.execute(query, (fabricante, modelo))
        row = cursor.fetchone()
        if not row:
            return "Catálogo não encontrado para este modelo."
        return f"Limites - Temp max: {row['temp_max_tolerada']}°C, Vibração RMS: {row['vibracao_limite_rms']} mm/s"

@mcp.tool()
def inspecionar_eventos(tag_ativo: str) -> str:
    """Lista o último evento crítico ou de alerta registrado para um determinado motor pelo TAG."""
    query = """
    SELECT severidade, diagnostico_ia, acao_recomendada, created_at 
    FROM eventos_operacionais 
    WHERE tag_ativo = ? 
    ORDER BY created_at DESC LIMIT 1
    """
    with get_connection() as conn:
        cursor = conn.execute(query, (tag_ativo,))
        row = cursor.fetchone()
        if not row:
            return f"Nenhum evento registrado para o TAG {tag_ativo}."
        return f"[{row['created_at']}] Severidade: {row['severidade']} | Diagnóstico: {row['diagnostico_ia']} | Ação: {row['acao_recomendada']}"

@mcp.tool()
def listar_eventos_abertos() -> str:
    """Lista os eventos operacionais ainda abertos (pendentes, encaminhados ou em atendimento)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT evento_id, tag_ativo, severidade, status_resolucao, ocorrencias, acao_recomendada "
            "FROM vw_eventos_abertos ORDER BY evento_id").fetchall()
    if not rows:
        return "Nenhum evento em aberto."
    return "\n".join(f"#{r['evento_id']} {r['tag_ativo']} | {r['severidade']} | {r['status_resolucao']} | "
                     f"{r['ocorrencias']} ocorrência(s) | Ação: {r['acao_recomendada']}" for r in rows)


@mcp.tool()
def consultar_historico_ativo(tag_ativo: str) -> str:
    """Mostra a linha do tempo dos eventos de um ativo, com encaminhamentos e resoluções."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT h.criado_em, h.evento_id, h.acao, h.status_novo, h.ator, h.observacao "
            "FROM historico_eventos h JOIN eventos_operacionais e ON e.id = h.evento_id "
            "WHERE e.tag_ativo = ? ORDER BY h.id DESC LIMIT 20", (tag_ativo,)).fetchall()
    if not rows:
        return f"Nenhum histórico para o TAG {tag_ativo}."
    return "\n".join(f"{r['criado_em']} | evento {r['evento_id']} | {r['acao']} -> {r['status_novo']} | "
                     f"{r['ator']} | {r['observacao']}" for r in rows)


@mcp.tool()
def buscar_procedimento_tecnico(descricao_problema: str) -> str:
    """Busca nos manuais técnicos os trechos mais relevantes para um problema descrito em texto."""
    from src.analise.base_conhecimento import BaseConhecimento
    trechos = BaseConhecimento().buscar_trechos(descricao_problema, top_k=3, colecao="manuais")
    if not trechos:
        return "Nenhum trecho relevante encontrado nos manuais."
    return "\n\n".join(f"[{t.referencia()}]\n{t.texto}" for t in trechos)


@mcp.tool()
def consultar_contexto_ativo(tag_ativo: str) -> str:
    """Devolve o documento de contexto operacional (perfil, estado, eventos e manutenções) do ativo."""
    from src.integracao.config import Config
    doc = Config.carregar().rag_dir / f"{tag_ativo}.md"
    return doc.read_text(encoding="utf-8") if doc.exists() else f"Sem contexto exportado para {tag_ativo}."


if __name__ == "__main__":
    mcp.run()

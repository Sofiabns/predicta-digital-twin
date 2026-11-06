"""Camada de servico de dados para o dashboard.

Centraliza queries agregadas usadas pelas abas do Gradio,
isolando o dashboard da camada de persistencia direta.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# KPIs - Visao Geral
# ============================================================
def obter_kpis() -> dict[str, Any]:
    """Retorna os principais indicadores agregados da operacao."""
    with get_connection() as conn:
        total_motores = conn.execute(
            "SELECT COUNT(*) FROM motores"
        ).fetchone()[0]

        motores_ativos = conn.execute(
            "SELECT COUNT(*) FROM motores WHERE status = 'ativo'"
        ).fetchone()[0]

        total_leituras = conn.execute(
            "SELECT COUNT(*) FROM leituras"
        ).fetchone()[0]

        total_anomalias = conn.execute(
            "SELECT COUNT(*) FROM anomalias"
        ).fetchone()[0]

        anomalias_criticas = conn.execute(
            "SELECT COUNT(*) FROM anomalias WHERE severidade = 'critica'"
        ).fetchone()[0]

        manutencoes_pendentes = conn.execute(
            "SELECT COUNT(*) FROM manutencoes WHERE status = 'pendente'"
        ).fetchone()[0]

        # ✅ CORREÇÃO: conta LEITURAS únicas com anomalia
        # (1 leitura pode ter várias anomalias: temperatura + vibração)
        leituras_com_anomalia = conn.execute(
            "SELECT COUNT(DISTINCT leitura_id) FROM anomalias "
            "WHERE leitura_id IS NOT NULL"
        ).fetchone()[0]

    # ✅ Taxa de saude: % de leituras SAUDAVEIS (sem qualquer anomalia)
    # Garantindo que fique sempre entre 0 e 100
    if total_leituras > 0:
        leituras_saudaveis = max(0, total_leituras - leituras_com_anomalia)
        taxa_saude = round((leituras_saudaveis / total_leituras) * 100, 1)
        taxa_saude = max(0.0, min(100.0, taxa_saude))  # clamp [0, 100]
    else:
        taxa_saude = 0.0

    return {
        "total_motores": total_motores,
        "motores_ativos": motores_ativos,
        "total_leituras": total_leituras,
        "total_anomalias": total_anomalias,
        "anomalias_criticas": anomalias_criticas,
        "manutencoes_pendentes": manutencoes_pendentes,
        "taxa_saude": taxa_saude,
        "leituras_com_anomalia": leituras_com_anomalia,  # bônus: pode exibir no dashboard
    }


# ============================================================
# Motores
# ============================================================
def listar_motores_resumo() -> pd.DataFrame:
    """Retorna a view consolidada de motores como DataFrame."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM v_resumo_motores ORDER BY anomalias_criticas DESC, codigo",
            conn,
        )
    return df


def listar_codigos_motores() -> list[str]:
    """Lista codigos de motores para uso em dropdowns."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT codigo FROM motores ORDER BY codigo"
        ).fetchall()
    return [r[0] for r in rows]


# ============================================================
# Telemetria
# ============================================================
def obter_telemetria_motor(codigo: str, limite: int = 500) -> pd.DataFrame:
    """Retorna leituras recentes de um motor com flag de anomalia real."""
    sql = """
        SELECT 
            l.id AS leitura_id,
            l.timestamp, 
            l.temperatura, l.vibracao, l.corrente, l.rpm, l.tensao,
            l.classe_origem,
            -- ✅ NOVO: marca se a leitura tem anomalia REAL detectada
            CASE WHEN EXISTS (
                SELECT 1 FROM anomalias a 
                WHERE a.leitura_id = l.id
            ) THEN 1 ELSE 0 END AS tem_anomalia_critica,
            CASE WHEN EXISTS (
                SELECT 1 FROM anomalias a 
                WHERE a.leitura_id = l.id 
                  AND a.tipo = 'temperatura'
            ) THEN 1 ELSE 0 END AS critica_temperatura,
            CASE WHEN EXISTS (
                SELECT 1 FROM anomalias a 
                WHERE a.leitura_id = l.id 
                  AND a.tipo = 'vibracao'
            ) THEN 1 ELSE 0 END AS critica_vibracao
        FROM leituras l
        JOIN motores m ON m.id = l.motor_id
        WHERE m.codigo = ?
        ORDER BY l.timestamp DESC
        LIMIT ?
    """
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn, params=(codigo, limite))

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
    return df


# ============================================================
# Anomalias
# ============================================================
def listar_anomalias(severidade: str | None = None) -> pd.DataFrame:
    """Retorna anomalias detectadas, opcionalmente filtradas por severidade."""
    base_sql = """
        SELECT
            a.id,
            m.codigo AS motor,
            a.tipo,
            a.severidade,
            ROUND(a.valor_medido, 2) AS valor_medido,
            ROUND(a.valor_limite, 2) AS valor_limite,
            a.descricao,
            a.detectado_em
        FROM anomalias a
        JOIN motores m ON m.id = a.motor_id
    """
    params: tuple = ()
    if severidade and severidade != "todas":
        base_sql += " WHERE a.severidade = ?"
        params = (severidade,)
    base_sql += " ORDER BY a.detectado_em DESC LIMIT 200"

    with get_connection() as conn:
        df = pd.read_sql_query(base_sql, conn, params=params)
    return df


def contagem_anomalias_por_severidade() -> pd.DataFrame:
    """Distribuicao de anomalias por severidade."""
    sql = """
        SELECT severidade, COUNT(*) AS total
        FROM anomalias
        GROUP BY severidade
        ORDER BY
            CASE severidade
                WHEN 'critica' THEN 1
                WHEN 'alta'    THEN 2
                WHEN 'media'   THEN 3
                WHEN 'baixa'   THEN 4
            END
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def contagem_anomalias_por_motor() -> pd.DataFrame:
    """Top motores com mais anomalias."""
    sql = """
        SELECT m.codigo AS motor, COUNT(a.id) AS total
        FROM motores m
        LEFT JOIN anomalias a ON a.motor_id = m.id
        GROUP BY m.id, m.codigo
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 10
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)

def obter_limites_motor(codigo: str) -> dict[str, float]:
    """Recupera limites normativos do catálogo."""
    sql = """
        SELECT c.temp_max_tolerada, c.vibracao_limite_rms
        FROM motores m
        LEFT JOIN dados_placa_motor dp ON dp.motor_id = m.id
        LEFT JOIN catalogo_especificacoes_externas c 
          ON c.modelo_motor = dp.modelo AND c.fabricante = dp.fabricante
        WHERE m.codigo = ?
    """
    with get_connection() as conn:
        row = conn.execute(sql, (codigo,)).fetchone()
        
    return {
        "temperatura": float(row["temp_max_tolerada"]) if row and row["temp_max_tolerada"] else 80.0,
        "vibracao": float(row["vibracao_limite_rms"]) if row and row["vibracao_limite_rms"] else 2.8
    }

# ============================================================
# CS02 — Digital Twin / Navegação operacional
# ============================================================
def listar_codigos_plantas() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT codigo FROM plantas ORDER BY nome").fetchall()
        return [str(r["codigo"]) for r in rows]


def listar_codigos_areas(planta_codigo: str | None) -> list[str]:
    if not planta_codigo:
        return []
    sql = """
        SELECT a.codigo FROM areas a
        JOIN plantas p ON p.id = a.planta_id
        WHERE p.codigo = ?
        ORDER BY a.nome
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (planta_codigo,)).fetchall()
        return [str(r["codigo"]) for r in rows]


def listar_codigos_linhas(planta_codigo: str | None, area_codigo: str | None) -> list[str]:
    if not planta_codigo or not area_codigo:
        return []
    sql = """
        SELECT ln.codigo FROM linhas ln
        JOIN areas ar ON ar.id = ln.area_id
        JOIN plantas p ON p.id = ar.planta_id
        WHERE p.codigo = ? AND ar.codigo = ?
        ORDER BY ln.nome
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (planta_codigo, area_codigo)).fetchall()
        return [str(r["codigo"]) for r in rows]


def listar_tags_por_hierarquia(
    planta_codigo: str | None,
    area_codigo: str | None,
    linha_codigo: str | None,
) -> list[str]:
    if not (planta_codigo and area_codigo and linha_codigo):
        return []
    sql = """
        SELECT aa.tag
        FROM associacoes_ativos aa
        JOIN localizacoes loc ON loc.id = aa.localizacao_id
        JOIN linhas ln ON ln.id = loc.linha_id
        JOIN areas ar ON ar.id = ln.area_id
        JOIN plantas p ON p.id = ar.planta_id
        WHERE p.codigo = ? AND ar.codigo = ? AND ln.codigo = ?
        ORDER BY aa.tag
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (planta_codigo, area_codigo, linha_codigo)).fetchall()
        return [str(r["tag"]) for r in rows]


def consultar_digital_twin_por_tag(tag: str) -> dict[str, Any] | None:
    """Retorna visão consolidada do Digital Twin para uma TAG."""
    if not tag or not str(tag).strip():
        return None
    sql = "SELECT * FROM vw_digital_twin_ativos WHERE tag = ? COLLATE NOCASE"
    with get_connection() as conn:
        row = conn.execute(sql, (tag.strip(),)).fetchone()
        return dict(row) if row else None


def consultar_digital_twin_por_codigo_motor(codigo_motor: str) -> dict[str, Any] | None:
    if not codigo_motor:
        return None
    sql = "SELECT * FROM vw_digital_twin_ativos WHERE codigo_motor = ?"
    with get_connection() as conn:
        row = conn.execute(sql, (codigo_motor.strip(),)).fetchone()
        return dict(row) if row else None


def obter_mapa_ativos_df() -> pd.DataFrame:
    """Coordenadas para scatter operacional."""
    sql = """
        SELECT
            codigo_motor,
            tag,
            planta_nome,
            area_nome,
            status_operacional,
            coordenada_x,
            coordenada_y
        FROM vw_ativos_operacionais
        WHERE tag IS NOT NULL
          AND coordenada_x IS NOT NULL
          AND coordenada_y IS NOT NULL
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def contar_anomalias_criticas_recentes(motor_id: int, dias: int = 7) -> int:
    sql = """
        SELECT COUNT(*) AS c FROM anomalias
        WHERE motor_id = ?
          AND severidade = 'critica'
          AND date(detectado_em) >= date('now', ?)
    """
    with get_connection() as conn:
        row = conn.execute(sql, (motor_id, f"-{int(dias)} days")).fetchone()
        return int(row["c"] if row and row["c"] is not None else 0)


def listar_anomalias_por_motor(codigo_motor: str, limite: int = 50) -> pd.DataFrame:
    sql = """
        SELECT a.tipo, a.severidade, a.valor_medido, a.valor_limite, a.detectado_em
        FROM anomalias a
        JOIN motores m ON m.id = a.motor_id
        WHERE m.codigo = ?
        ORDER BY a.detectado_em DESC
        LIMIT ?
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(codigo_motor, limite))


def listar_auditoria_operacional_df(limite: int = 40) -> pd.DataFrame:
    sql = """
        SELECT entidade, entidade_id, acao, origem, detalhes, data_evento
        FROM auditoria_operacional
        ORDER BY data_evento DESC
        LIMIT ?
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(limite,))

# ============================================================
# CS03 — Inteligência Operacional e Apoio à Decisão
# ============================================================
def listar_eventos_operacionais() -> pd.DataFrame:
    sql = """
        SELECT
            id AS 'Evento',
            tag_ativo AS 'TAG',
            severidade AS 'Severidade',
            status_resolucao AS 'Situação',
            ocorrencias AS 'Ocorrências',
            descricao_anomalia AS 'Descrição Anomalia',
            diagnostico_ia AS 'Diagnóstico',
            acao_recomendada AS 'Ação Recomendada',
            origem_recomendacao AS 'Origem',
            created_at AS 'Aberto em',
            encerrado_em AS 'Encerrado em'
        FROM eventos_operacionais
        ORDER BY id DESC
        LIMIT 50
    """
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn)
        return df.fillna("-")


def listar_historico_eventos(limite: int = 60) -> pd.DataFrame:
    """Linha do tempo (rastreabilidade) dos eventos: quem fez o quê e quando."""
    sql = """
        SELECT h.criado_em AS 'Quando', e.tag_ativo AS 'TAG', h.evento_id AS 'Evento',
               h.acao AS 'Ação', h.status_novo AS 'Situação', h.ator AS 'Responsável',
               h.observacao AS 'Observação'
        FROM historico_eventos h JOIN eventos_operacionais e ON e.id = h.evento_id
        ORDER BY h.id DESC LIMIT ?
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(limite,)).fillna("-")


def listar_ciclos_execucao(limite: int = 20) -> pd.DataFrame:
    """Últimos ciclos da automação integrada e seu resultado."""
    sql = """
        SELECT ciclo AS 'Ciclo', status AS 'Resultado', inicio AS 'Início', fim AS 'Fim', resumo_json AS 'Etapas'
        FROM execucoes_pipeline ORDER BY id DESC LIMIT ?
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(limite,)).fillna("-")


def obter_painel_decisao() -> pd.DataFrame:
    sql = """
        SELECT
            v.tag AS 'TAG',
            o.codigo_motor AS 'Ativo',
            v.area_nome AS 'Área',
            ROUND(v.ultima_temperatura, 1) AS 'Temp (°C)',
            ROUND(v.ultima_vibracao, 2) AS 'Vibração (mm/s)',
            UPPER(v.status_operacional) AS 'Status',
            COALESCE(v.diagnostico_ia, 'Normal') AS 'Diagnóstico IA'
        FROM vw_painel_decisao_operacional v
        LEFT JOIN vw_ativos_operacionais o ON o.tag = v.tag
    """
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn)
        return df.fillna("N/A")

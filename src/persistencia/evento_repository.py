"""
Repositório para eventos e anomalias registradas na operação.
"""

import sqlite3
from typing import List

from src.persistencia.database import get_connection


def registrar_evento(
    tag_ativo: str,
    codigo_motor: str,
    tipo_evento: str,
    severidade: str,
    descricao_anomalia: str,
    diagnostico_ia: str,
    acao_recomendada: str
) -> int:
    """Registra uma ocorrência ou anomalia operacional com diagnóstico."""
    query = """
    INSERT INTO eventos_operacionais (
        tag_ativo, codigo_motor, tipo_evento, severidade,
        descricao_anomalia, diagnostico_ia, acao_recomendada
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            query,
            (
                tag_ativo,
                codigo_motor,
                tipo_evento,
                severidade,
                descricao_anomalia,
                diagnostico_ia,
                acao_recomendada
            )
        )
        return cursor.lastrowid


def listar_eventos() -> List[sqlite3.Row]:
    query = "SELECT * FROM eventos_operacionais ORDER BY id DESC"
    with get_connection() as conn:
        cursor = conn.execute(query)
        return cursor.fetchall()


def obter_painel_decisao() -> List[sqlite3.Row]:
    """Obtém dados consolidados do painel de decisão da IA."""
    query = "SELECT * FROM vw_painel_decisao_operacional"
    with get_connection() as conn:
        cursor = conn.execute(query)
        return cursor.fetchall()

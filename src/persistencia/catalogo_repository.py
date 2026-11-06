"""
Repositório para persistência de dados técnicos e especificações do catálogo.
"""

import json
import sqlite3
from typing import Any, Dict, Optional

from src.persistencia.database import get_connection


def salvar_especificacao(
    modelo_motor: str,
    fabricante: str,
    temp_max: float,
    vib_max: float,
    guia_troubleshooting: Dict[str, Any],
    dados_climaticos: Dict[str, Any],
    fonte_url: str
) -> int:
    """Insere ou atualiza as especificações normativas de um motor."""
    with get_connection() as conn:
        existente = conn.execute(
            "SELECT id FROM catalogo_especificacoes_externas "
            "WHERE modelo_motor = ? AND fabricante = ? ORDER BY id DESC LIMIT 1",
            (modelo_motor, fabricante),
        ).fetchone()
        if existente:
            conn.execute(
                """UPDATE catalogo_especificacoes_externas
                   SET temp_max_tolerada = ?, vibracao_limite_rms = ?,
                       guia_troubleshooting_json = ?, dados_climaticos_json = ?,
                       fonte_url = ?, data_coleta = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (temp_max, vib_max, json.dumps(guia_troubleshooting),
                 json.dumps(dados_climaticos), fonte_url, existente["id"]),
            )
            return int(existente["id"])
    query = """
    INSERT INTO catalogo_especificacoes_externas (
        modelo_motor, fabricante, temp_max_tolerada, vibracao_limite_rms,
        guia_troubleshooting_json, dados_climaticos_json, fonte_url
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            query,
            (
                modelo_motor,
                fabricante,
                temp_max,
                vib_max,
                json.dumps(guia_troubleshooting),
                json.dumps(dados_climaticos),
                fonte_url
            )
        )
        return cursor.lastrowid


def buscar_especificacao(modelo: str, fabricante: str) -> Optional[sqlite3.Row]:
    query = """
    SELECT * FROM catalogo_especificacoes_externas
    WHERE modelo_motor = ? AND fabricante = ?
    ORDER BY id DESC LIMIT 1
    """
    with get_connection() as conn:
        cursor = conn.execute(query, (modelo, fabricante))
        return cursor.fetchone()

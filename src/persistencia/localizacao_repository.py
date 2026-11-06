"""Repositório de localizações físicas na planta (CS02)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def buscar_localizacao_por_codigo(
    linha_id: int,
    codigo: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM localizacoes WHERE linha_id = ? AND codigo = ?"
    if conn is not None:
        row = conn.execute(sql, (linha_id, codigo)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (linha_id, codigo)).fetchone()
        return dict(row) if row else None


def upsert_localizacao(
    linha_id: int,
    codigo: str,
    descricao: str | None,
    coordenada_x: float,
    coordenada_y: float,
    conn: sqlite3.Connection | None = None,
) -> tuple[int, str]:
    existente = buscar_localizacao_por_codigo(linha_id, codigo, conn=conn)
    if existente:
        sql = """
            UPDATE localizacoes
            SET descricao = ?, coordenada_x = ?, coordenada_y = ?,
                data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        params = (descricao, coordenada_x, coordenada_y, existente["id"])
        if conn is not None:
            conn.execute(sql, params)
        else:
            with get_connection() as c:
                c.execute(sql, params)
        return int(existente["id"]), "atualizado"
    sql_ins = """
        INSERT INTO localizacoes (linha_id, codigo, descricao, coordenada_x, coordenada_y)
        VALUES (?, ?, ?, ?, ?)
    """
    if conn is not None:
        cur = conn.execute(sql_ins, (linha_id, codigo, descricao, coordenada_x, coordenada_y))
        lid = int(cur.lastrowid)
    else:
        with get_connection() as c:
            cur = c.execute(sql_ins, (linha_id, codigo, descricao, coordenada_x, coordenada_y))
            lid = int(cur.lastrowid)
    logger.info("Localização criada: id=%s linha_id=%s codigo=%s", lid, linha_id, codigo)
    return lid, "criado"

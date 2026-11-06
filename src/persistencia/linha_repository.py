"""Repositório de linhas/setores (CS02)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def buscar_linha_por_codigo(
    area_id: int,
    codigo: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM linhas WHERE area_id = ? AND codigo = ?"
    if conn is not None:
        row = conn.execute(sql, (area_id, codigo)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (area_id, codigo)).fetchone()
        return dict(row) if row else None


def upsert_linha(
    area_id: int,
    codigo: str,
    nome: str,
    descricao: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> tuple[int, str]:
    existente = buscar_linha_por_codigo(area_id, codigo, conn=conn)
    if existente:
        sql = """
            UPDATE linhas
            SET nome = ?, descricao = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        if conn is not None:
            conn.execute(sql, (nome, descricao, existente["id"]))
        else:
            with get_connection() as c:
                c.execute(sql, (nome, descricao, existente["id"]))
        return int(existente["id"]), "atualizado"
    sql_ins = """
        INSERT INTO linhas (area_id, codigo, nome, descricao)
        VALUES (?, ?, ?, ?)
    """
    if conn is not None:
        cur = conn.execute(sql_ins, (area_id, codigo, nome, descricao))
        lid = int(cur.lastrowid)
    else:
        with get_connection() as c:
            cur = c.execute(sql_ins, (area_id, codigo, nome, descricao))
            lid = int(cur.lastrowid)
    logger.info("Linha criada: id=%s area_id=%s codigo=%s", lid, area_id, codigo)
    return lid, "criado"

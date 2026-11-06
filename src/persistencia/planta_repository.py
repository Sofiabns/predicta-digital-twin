"""Repositório de plantas industriais (CS02)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def buscar_planta_por_codigo(codigo: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    sql = "SELECT * FROM plantas WHERE codigo = ?"
    if conn is not None:
        row = conn.execute(sql, (codigo,)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (codigo,)).fetchone()
        return dict(row) if row else None


def inserir_planta(
    codigo: str,
    nome: str,
    descricao: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    sql = """
        INSERT INTO plantas (codigo, nome, descricao)
        VALUES (?, ?, ?)
    """
    if conn is not None:
        cur = conn.execute(sql, (codigo, nome, descricao))
        return int(cur.lastrowid)
    with get_connection() as c:
        cur = c.execute(sql, (codigo, nome, descricao))
        return int(cur.lastrowid)


def upsert_planta(
    codigo: str,
    nome: str,
    descricao: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> tuple[int, str]:
    """Retorna (id, 'criado'|'atualizado')."""
    existente = buscar_planta_por_codigo(codigo, conn=conn)
    if existente:
        sql = """
            UPDATE plantas
            SET nome = ?, descricao = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        if conn is not None:
            conn.execute(sql, (nome, descricao, existente["id"]))
        else:
            with get_connection() as c:
                c.execute(sql, (nome, descricao, existente["id"]))
        return int(existente["id"]), "atualizado"
    pid = inserir_planta(codigo, nome, descricao, conn=conn)
    logger.info("Planta criada: id=%s codigo=%s", pid, codigo)
    return pid, "criado"

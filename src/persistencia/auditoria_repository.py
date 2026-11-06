"""Persistência de eventos de auditoria operacional (CS02)."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def registrar_auditoria(
    entidade: str,
    acao: str,
    *,
    entidade_id: int | None = None,
    origem: str | None = None,
    detalhes: str | dict | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Insere um registro de auditoria. Se `conn` for informado, não faz commit."""
    if isinstance(detalhes, dict):
        detalhes_str = json.dumps(detalhes, ensure_ascii=False)
    else:
        detalhes_str = detalhes

    sql = """
        INSERT INTO auditoria_operacional (entidade, entidade_id, acao, origem, detalhes)
        VALUES (?, ?, ?, ?, ?)
    """

    def _run(c: sqlite3.Connection) -> int:
        cur = c.execute(
            sql,
            (entidade, entidade_id, acao, origem, detalhes_str),
        )
        return int(cur.lastrowid)

    if conn is not None:
        return _run(conn)

    with get_connection() as c:
        rid = _run(c)
    logger.debug("Auditoria registrada: id=%s entidade=%s acao=%s", rid, entidade, acao)
    return rid


def listar_auditoria_recente(limite: int = 50) -> list[dict[str, Any]]:
    """Lista eventos recentes para exibição (perfil admin)."""
    sql = """
        SELECT id, entidade, entidade_id, acao, origem, detalhes, data_evento
        FROM auditoria_operacional
        ORDER BY data_evento DESC
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (limite,)).fetchall()
        return [dict(r) for r in rows]

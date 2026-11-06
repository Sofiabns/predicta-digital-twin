"""Repositório de operações CRUD para a tabela `motores`."""

from __future__ import annotations

import logging
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def inserir_motor(
    codigo: str,
    modelo: str,
    localizacao: str,
    fabricante: str | None = None,
    potencia_kw: float | None = None,
    data_instalacao: str | None = None,
) -> int:
    """Insere um motor e retorna o ID gerado."""
    sql = """
        INSERT INTO motores (codigo, modelo, fabricante, localizacao, potencia_kw, data_instalacao)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(sql, (codigo, modelo, fabricante, localizacao, potencia_kw, data_instalacao))
        motor_id = cursor.lastrowid
        logger.info("Motor inserido: id=%s codigo=%s", motor_id, codigo)
        return motor_id


def buscar_motor_por_id(motor_id: int) -> dict[str, Any] | None:
    """Busca um motor pelo ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM motores WHERE id = ?", (motor_id,)).fetchone()
        return dict(row) if row else None


def buscar_motor_por_codigo(codigo: str) -> dict[str, Any] | None:
    """Busca um motor pelo código."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM motores WHERE codigo = ?", (codigo,)).fetchone()
        return dict(row) if row else None


def listar_motores(status: str | None = None) -> list[dict[str, Any]]:
    """Lista todos os motores, opcionalmente filtrando por status."""
    with get_connection() as conn:
        if status:
            rows = conn.execute("SELECT * FROM motores WHERE status = ? ORDER BY codigo", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM motores ORDER BY codigo").fetchall()
        return [dict(r) for r in rows]


def atualizar_status_motor(motor_id: int, status: str) -> bool:
    """Atualiza o status de um motor."""
    sql = """
        UPDATE motores
        SET status = ?, atualizado_em = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    with get_connection() as conn:
        cursor = conn.execute(sql, (status, motor_id))
        return cursor.rowcount > 0
    
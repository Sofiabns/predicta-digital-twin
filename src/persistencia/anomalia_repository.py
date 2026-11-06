"""Repositório de operações CRUD para a tabela `anomalias`."""

from __future__ import annotations

import logging
from typing import Any

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def inserir_anomalia(
    motor_id: int,
    leitura_id: int,
    tipo: str,
    severidade: str,
    valor_medido: float,
    valor_limite: float,
    descricao: str | None = None,
) -> int:
    """Registra uma anomalia detectada."""
    sql = """
        INSERT INTO anomalias (motor_id, leitura_id, tipo, severidade,
                               valor_medido, valor_limite, descricao)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            sql,
            (motor_id, leitura_id, tipo, severidade, valor_medido, valor_limite, descricao),
        )
        anomalia_id = cursor.lastrowid
        logger.warning(
            "Anomalia registrada: motor=%s tipo=%s severidade=%s valor=%.2f",
            motor_id, tipo, severidade, valor_medido,
        )
        return anomalia_id


def listar_anomalias_por_motor(motor_id: int, limite: int = 50) -> list[dict[str, Any]]:
    """Lista as anomalias de um motor específico."""
    sql = """
        SELECT * FROM anomalias
        WHERE motor_id = ?
        ORDER BY detectado_em DESC
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (motor_id, limite)).fetchall()
        return [dict(r) for r in rows]


def listar_anomalias_criticas_nao_notificadas() -> list[dict[str, Any]]:
    """Lista anomalias críticas que ainda não foram notificadas."""
    sql = """
        SELECT a.*, m.codigo AS motor_codigo, m.localizacao
        FROM anomalias a
        JOIN motores m ON m.id = a.motor_id
        WHERE a.severidade IN ('alta', 'critica')
          AND a.notificado = 0
        ORDER BY a.detectado_em ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def marcar_como_notificada(anomalia_id: int) -> bool:
    """Marca anomalia como notificada."""
    with get_connection() as conn:
        cursor = conn.execute("UPDATE anomalias SET notificado = 1 WHERE id = ?", (anomalia_id,))
        return cursor.rowcount > 0


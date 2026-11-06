"""Repositório de operações CRUD para a tabela `leituras`."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def inserir_leitura(
    motor_id: int,
    temperatura: float,
    vibracao: float,
    corrente: float,
    tensao: float | None = None,
    rpm: float | None = None,
    timestamp: str | None = None,
    label_origem: int | None = None,
    classe_origem: str | None = None,
) -> int:
    """Insere uma leitura telemétrica e retorna o ID gerado.

    Args:
        motor_id: FK para o motor monitorado.
        temperatura: em °C.
        vibracao: em mm/s.
        corrente: em Amperes.
        tensao: em Volts (opcional, mas recomendado).
        rpm: rotações por minuto (opcional).
        timestamp: ISO 8601. Se omitido, usa CURRENT_TIMESTAMP do banco.
        label_origem: rótulo de anomalia da fonte (0=normal, 1=anomalia).
        classe_origem: classe da fonte ('normal', 'alerta', 'critico').

    Returns:
        ID autoincrementado da leitura inserida.
    """
    if timestamp:
        sql = """
            INSERT INTO leituras
                (motor_id, temperatura, vibracao, corrente, tensao, rpm,
                 timestamp, label_origem, classe_origem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            motor_id, temperatura, vibracao, corrente, tensao, rpm,
            timestamp, label_origem, classe_origem,
        )
    else:
        sql = """
            INSERT INTO leituras
                (motor_id, temperatura, vibracao, corrente, tensao, rpm,
                 label_origem, classe_origem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            motor_id, temperatura, vibracao, corrente, tensao, rpm,
            label_origem, classe_origem,
        )

    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        logger.debug("Leitura inserida: motor_id=%s, id=%s", motor_id, cursor.lastrowid)
        return cursor.lastrowid


def inserir_leituras_lote(leituras: Iterable[dict[str, Any]]) -> int:
    """
    Insere múltiplas leituras em uma única transação (mais performático).

    Args:
        leituras: iterável de dicts com chaves:
            motor_id, temperatura, vibracao, corrente, tensao, rpm, timestamp,
            label_origem, classe_origem.

    Returns:
        Quantidade de leituras inseridas.
    """
    sql = """
        INSERT INTO leituras
            (motor_id, temperatura, vibracao, corrente, tensao, rpm,
             timestamp, label_origem, classe_origem)
        VALUES
            (:motor_id, :temperatura, :vibracao, :corrente, :tensao, :rpm,
             :timestamp, :label_origem, :classe_origem)
    """
    leituras_list = list(leituras)

    if not leituras_list:
        logger.warning("Nenhuma leitura fornecida para inserção em lote")
        return 0

    # Garante que todas as chaves existam (evita KeyError no executemany)
    chaves_obrigatorias = {
        "motor_id", "temperatura", "vibracao", "corrente",
        "tensao", "rpm", "timestamp",
        "label_origem", "classe_origem",
    }
    for leitura in leituras_list:
        for chave in chaves_obrigatorias:
            leitura.setdefault(chave, None)

    with get_connection() as conn:
        conn.executemany(sql, leituras_list)
        logger.info("Inseridas %d leituras em lote", len(leituras_list))
        return len(leituras_list)


def listar_leituras_motor(motor_id: int, limite: int = 100) -> list[dict[str, Any]]:
    """Lista as últimas N leituras de um motor."""
    sql = """
        SELECT * FROM leituras
        WHERE motor_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (motor_id, limite)).fetchall()
        return [dict(r) for r in rows]


def listar_leituras_nao_processadas(limite: int = 50) -> list[dict[str, Any]]:
    """Lista leituras ainda não processadas (para análise de anomalias)."""
    sql = """
        SELECT * FROM leituras
        WHERE processado = 0
        ORDER BY timestamp ASC
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (limite,)).fetchall()
        return [dict(r) for r in rows]


def marcar_como_processada(leitura_id: int) -> bool:
    """Marca uma leitura como processada."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE leituras SET processado = 1 WHERE id = ?", (leitura_id,)
        )
        return cursor.rowcount > 0


def contar_leituras(motor_id: int | None = None) -> int:
    """Conta o total de leituras, opcionalmente filtradas por motor."""
    with get_connection() as conn:
        if motor_id is not None:
            row = conn.execute(
                "SELECT COUNT(*) as total FROM leituras WHERE motor_id = ?",
                (motor_id,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as total FROM leituras").fetchone()
        return row["total"]

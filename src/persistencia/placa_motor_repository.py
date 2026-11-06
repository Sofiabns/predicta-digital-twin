"""Dados técnicos extraídos da placa do motor (CS02)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.persistencia.auditoria_repository import registrar_auditoria
from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


def buscar_placa_por_motor_id(
    motor_id: int,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM dados_placa_motor WHERE motor_id = ?"
    if conn is not None:
        row = conn.execute(sql, (motor_id,)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (motor_id,)).fetchone()
        return dict(row) if row else None


def upsert_dados_placa(
    motor_id: int,
    dados: dict[str, Any],
    origem_arquivo: str,
    *,
    origem_evento: str = "pipeline_placa",
    conn: sqlite3.Connection | None = None,
) -> str:
    """Insere ou atualiza dados da placa. Retorna 'criado' ou 'atualizado'."""

    def _float(key: str) -> float | None:
        v = dados.get(key)
        if v is None or v == "":
            return None
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    campos = {
        "fabricante": dados.get("fabricante"),
        "modelo": dados.get("modelo"),
        "numero_serie": dados.get("numero_serie"),
        "potencia": _float("potencia"),
        "tensao_nominal": _float("tensao_nominal"),
        "corrente_nominal": _float("corrente_nominal"),
        "rpm_nominal": _float("rpm_nominal"),
        "frequencia": _float("frequencia"),
        "fator_servico": _float("fator_servico"),
        "rendimento": _float("rendimento"),
        "origem_imagem": dados.get("origem_imagem"),
        "origem_arquivo": origem_arquivo,
        "confianca_extracao": _float("confianca_extracao"),
    }

    def _run(c: sqlite3.Connection) -> str:
        existente = c.execute(
            "SELECT id FROM dados_placa_motor WHERE motor_id = ?",
            (motor_id,),
        ).fetchone()
        if existente:
            c.execute(
                """
                UPDATE dados_placa_motor SET
                    fabricante = ?, modelo = ?, numero_serie = ?,
                    potencia = ?, tensao_nominal = ?, corrente_nominal = ?,
                    rpm_nominal = ?, frequencia = ?, fator_servico = ?, rendimento = ?,
                    origem_imagem = ?, origem_arquivo = ?,
                    data_extracao = CURRENT_TIMESTAMP,
                    confianca_extracao = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE motor_id = ?
                """,
                (
                    campos["fabricante"],
                    campos["modelo"],
                    campos["numero_serie"],
                    campos["potencia"],
                    campos["tensao_nominal"],
                    campos["corrente_nominal"],
                    campos["rpm_nominal"],
                    campos["frequencia"],
                    campos["fator_servico"],
                    campos["rendimento"],
                    campos["origem_imagem"],
                    campos["origem_arquivo"],
                    campos["confianca_extracao"],
                    motor_id,
                ),
            )
            acao = "atualizado"
            eid = int(existente["id"])
        else:
            cur = c.execute(
                """
                INSERT INTO dados_placa_motor (
                    motor_id, fabricante, modelo, numero_serie,
                    potencia, tensao_nominal, corrente_nominal,
                    rpm_nominal, frequencia, fator_servico, rendimento,
                    origem_imagem, origem_arquivo, confianca_extracao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    motor_id,
                    campos["fabricante"],
                    campos["modelo"],
                    campos["numero_serie"],
                    campos["potencia"],
                    campos["tensao_nominal"],
                    campos["corrente_nominal"],
                    campos["rpm_nominal"],
                    campos["frequencia"],
                    campos["fator_servico"],
                    campos["rendimento"],
                    campos["origem_imagem"],
                    campos["origem_arquivo"],
                    campos["confianca_extracao"],
                ),
            )
            acao = "criado"
            eid = int(cur.lastrowid)

        registrar_auditoria(
            "dados_placa_motor",
            acao,
            entidade_id=eid,
            origem=origem_evento,
            detalhes={"motor_id": motor_id, "arquivo": origem_arquivo},
            conn=c,
        )
        return acao

    if conn is not None:
        return _run(conn)

    with get_connection() as c:
        resultado = _run(c)
    logger.info("Dados de placa %s: motor_id=%s", resultado, motor_id)
    return resultado

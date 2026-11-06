"""Transformação: validação, limpeza e mapeamento de colunas do CSV."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Mapeamento das colunas do CSV -> colunas da tabela `leituras`
MAPEAMENTO_COLUNAS = {
    "timestamp": "timestamp",
    "tensao_V": "tensao",
    "corrente_A": "corrente",
    "temperatura_C": "temperatura",
    "rpm": "rpm",
    "vibracao_mm_s": "vibracao",
    "label_anomalia": "label_origem",
    "classe_manutencao": "classe_origem",
}

# Classes válidas (alinhadas com CHECK do schema)
CLASSES_VALIDAS = {"normal", "alerta", "critico"}


def _to_float(valor: str | None) -> float | None:
    """Converte string em float; retorna None se vazio ou inválido."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def _to_int(valor: str | None) -> int | None:
    """Converte string em int; retorna None se vazio ou inválido."""
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))  # tolera "1.0"
    except (ValueError, TypeError):
        return None


def _normalizar_timestamp(valor: str | None) -> str | None:
    """Valida e normaliza timestamp para formato ISO 8601 (YYYY-MM-DD HH:MM:SS)."""
    if not valor:
        return None
    formatos = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M")
    for fmt in formatos:
        try:
            dt = datetime.strptime(valor.strip(), fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _normalizar_classe(valor: str | None) -> str | None:
    """Valida classe_origem contra valores permitidos."""
    if not valor:
        return None
    classe = valor.strip().lower()
    return classe if classe in CLASSES_VALIDAS else None


def transformar_linha(
    linha: dict[str, Any],
    motor_id: int,
) -> dict[str, Any] | None:
    """Transforma uma linha bruta do CSV em registro pronto pra inserção.

    Args:
        linha: dict com chaves do CSV original.
        motor_id: ID do motor (FK) ao qual associar a leitura.

    Returns:
        Dict no formato esperado por `inserir_leituras_lote`, ou None se a
        linha for inválida (timestamp ausente, por exemplo).
    """
    timestamp = _normalizar_timestamp(linha.get("timestamp"))
    if not timestamp:
        logger.debug("Linha descartada (timestamp inválido): %s", linha)
        return None

    return {
        "motor_id": motor_id,
        "timestamp": timestamp,
        "tensao": _to_float(linha.get("tensao_V")),
        "corrente": _to_float(linha.get("corrente_A")),
        "temperatura": _to_float(linha.get("temperatura_C")),
        "rpm": _to_float(linha.get("rpm")),
        "vibracao": _to_float(linha.get("vibracao_mm_s")),
        "label_origem": _to_int(linha.get("label_anomalia")),
        "classe_origem": _normalizar_classe(linha.get("classe_manutencao")),
    }


def transformar_lote(
    linhas: list[dict[str, Any]],
    motor_id: int,
) -> tuple[list[dict[str, Any]], int]:
    """Transforma um lote de linhas e retorna registros válidos + contagem de descartes.

    Returns:
        Tupla (registros_validos, total_descartados).
    """
    validos: list[dict[str, Any]] = []
    descartadas = 0

    for linha in linhas:
        registro = transformar_linha(linha, motor_id)
        if registro is None:
            descartadas += 1
        else:
            validos.append(registro)

    if descartadas:
        logger.warning("Linhas descartadas na transformação: %d", descartadas)

    logger.info(
        "Transformação concluída | válidas=%d | descartadas=%d",
        len(validos),
        descartadas,
    )
    return validos, descartadas

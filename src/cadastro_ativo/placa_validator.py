"""Validação de registros estruturados de placa (OCR simulado) — CS02."""

from __future__ import annotations

from typing import Any

CAMPOS_OBRIGATORIOS = (
    "codigo_motor",
    "fabricante",
    "modelo",
    "numero_serie",
    "origem_imagem",
    "confianca_extracao",
)


def validar_payload_placa(payload: dict[str, Any]) -> tuple[bool, str | None]:
    for campo in CAMPOS_OBRIGATORIOS:
        v = payload.get(campo)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return False, f"campo_obrigatorio_ausente:{campo}"
    return True, None

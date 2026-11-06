"""Validação de linhas do CSV de cadastro operacional (CS02)."""

from __future__ import annotations

from typing import Any

CAMPOS_OBRIGATORIOS = (
    "codigo_motor",
    "tag",
    "planta_codigo",
    "planta_nome",
    "area_codigo",
    "area_nome",
    "linha_codigo",
    "linha_nome",
    "localizacao_codigo",
)


def validar_linha_cadastro(row: dict[str, Any]) -> tuple[bool, str | None]:
    """Retorna (ok, mensagem_erro)."""
    for campo in CAMPOS_OBRIGATORIOS:
        val = row.get(campo)
        if val is None or str(val).strip() == "":
            return False, f"campo_obrigatorio_ausente:{campo}"
    return True, None

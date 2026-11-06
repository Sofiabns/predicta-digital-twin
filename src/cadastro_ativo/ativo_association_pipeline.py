"""Pipeline RPA: associação Ativo / TAG / Localização (CS02)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.cadastro_ativo.ativo_loader import (
    RAW_CADASTRO_PATH,
    arquivar_cadastro_processado,
    carregar_cadastro_csv,
)
from src.cadastro_ativo.ativo_validator import validar_linha_cadastro
from src.persistencia.ativo_repository import sincronizar_cadastro_operacional

logger = logging.getLogger(__name__)


def executar_associacao_ativos(
    caminho_csv: Path | None = None,
    *,
    arquivar: bool = True,
    origem: str = "rpa_cadastro_csv",
) -> dict[str, Any]:
    """
    Processa `data/raw/cadastro_ativos.csv` (ou caminho informado).

    Returns:
        Resumo com contagens e lista de erros.
    """
    caminho = caminho_csv or RAW_CADASTRO_PATH
    resumo: dict[str, Any] = {
        "arquivo": str(caminho),
        "lidos": 0,
        "validos": 0,
        "criados": 0,
        "atualizados": 0,
        "inalterados": 0,
        "ignorados": 0,
        "erros": 0,
        "detalhes_erros": [],
    }

    if not caminho.exists():
        logger.warning("Arquivo de cadastro não encontrado: %s", caminho)
        resumo["detalhes_erros"].append("arquivo_nao_encontrado")
        return resumo

    try:
        linhas = carregar_cadastro_csv(caminho)
    except Exception as exc:
        logger.exception("Falha ao ler CSV de cadastro: %s", exc)
        resumo["erros"] += 1
        resumo["detalhes_erros"].append(str(exc))
        return resumo

    resumo["lidos"] = len(linhas)

    for idx, row in enumerate(linhas, start=1):
        ok, motivo = validar_linha_cadastro(row)
        if not ok:
            resumo["erros"] += 1
            msg = f"linha_{idx}:{motivo}"
            resumo["detalhes_erros"].append(msg)
            logger.error("Linha inválida (%s): %s", idx, motivo)
            continue

        resumo["validos"] += 1
        try:
            out = sincronizar_cadastro_operacional(row, origem=origem)
        except Exception as exc:
            resumo["erros"] += 1
            resumo["detalhes_erros"].append(f"linha_{idx}:{exc}")
            logger.exception("Erro ao processar linha %s", idx)
            continue

        if out["status"] == "ignorado":
            resumo["ignorados"] += 1
            logger.error("Motor ignorado: %s", out.get("codigo_motor"))
            continue

        assoc = out.get("associacao")
        if assoc == "criado":
            resumo["criados"] += 1
        elif assoc == "atualizado":
            resumo["atualizados"] += 1
        elif assoc == "inalterado":
            resumo["inalterados"] += 1

    if arquivar and resumo["lidos"] > 0:
        try:
            arquivar_cadastro_processado(caminho)
        except Exception as exc:
            logger.warning("Falha ao arquivar CSV: %s", exc)
            resumo["detalhes_erros"].append(f"arquivamento:{exc}")

    return resumo

"""Extração: leitura de arquivos CSV brutos do diretório data/raw/."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Diretório padrão de dados brutos
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def listar_arquivos_csv(diretorio: Path | None = None) -> list[Path]:
    """Lista todos os arquivos .csv no diretório informado.

    Args:
        diretorio: diretório a inspecionar. Padrão: data/raw/.

    Returns:
        Lista de Paths dos CSVs encontrados (ordenados alfabeticamente).
    """
    dir_alvo = diretorio or RAW_DIR
    if not dir_alvo.exists():
        logger.warning("Diretório não existe: %s", dir_alvo)
        return []

    arquivos = sorted(dir_alvo.glob("*.csv"))
    logger.info("Encontrados %d arquivo(s) CSV em %s", len(arquivos), dir_alvo)
    return arquivos


def extrair_csv(caminho: Path) -> list[dict[str, Any]]:
    """Lê um CSV e retorna lista de dicionários (uma por linha).

    Args:
        caminho: caminho absoluto ou relativo do CSV.

    Returns:
        Lista de dicts com chaves vindas do header do CSV.

    Raises:
        FileNotFoundError: se o arquivo não existir.
        ValueError: se o CSV estiver vazio ou sem header.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"CSV não encontrado: {caminho}")

    logger.info("Extraindo dados de: %s", caminho.name)

    with caminho.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV sem cabeçalho: {caminho}")

        linhas = list(reader)

    if not linhas:
        logger.warning("CSV vazio (sem dados): %s", caminho.name)
        return []

    logger.info(
        "Extraídas %d linha(s) | colunas: %s",
        len(linhas),
        list(linhas[0].keys()),
    )
    return linhas


def extrair_codigo_motor(caminho: Path) -> str | None:
    """Extrai o código do motor a partir do nome do arquivo.

    Convenção: `leituras_<CODIGO>.csv` -> retorna `<CODIGO>`.
    Ex.: `leituras_MTR-001.csv` -> `MTR-001`.

    Returns:
        Código do motor ou None se o padrão não for encontrado.
    """
    nome = caminho.stem  # sem extensão
    if not nome.startswith("leituras_"):
        logger.warning("Arquivo fora do padrão 'leituras_<CODIGO>.csv': %s", caminho.name)
        return None

    codigo = nome.replace("leituras_", "", 1).strip()
    return codigo or None

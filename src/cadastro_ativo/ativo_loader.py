"""Carregamento de CSV de cadastro de ativos (CS02)."""

from __future__ import annotations

import csv
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CADASTRO_PATH = PROJECT_ROOT / "data" / "raw" / "cadastro_ativos.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def carregar_cadastro_csv(caminho: Path) -> list[dict[str, Any]]:
    """Lê CSV com utf-8-sig (Excel) ou utf-8."""
    if not caminho.exists():
        raise FileNotFoundError(str(caminho))
    linhas: list[dict[str, Any]] = []
    for enc in ("utf-8-sig", "utf-8"):
        try:
            with caminho.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    raise ValueError("CSV sem cabeçalho")
                linhas = [dict(r) for r in reader]
            logger.info("CSV cadastro lido com encoding=%s linhas=%d", enc, len(linhas))
            return linhas
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"Não foi possível decodificar: {caminho}")


def arquivar_cadastro_processado(origem: Path) -> Path:
    """Move CSV processado para data/processed/ com timestamp."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PROCESSED_DIR / f"{origem.stem}_{carimbo}{origem.suffix}"
    shutil.move(str(origem), str(destino))
    logger.info("Cadastro arquivado: %s -> %s", origem.name, destino.name)
    return destino

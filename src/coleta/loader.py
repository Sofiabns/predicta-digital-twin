"""Carga: persistência das leituras transformadas no banco SQLite."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.persistencia.leitura_repository import inserir_leituras_lote

logger = logging.getLogger(__name__)

# Diretório para arquivos já processados
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def carregar_leituras(registros: list[dict[str, Any]]) -> int:
    """Insere registros já transformados no banco em lote.

    Args:
        registros: lista de dicts no formato do `inserir_leituras_lote`.

    Returns:
        Quantidade de registros inseridos.
    """
    if not registros:
        logger.warning("Nenhum registro para carregar no banco")
        return 0

    qtd = inserir_leituras_lote(registros)
    logger.info("Carga concluída | registros inseridos: %d", qtd)
    return qtd


def arquivar_csv_processado(origem: Path) -> Path:
    """Move o CSV processado para data/processed/ com timestamp no nome.

    Evita reprocessar o mesmo arquivo na próxima execução.

    Args:
        origem: caminho do CSV em data/raw/.

    Returns:
        Novo caminho do arquivo em data/processed/.
    """
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PROCESSED_DIR / f"{origem.stem}_{carimbo}{origem.suffix}"

    shutil.move(str(origem), str(destino))
    logger.info("Arquivo arquivado: %s -> %s", origem.name, destino.name)
    return destino

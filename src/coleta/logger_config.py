"""Configuração centralizada de logging para o pipeline de coleta."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

# Diretório de logs (criado se não existir)
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def configurar_logger(
    nome: str = "rpa-cs01",
    nivel: int = logging.INFO,
    arquivo: bool = True,
) -> logging.Logger:
    """Configura logger com saída em console e arquivo (opcional).

    Args:
        nome: nome do logger (aparece nos registros).
        nivel: nível mínimo (DEBUG, INFO, WARNING, ERROR).
        arquivo: se True, grava também em logs/pipeline_YYYYMMDD.log.

    Returns:
        Logger configurado pronto para uso.
    """
    logger = logging.getLogger(nome)
    logger.setLevel(nivel)

    # Evita handlers duplicados em re-execuções
    if logger.handlers:
        return logger

    formato = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de console
    console = logging.StreamHandler()
    console.setLevel(nivel)
    console.setFormatter(formato)
    logger.addHandler(console)

    # Handler de arquivo
    if arquivo:
        data_str = datetime.now().strftime("%Y%m%d")
        log_path = LOG_DIR / f"pipeline_{data_str}.log"
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # arquivo grava tudo
        file_handler.setFormatter(formato)
        logger.addHandler(file_handler)

    return logger

"""Orquestração do pipeline ETL: Extract -> Transform -> Load."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.coleta.extractor import (
    RAW_DIR,
    extrair_codigo_motor,
    extrair_csv,
    listar_arquivos_csv,
)
from src.coleta.loader import arquivar_csv_processado, carregar_leituras
from src.coleta.transformer import transformar_lote
from src.persistencia.motor_repository import buscar_motor_por_codigo

logger = logging.getLogger(__name__)


def processar_arquivo(
    caminho: Path,
    arquivar: bool = True,
) -> dict[str, Any]:
    """Executa o ETL completo para um único arquivo CSV.

    Args:
        caminho: CSV a processar.
        arquivar: se True, move para data/processed/ ao final.

    Returns:
        Dict com estatísticas: arquivo, motor, extraidas, validas,
        descartadas, inseridas, status.
    """
    resultado: dict[str, Any] = {
        "arquivo": caminho.name,
        "motor": None,
        "extraidas": 0,
        "validas": 0,
        "descartadas": 0,
        "inseridas": 0,
        "status": "erro",
    }

    # 1. Identifica o motor pelo nome do arquivo
    codigo = extrair_codigo_motor(caminho)
    if not codigo:
        logger.error("Não foi possível extrair código do motor: %s", caminho.name)
        return resultado

    resultado["motor"] = codigo

    motor = buscar_motor_por_codigo(codigo)
    if not motor:
        logger.error(
            "Motor '%s' não cadastrado no banco. Cadastre antes de processar.",
            codigo,
        )
        resultado["status"] = "motor_nao_cadastrado"
        return resultado

    motor_id = motor["id"]

    # 2. EXTRACT
    try:
        linhas = extrair_csv(caminho)
    except Exception as exc:
        logger.exception("Falha na extração de %s: %s", caminho.name, exc)
        return resultado

    resultado["extraidas"] = len(linhas)
    if not linhas:
        resultado["status"] = "vazio"
        return resultado

    # 3. TRANSFORM
    validos, descartadas = transformar_lote(linhas, motor_id)
    resultado["validas"] = len(validos)
    resultado["descartadas"] = descartadas

    if not validos:
        resultado["status"] = "sem_registros_validos"
        return resultado

    # 4. LOAD
    try:
        inseridas = carregar_leituras(validos)
        resultado["inseridas"] = inseridas
    except Exception as exc:
        logger.exception("Falha na carga de %s: %s", caminho.name, exc)
        return resultado

    # 5. Arquivamento
    if arquivar:
        try:
            arquivar_csv_processado(caminho)
        except Exception as exc:
            logger.warning("Falha ao arquivar %s: %s", caminho.name, exc)

    resultado["status"] = "ok"
    return resultado


def executar_pipeline(
    diretorio: Path | None = None,
    arquivar: bool = True,
) -> list[dict[str, Any]]:
    """Executa o pipeline para TODOS os CSVs de um diretório.

    Args:
        diretorio: pasta com CSVs. Padrão: data/raw/.
        arquivar: se True, move arquivos processados.

    Returns:
        Lista de dicts (um por arquivo) com estatísticas.
    """
    dir_alvo = diretorio or RAW_DIR
    arquivos = listar_arquivos_csv(dir_alvo)

    if not arquivos:
        logger.warning("Nenhum CSV encontrado em %s", dir_alvo)
        return []

    logger.info("=" * 60)
    logger.info("INICIANDO PIPELINE | arquivos: %d", len(arquivos))
    logger.info("=" * 60)

    resultados = []
    for arquivo in arquivos:
        logger.info("-" * 60)
        logger.info("Processando: %s", arquivo.name)
        resultado = processar_arquivo(arquivo, arquivar=arquivar)
        resultados.append(resultado)
        logger.info("Resultado: %s", resultado)

    logger.info("=" * 60)
    logger.info("PIPELINE FINALIZADO | %d arquivo(s) processado(s)", len(resultados))
    logger.info("=" * 60)
    return resultados

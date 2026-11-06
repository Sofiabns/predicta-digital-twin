"""Pipeline RPA: integração de dados técnicos da placa (OCR simulado → JSON) — CS02."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.cadastro_ativo.placa_validator import validar_payload_placa
from src.persistencia.motor_repository import buscar_motor_por_codigo
from src.persistencia.placa_motor_repository import upsert_dados_placa

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PLACAS_DIR = PROJECT_ROOT / "data" / "raw" / "placas_extraidas"
PROCESSED_PLACAS_DIR = PROJECT_ROOT / "data" / "processed" / "placas_extraidas"


def _carregar_json(caminho: Path) -> dict[str, Any]:
    texto = caminho.read_text(encoding="utf-8")
    data = json.loads(texto)
    if not isinstance(data, dict):
        raise ValueError("JSON raiz deve ser um objeto")
    return data


def executar_pipeline_placas(
    diretorio: Path | None = None,
    *,
    arquivar: bool = True,
) -> dict[str, Any]:
    """
    Lê todos os `.json` do diretório de placas extraídas, valida e persiste.

    Returns:
        Resumo com contagens.
    """
    dir_alvo = diretorio or RAW_PLACAS_DIR
    resumo: dict[str, Any] = {
        "diretorio": str(dir_alvo),
        "lidos": 0,
        "validos": 0,
        "criados": 0,
        "atualizados": 0,
        "ignorados": 0,
        "erros": 0,
        "detalhes_erros": [],
    }

    if not dir_alvo.exists():
        logger.warning("Diretório de placas não existe: %s", dir_alvo)
        resumo["detalhes_erros"].append("diretorio_inexistente")
        return resumo

    PROCESSED_PLACAS_DIR.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(dir_alvo.glob("*.json"))
    resumo["lidos"] = len(arquivos)

    for caminho in arquivos:
        try:
            payload = _carregar_json(caminho)
        except Exception as exc:
            resumo["erros"] += 1
            resumo["detalhes_erros"].append(f"{caminho.name}:{exc}")
            logger.exception("Falha ao ler JSON: %s", caminho.name)
            continue

        ok, motivo = validar_payload_placa(payload)
        if not ok:
            resumo["erros"] += 1
            resumo["detalhes_erros"].append(f"{caminho.name}:{motivo}")
            logger.error("Payload inválido %s: %s", caminho.name, motivo)
            continue

        resumo["validos"] += 1
        codigo = str(payload["codigo_motor"]).strip()
        motor = buscar_motor_por_codigo(codigo)
        if not motor:
            resumo["ignorados"] += 1
            logger.error("Motor não cadastrado para placa: %s", codigo)
            continue

        try:
            op = upsert_dados_placa(
                int(motor["id"]),
                payload,
                caminho.name,
                origem_evento="pipeline_placa_json",
            )
        except Exception as exc:
            resumo["erros"] += 1
            resumo["detalhes_erros"].append(f"{caminho.name}:{exc}")
            logger.exception("Falha ao persistir placa: %s", caminho.name)
            continue

        if op == "criado":
            resumo["criados"] += 1
        else:
            resumo["atualizados"] += 1

        if arquivar:
            carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
            destino = PROCESSED_PLACAS_DIR / f"{caminho.stem}_{carimbo}{caminho.suffix}"
            shutil.move(str(caminho), str(destino))
            logger.info("Placa arquivada: %s -> %s", caminho.name, destino.name)

    return resumo

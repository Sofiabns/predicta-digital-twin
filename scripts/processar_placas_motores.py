"""Entry point: pipeline de dados técnicos da placa (OCR simulado → JSON) — CS02."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.cadastro_ativo.placa_pipeline import RAW_PLACAS_DIR, executar_pipeline_placas  # noqa: E402
from src.coleta.logger_config import LOG_DIR, configurar_logger  # noqa: E402


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    configurar_logger("rpa-cs02.placa")
    RAW_PLACAS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("RPA CS02 — Processamento de placas (JSON estruturado)")
    print("=" * 60)

    resumo = executar_pipeline_placas(arquivar=True)

    print(f"\nDiretório: {resumo['diretorio']}")
    print(f"Arquivos lidos:     {resumo['lidos']}")
    print(f"Registros válidos:  {resumo['validos']}")
    print(f"Criados:            {resumo['criados']}")
    print(f"Atualizados:        {resumo['atualizados']}")
    print(f"Ignorados:         {resumo['ignorados']}")
    print(f"Erros:             {resumo['erros']}")
    if resumo["detalhes_erros"]:
        print("\nDetalhes:")
        for e in resumo["detalhes_erros"][:30]:
            print(f"  - {e}")
    print("=" * 60)

    logging.shutdown()
    return 0 if resumo["erros"] == 0 or resumo["validos"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

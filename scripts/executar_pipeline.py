"""Entry point manual: executa o pipeline ETL sobre data/raw/."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o src/ seja importável quando rodar via `python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.coleta.logger_config import configurar_logger  # noqa: E402
from src.coleta.pipeline import executar_pipeline  # noqa: E402
from src.persistencia.leitura_repository import contar_leituras  # noqa: E402


def main() -> int:
    logger = configurar_logger("rpa-cs01.coleta")

    print("=" * 60)
    print("PIPELINE DE COLETA - RPA-CS01 Predicta")
    print("=" * 60)

    total_antes = contar_leituras()
    print(f"\n[INFO] Leituras no banco antes do pipeline: {total_antes}\n")

    resultados = executar_pipeline(arquivar=True)

    if not resultados:
        print("\n[AVISO] Nenhum arquivo processado.")
        return 1

    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO POR ARQUIVO")
    print("=" * 60)
    print(f"{'Arquivo':<35} {'Motor':<10} {'Inseridas':>10} {'Status':>15}")
    print("-" * 75)

    total_inseridas = 0
    for r in resultados:
        print(
            f"{r['arquivo']:<35} "
            f"{(r['motor'] or '-'):<10} "
            f"{r['inseridas']:>10} "
            f"{r['status']:>15}"
        )
        total_inseridas += r["inseridas"]

    total_depois = contar_leituras()
    print("-" * 75)
    print(f"\n[OK] Total de leituras inseridas neste run: {total_inseridas}")
    print(f"[OK] Total de leituras no banco agora:      {total_depois}")
    print("=" * 60)

    return 0 if any(r["status"] == "ok" for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())

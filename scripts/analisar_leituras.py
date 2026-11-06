"""Executa a analise de leituras nao processadas e persiste anomalias.

Uso:
    python scripts/analisar_leituras.py
    python scripts/analisar_leituras.py --limite 100
    python scripts/analisar_leituras.py --reset
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analise.analisador import executar_analise
from src.persistencia.database import get_connection


def configurar_logging() -> None:
    """Configura logging com saida no console + arquivo."""
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "analise.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def reset_processamento() -> None:
    """Reseta processado=0 em todas as leituras e limpa anomalias."""
    with get_connection() as conn:
        conn.execute("UPDATE leituras SET processado = 0")
        conn.execute("DELETE FROM anomalias")
    print("[OK] Reset realizado: processado=0 em todas leituras + anomalias apagadas.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analisa leituras e detecta anomalias")
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Limite de leituras a processar (default: todas)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reseta processado=0 e apaga anomalias antes de rodar",
    )
    args = parser.parse_args()

    configurar_logging()

    if args.reset:
        reset_processamento()

    relatorio = executar_analise(limite=args.limite)

    print("\n" + "=" * 60)
    print("RELATORIO DE ANALISE")
    print("=" * 60)
    print(relatorio.resumo())
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

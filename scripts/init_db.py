"""
Script de inicialização do banco de dados.

Executa o schema.sql e exibe estatísticas do banco.

Uso:
    python scripts/init_db.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.persistencia.database import check_database, get_db_path, init_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    print("=" * 60)
    print("RPA-CS01 Predicta - Inicializacao do Banco de Dados")
    print("=" * 60)

    db_path = get_db_path()
    print(f"\n[INFO] Caminho do banco: {db_path}")

    try:
        init_database()
        print("[OK] Schema aplicado com sucesso!\n")

        stats = check_database()
        print("Estatisticas do banco:")
        print("-" * 40)
        for tabela, total in stats.items():
            print(f"  {tabela:15s} {total:>6} registros")
        print("-" * 40)
        print("\n[OK] Banco pronto para uso!")

    except Exception as exc:
        logger.error("Falha ao inicializar banco: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Script de entrada para iniciar o dashboard Predicta."""

import sys
from pathlib import Path

# Adiciona raiz do projeto ao PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.dashboard.app import main

if __name__ == "__main__":
    main()

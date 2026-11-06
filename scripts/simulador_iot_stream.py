"""Simulador contínuo de sensores IoT + pipeline RPA integrado.

Mantido por compatibilidade com as sprints anteriores (run_unix.sh, Docker).
Agora delega ao orquestrador da Sprint 4, que executa coleta, análise,
avaliação dos ativos, recomendação, rastreabilidade e contexto do assistente.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.integracao.config import Config  # noqa: E402
from src.integracao.orquestrador import Orquestrador  # noqa: E402
from src.integracao.simulador import SimuladorTelemetria  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    cfg = Config.carregar()
    sim = SimuladorTelemetria(cfg.raw_dir, modo="aleatorio")
    print("Simulador IoT + RPA integrado em execução. Ctrl+C para encerrar.")
    Orquestrador(cfg, modo="continuo", simulador=sim).executar(None)


if __name__ == "__main__":
    main()

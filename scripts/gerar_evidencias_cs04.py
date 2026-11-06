"""Regera a pasta de evidências a partir do banco e do log atuais."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.integracao.config import Config  # noqa: E402
from src.integracao.evidencias import gerar_evidencias  # noqa: E402


def main() -> int:
    cfg = Config.carregar()
    log = cfg.logs_dir / "rpa_integrado.jsonl"
    destino = gerar_evidencias(cfg, log if log.exists() else None)
    print(f"Evidências geradas em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

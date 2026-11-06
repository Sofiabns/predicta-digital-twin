"""Valida a integridade da execução integrada da Sprint 4 (banco + log estruturado)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.integracao.config import Config  # noqa: E402
from src.integracao.validacao import validar_integridade  # noqa: E402


def main() -> int:
    cfg = Config.carregar()
    log = cfg.evidencias_dir / "logs" / "execucao.jsonl"
    if not log.exists():
        log = cfg.logs_dir / "rpa_integrado.jsonl"
    print("=" * 64)
    print("VALIDAÇÃO DA SPRINT 4 - INTEGRAÇÃO PONTA A PONTA")
    print("=" * 64)
    falhas = 0
    for nome, ok, detalhe in validar_integridade(log if log.exists() else None):
        print(f"[{'OK' if ok else 'FALHA'}] {nome} - {detalhe}")
        falhas += 0 if ok else 1
    print("=" * 64)
    print("RESULTADO:", "tudo certo" if not falhas else f"{falhas} verificação(ões) com falha")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

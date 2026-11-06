"""Ponto de entrada do pipeline RPA integrado (Sprint 4).

Exemplos:
    python scripts/executar_rpa_integrado.py --demo
    python scripts/executar_rpa_integrado.py --unico
    python scripts/executar_rpa_integrado.py --continuo --simular --intervalo 20
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.integracao.config import Config  # noqa: E402
from src.integracao.orquestrador import Orquestrador  # noqa: E402
from src.integracao.simulador import SimuladorTelemetria  # noqa: E402


def _tabela(resultados) -> None:
    print("\nCiclo  Status    Etapas com ressalva")
    print("-" * 60)
    for r in resultados:
        prob = ", ".join(f"{e.nome}:{e.status}" for e in r.etapas if e.status != "ok") or "-"
        print(f"{r.ciclo:>5}  {r.status:<8}  {prob}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline RPA integrado - Predicta (Sprint 4)")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--demo", action="store_true", help="demonstração completa e reproduzível (reinicia o banco)")
    modo.add_argument("--unico", action="store_true", help="executa um único ciclo com os dados já presentes")
    modo.add_argument("--continuo", action="store_true", help="executa ciclos até receber Ctrl+C")
    ap.add_argument("--simular", action="store_true", help="gera telemetria simulada a cada ciclo")
    ap.add_argument("--ciclos", type=int, default=14, help="número de ciclos (demo) ou limite (contínuo)")
    ap.add_argument("--intervalo", type=float, default=None, help="segundos entre ciclos")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--sem-falhas", action="store_true", help="na demo, não injeta falhas de teste")
    ap.add_argument("--sem-llm", action="store_true", help="não tenta usar o Ollama")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
    for ruidoso in ("src.analise.analisador", "src.coleta", "src.persistencia", "src.cadastro_ativo"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    if args.sem_llm:
        os.environ["PREDICTA_USAR_LLM"] = "nao"

    if args.demo or not (args.unico or args.continuo):
        from src.integracao.demo import executar_demo
        print("Demonstração: o banco local será recriado. Evidências em", Config.carregar().evidencias_dir)
        r = executar_demo(ciclos=args.ciclos, intervalo=args.intervalo or 0.0, semente=args.semente,
                          injetar_falhas=not args.sem_falhas)
        _tabela(r["ciclos"])
        print(f"\nEvidências geradas em: {r['evidencias']}\nLog estruturado: {r['log']}")
        return 0

    cfg = Config.carregar()
    sim = SimuladorTelemetria(cfg.raw_dir, modo="aleatorio", semente=args.semente) if args.simular else None
    orq = Orquestrador(cfg, modo="continuo" if args.continuo else "unico", simulador=sim)
    if args.unico:
        _tabela([orq.executar_ciclo(1)])
        return 0
    print("Modo contínuo iniciado. Pressione Ctrl+C para encerrar após o ciclo atual.")
    _tabela(orq.executar(None if args.ciclos == 14 else args.ciclos, args.intervalo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

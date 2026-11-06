"""Script de limpeza do banco Predicta.

Remove duplicatas de anomalias e opcionalmente zera todas as
anomalias/leituras para um novo ciclo de testes.

Uso:
    python scripts/limpar_banco.py                 # modo interativo
    python scripts/limpar_banco.py --dedup         # só remove duplicatas
    python scripts/limpar_banco.py --reset-all     # apaga TUDO (leituras+anomalias)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.persistencia.database import get_connection  # noqa: E402


def contar(conn, tabela: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def remover_duplicatas_anomalias(conn) -> int:
    """Remove anomalias duplicadas, mantendo apenas 1 por (motor, tipo, timestamp, severidade)."""
    antes = contar(conn, "anomalias")
    print(f"  📊 Anomalias antes: {antes:,}".replace(",", "."))

    # Mantém só o MENOR id de cada grupo duplicado
    sql_dedup = """
        DELETE FROM anomalias
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM anomalias
            GROUP BY motor_id, tipo, detectado_em, severidade
        )
    """
    cur = conn.execute(sql_dedup)
    conn.commit()

    depois = contar(conn, "anomalias")
    removidas = antes - depois
    print(f"  ✅ Anomalias depois: {depois:,}".replace(",", "."))
    print(f"  🗑️  Duplicatas removidas: {removidas:,}".replace(",", "."))
    return removidas


def reset_total(conn) -> None:
    """Apaga TODAS as leituras e anomalias (NAO apaga motores)."""
    print("  🗑️  Apagando anomalias...")
    conn.execute("DELETE FROM anomalias")

    print("  🗑️  Apagando leituras...")
    conn.execute("DELETE FROM leituras")

    print("  🗑️  Apagando manutencoes pendentes...")
    try:
        conn.execute("DELETE FROM manutencoes WHERE status = 'pendente'")
    except Exception:
        pass

    conn.commit()
    print("  ✅ Reset completo! Motores preservados.")


def menu_interativo() -> str:
    print("\n  Escolha uma operação:")
    print("    1 → Remover APENAS duplicatas de anomalias (seguro)")
    print("    2 → RESET TOTAL: apaga todas leituras + anomalias")
    print("    0 → Cancelar")
    return input("\n  Opção: ").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpeza do banco Predicta")
    parser.add_argument("--dedup", action="store_true",
                        help="Remove apenas duplicatas")
    parser.add_argument("--reset-all", action="store_true",
                        help="Apaga todas leituras e anomalias")
    args = parser.parse_args()

    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "  🧹 LIMPEZA DO BANCO PREDICTA".ljust(68) + "║")
    print("╚" + "═" * 68 + "╝")

    # Modo de operação
    if args.dedup:
        modo = "1"
    elif args.reset_all:
        modo = "2"
    else:
        modo = menu_interativo()

    if modo == "0":
        print("\n  ❌ Operação cancelada.")
        return

    with get_connection() as conn:
        print()
        if modo == "1":
            print("=" * 70)
            print("  🔍 REMOVENDO DUPLICATAS")
            print("=" * 70)
            remover_duplicatas_anomalias(conn)

        elif modo == "2":
            print("=" * 70)
            print("  ⚠️  RESET TOTAL")
            print("=" * 70)
            if not args.reset_all:
                confirma = input(
                    "\n  ⚠️  Tem certeza? Vai apagar TODAS leituras+anomalias. (sim/NAO): "
                ).strip().lower()
                if confirma != "sim":
                    print("  ❌ Operação cancelada.")
                    return
            reset_total(conn)

        else:
            print(f"  ❌ Opção inválida: {modo}")
            return

        # Resumo final
        print()
        print("=" * 70)
        print("  📊 ESTADO FINAL")
        print("=" * 70)
        print(f"  🏭 Motores:   {contar(conn, 'motores'):>8}")
        print(f"  📈 Leituras:  {contar(conn, 'leituras'):>8}")
        print(f"  🚨 Anomalias: {contar(conn, 'anomalias'):>8}")
        print()


if __name__ == "__main__":
    main()

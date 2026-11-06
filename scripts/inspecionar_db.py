"""Inspeciona o banco e mostra exemplos de leituras por classe."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Garante que o src/ seja importável
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "motores.db"


def exemplo_por_classe(conn: sqlite3.Connection, classe: str) -> None:
    """Imprime um exemplo de leitura da classe informada."""
    print("\n" + "=" * 60)
    print(f"EXEMPLO: Leitura {classe.upper()}")
    print("=" * 60)

    row = conn.execute(
        "SELECT * FROM leituras WHERE classe_origem = ? LIMIT 1",
        (classe,),
    ).fetchone()

    if row:
        print(json.dumps(dict(row), indent=2, ensure_ascii=False))
    else:
        print(f"[AVISO] Nenhuma leitura encontrada para classe '{classe}'")


def estatisticas_por_classe(conn: sqlite3.Connection) -> None:
    """Mostra min/max/avg de cada métrica agrupado por classe."""
    print("\n" + "=" * 60)
    print("ESTATISTICAS POR CLASSE")
    print("=" * 60)

    sql = """
        SELECT
            classe_origem,
            COUNT(*)              AS total,
            ROUND(AVG(temperatura), 2) AS temp_avg,
            ROUND(MIN(temperatura), 2) AS temp_min,
            ROUND(MAX(temperatura), 2) AS temp_max,
            ROUND(AVG(vibracao), 2)    AS vib_avg,
            ROUND(MIN(vibracao), 2)    AS vib_min,
            ROUND(MAX(vibracao), 2)    AS vib_max,
            ROUND(AVG(corrente), 2)    AS cor_avg,
            ROUND(AVG(rpm), 2)         AS rpm_avg,
            ROUND(AVG(tensao), 2)      AS ten_avg
        FROM leituras
        GROUP BY classe_origem
        ORDER BY
            CASE classe_origem
                WHEN 'normal' THEN 1
                WHEN 'alerta' THEN 2
                WHEN 'critico' THEN 3
                ELSE 4
            END
    """

    rows = conn.execute(sql).fetchall()
    for row in rows:
        d = dict(row)
        print(f"\n  Classe: {d['classe_origem']:<10} | Total: {d['total']}")
        print(f"    Temperatura : avg={d['temp_avg']:>8} | min={d['temp_min']:>8} | max={d['temp_max']:>8}")
        print(f"    Vibracao    : avg={d['vib_avg']:>8} | min={d['vib_min']:>8} | max={d['vib_max']:>8}")
        print(f"    Corrente avg: {d['cor_avg']:>8}")
        print(f"    RPM avg     : {d['rpm_avg']:>8}")
        print(f"    Tensao avg  : {d['ten_avg']:>8}")


def cruzamento_label_classe(conn: sqlite3.Connection) -> None:
    """Mostra cruzamento entre label_origem e classe_origem."""
    print("\n" + "=" * 60)
    print("CRUZAMENTO: label_origem x classe_origem")
    print("=" * 60)

    sql = """
        SELECT label_origem, classe_origem, COUNT(*) AS total
        FROM leituras
        GROUP BY label_origem, classe_origem
        ORDER BY label_origem, classe_origem
    """
    print(f"\n  {'label':<8} {'classe':<12} {'total':>8}")
    print(f"  {'-'*8} {'-'*12} {'-'*8}")
    for row in conn.execute(sql):
        d = dict(row)
        print(f"  {str(d['label_origem']):<8} {d['classe_origem']:<12} {d['total']:>8}")


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERRO] Banco nao encontrado: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print("INSPECAO DO BANCO DE DADOS - RPA-CS01")
    print("=" * 60)
    print(f"Banco: {DB_PATH}")

    # Exemplos por classe
    for classe in ("normal", "alerta", "critico"):
        exemplo_por_classe(conn, classe)

    # Estatisticas
    estatisticas_por_classe(conn)

    # Cruzamento
    cruzamento_label_classe(conn)

    print("\n" + "=" * 60)
    print("INSPECAO FINALIZADA")
    print("=" * 60)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

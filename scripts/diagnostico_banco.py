"""Script de diagnostico do banco de dados Predicta.

Investiga inconsistencias nos dados (anomalias duplicadas,
contagens, integridade referencial) e sugere correcoes.

Uso:
    python scripts/diagnostico_banco.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o src/ esta no PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.persistencia.database import get_connection  # noqa: E402


# ============================================================
# Helpers de formatacao
# ============================================================
def header(titulo: str, char: str = "=") -> None:
    print()
    print(char * 70)
    print(f"  {titulo}")
    print(char * 70)


def linha(label: str, valor, sufixo: str = "") -> None:
    print(f"  {label:<45} {valor}{sufixo}")


def fetch_one(conn, sql: str, params: tuple = ()) -> int | None:
    """Executa SQL e retorna o primeiro valor da primeira linha."""
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def fetch_all(conn, sql: str, params: tuple = ()) -> list[tuple]:
    """Executa SQL e retorna todas as linhas."""
    return conn.execute(sql, params).fetchall()


# ============================================================
# Diagnosticos
# ============================================================
def diag_contagens_basicas(conn) -> dict[str, int]:
    """Contagens fundamentais das tabelas."""
    header("📊 CONTAGENS BÁSICAS")

    total_motores = fetch_one(conn, "SELECT COUNT(*) FROM motores") or 0
    motores_ativos = fetch_one(
        conn, "SELECT COUNT(*) FROM motores WHERE status = 'ativo'"
    ) or 0
    total_leituras = fetch_one(conn, "SELECT COUNT(*) FROM leituras") or 0
    total_anomalias = fetch_one(conn, "SELECT COUNT(*) FROM anomalias") or 0

    linha("🏭 Total de motores:", total_motores)
    linha("⚡ Motores ativos:", motores_ativos)
    linha("📈 Total de leituras:", f"{total_leituras:,}".replace(",", "."))
    linha("🚨 Total de anomalias:", f"{total_anomalias:,}".replace(",", "."))

    return {
        "motores": total_motores,
        "motores_ativos": motores_ativos,
        "leituras": total_leituras,
        "anomalias": total_anomalias,
    }


def diag_anomalias_detalhado(conn, totais: dict) -> dict:
    """Investiga anomalias em detalhe (duplicacao, leituras unicas)."""
    header("🔬 ANÁLISE DE ANOMALIAS")

    # Verifica se existe coluna leitura_id ou id_leitura
    leituras_com_anomalia = None
    coluna_fk = None
    for col_candidata in ("leitura_id", "id_leitura"):
        try:
            leituras_com_anomalia = fetch_one(
                conn, f"SELECT COUNT(DISTINCT {col_candidata}) FROM anomalias"
            )
            coluna_fk = col_candidata
            break
        except Exception:
            continue

    if coluna_fk:
        linha(f"🔗 Coluna FK detectada:", coluna_fk)
        linha("📌 Leituras únicas com anomalia:", leituras_com_anomalia or 0)

        if totais["leituras"] > 0 and leituras_com_anomalia:
            pct = (leituras_com_anomalia / totais["leituras"]) * 100
            linha("📊 % leituras afetadas:", f"{pct:.2f}%")

        if totais["anomalias"] > 0 and leituras_com_anomalia:
            ratio = totais["anomalias"] / leituras_com_anomalia
            linha("⚠️ Anomalias por leitura (média):", f"{ratio:.2f}")
            if ratio > 1:
                print()
                print(f"  💡 Cada leitura gera ~{ratio:.1f} anomalias em média.")
                print(f"     Isso explica por que anomalias ({totais['anomalias']}) ")
                print(f"     > leituras ({totais['leituras']}).")
    else:
        print("  ⚠️ Não foi possível identificar coluna FK em anomalias")
        print("     (procurei por 'leitura_id' e 'id_leitura')")

    # Por severidade
    print()
    print("  📊 Distribuição por severidade:")
    rows = fetch_all(
        conn,
        "SELECT severidade, COUNT(*) FROM anomalias GROUP BY severidade",
    )
    for sev, qtd in rows:
        linha(f"     {sev}:", qtd)

    # Por tipo
    print()
    print("  📊 Distribuição por tipo:")
    rows = fetch_all(
        conn,
        "SELECT tipo, COUNT(*) FROM anomalias GROUP BY tipo ORDER BY 2 DESC",
    )
    for tipo, qtd in rows:
        linha(f"     {tipo}:", qtd)

    return {
        "leituras_com_anomalia": leituras_com_anomalia,
        "coluna_fk": coluna_fk,
    }


def diag_taxa_saude(conn, totais: dict, anom_info: dict) -> None:
    """Calcula a taxa de saude com diferentes formulas."""
    header("💚 TAXA DE SAÚDE — COMPARAÇÃO DE FÓRMULAS")

    leituras = totais["leituras"]
    anomalias = totais["anomalias"]
    leituras_unicas = anom_info.get("leituras_com_anomalia") or 0

    if leituras == 0:
        print("  ⚠️ Sem leituras — não é possível calcular.")
        return

    # Fórmula atual (BUGADA)
    taxa_atual = round(((leituras - anomalias) / leituras) * 100, 2)
    linha("❌ Fórmula ATUAL (bugada):", f"{taxa_atual}%")

    # Fórmula corrigida com clamp
    taxa_clamp = max(0.0, min(100.0, taxa_atual))
    linha("⚠️ Com clamp [0-100]:", f"{taxa_clamp}%")

    # Fórmula correta — leituras únicas
    if leituras_unicas:
        taxa_correta = round(
            ((leituras - leituras_unicas) / leituras) * 100, 2
        )
        linha("✅ Por leituras únicas (RECOMENDADA):", f"{taxa_correta}%")

    print()
    print("  💡 RECOMENDAÇÃO: usar leituras únicas com anomalia,")
    print("     pois uma leitura pode gerar múltiplas anomalias")
    print("     (ex.: temperatura + vibração na mesma amostra).")


def diag_motores(conn) -> None:
    """Lista motores e suas anomalias."""
    header("🏭 MOTORES CADASTRADOS")

    sql = """
        SELECT
            m.codigo,
            m.status,
            COUNT(DISTINCT l.id) AS leituras,
            COUNT(a.id) AS anomalias
        FROM motores m
        LEFT JOIN leituras l ON l.motor_id = m.id
        LEFT JOIN anomalias a ON a.motor_id = m.id
        GROUP BY m.id, m.codigo, m.status
        ORDER BY m.codigo
    """
    try:
        rows = fetch_all(conn, sql)
        if not rows:
            print("  ⚠️ Nenhum motor cadastrado!")
            return

        print(f"  {'CÓDIGO':<12} {'STATUS':<12} {'LEITURAS':>10} {'ANOMALIAS':>12}")
        print(f"  {'-' * 50}")
        for codigo, status, leituras, anomalias in rows:
            print(
                f"  {codigo:<12} {status:<12} "
                f"{leituras:>10} {anomalias:>12}"
            )
    except Exception as e:
        print(f"  ❌ Erro ao consultar motores: {e}")


def diag_duplicatas(conn) -> None:
    """Detecta possiveis duplicatas em anomalias."""
    header("🔍 DETECÇÃO DE DUPLICATAS")

    # Tenta detectar pela combinação motor + tipo + timestamp
    sql_dup = """
        SELECT motor_id, tipo, detectado_em, COUNT(*) AS qtd
        FROM anomalias
        GROUP BY motor_id, tipo, detectado_em
        HAVING COUNT(*) > 1
        ORDER BY qtd DESC
        LIMIT 10
    """
    try:
        rows = fetch_all(conn, sql_dup)
        if not rows:
            print("  ✅ Nenhuma duplicata detectada (motor + tipo + timestamp)")
        else:
            print(f"  ⚠️ {len(rows)} grupos com duplicatas (mostrando top 10):")
            for motor_id, tipo, ts, qtd in rows:
                print(f"     motor={motor_id} tipo={tipo} ts={ts} → {qtd}x")
    except Exception as e:
        print(f"  ⚠️ Não foi possível verificar: {e}")


def diag_integridade(conn) -> None:
    """Verifica integridade referencial."""
    header("🔗 INTEGRIDADE REFERENCIAL")

    # Anomalias órfãs (sem motor)
    try:
        orfas_motor = fetch_one(
            conn,
            """
            SELECT COUNT(*) FROM anomalias a
            LEFT JOIN motores m ON m.id = a.motor_id
            WHERE m.id IS NULL
            """,
        ) or 0
        status = "✅" if orfas_motor == 0 else "❌"
        linha(f"{status} Anomalias sem motor válido:", orfas_motor)
    except Exception as e:
        print(f"  ⚠️ Erro ao verificar órfãs: {e}")

    # Leituras órfãs
    try:
        orfas_leitura = fetch_one(
            conn,
            """
            SELECT COUNT(*) FROM leituras l
            LEFT JOIN motores m ON m.id = l.motor_id
            WHERE m.id IS NULL
            """,
        ) or 0
        status = "✅" if orfas_leitura == 0 else "❌"
        linha(f"{status} Leituras sem motor válido:", orfas_leitura)
    except Exception as e:
        print(f"  ⚠️ Erro ao verificar leituras órfãs: {e}")


# ============================================================
# Main
# ============================================================
def main() -> None:
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "  🔬 DIAGNÓSTICO DO BANCO PREDICTA".ljust(68) + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        with get_connection() as conn:
            totais = diag_contagens_basicas(conn)
            anom_info = diag_anomalias_detalhado(conn, totais)
            diag_taxa_saude(conn, totais, anom_info)
            diag_motores(conn)
            diag_duplicatas(conn)
            diag_integridade(conn)

        header("✅ DIAGNÓSTICO CONCLUÍDO", char="=")
        print()
        print("  📋 PRÓXIMOS PASSOS SUGERIDOS:")
        print("     1. Se taxa de saúde < 0  → corrigir fórmula em obter_kpis()")
        print("     2. Se há duplicatas       → investigar pipeline de detecção")
        print("     3. Se só tem 1 motor      → rodar seed completo da frota")
        print()

    except Exception as e:
        print(f"\n❌ ERRO durante diagnóstico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

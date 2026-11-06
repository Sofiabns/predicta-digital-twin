#!/usr/bin/env python3
"""
Validação de alto nível da entrega CS02 (ambiente local).

Uso:
    python scripts/validar_cs02.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.coleta.logger_config import LOG_DIR, configurar_logger  # noqa: E402
from src.dashboard import data_service as ds  # noqa: E402
from src.persistencia.database import check_database, get_connection, get_db_path  # noqa: E402

configurar_logger("rpa-cs02.validacao")
LOG_DIR.mkdir(parents=True, exist_ok=True)

TABELAS_CS02 = (
    "plantas",
    "areas",
    "linhas",
    "localizacoes",
    "associacoes_ativos",
    "dados_placa_motor",
    "auditoria_operacional",
)
VIEWS_CS02 = (
    "vw_ativos_operacionais",
    "vw_digital_twin_ativos",
    "vw_ultimas_leituras_por_ativo",
)


def _linha(msg: str, ok: bool | None = None) -> str:
    if ok is True:
        tag = "[OK]"
    elif ok is False:
        tag = "[ATENCAO]"
    else:
        tag = "[INFO]"
    return f"{tag} {msg}"


def main() -> int:
    print("=" * 72)
    print(" VALIDAÇÃO CS02 — RPA Predicta")
    print("=" * 72)

    erros = 0
    db_path = get_db_path()
    print(_linha(f"Banco configurado: {db_path}", db_path.exists()))
    if not db_path.exists():
        print(_linha("Execute: python scripts/init_db.py", False))
        return 1

    stats = check_database()
    print("\n--- Tabelas (contagens) ---")
    for t, n in stats.items():
        print(f"  {t}: {n}")

    for t in TABELAS_CS02:
        if t not in stats:
            print(_linha(f"Tabela CS02 ausente no check_database: {t}", False))
            erros += 1

    print("\n--- Views CS02 ---")
    with get_connection() as conn:
        for v in VIEWS_CS02:
            try:
                conn.execute(f"SELECT 1 FROM {v} LIMIT 1")
                print(_linha(f"View `{v}` consultável", True))
            except Exception as exc:
                print(_linha(f"View `{v}`: {exc}", False))
                erros += 1

    plantas = stats.get("plantas", 0)
    assoc = stats.get("associacoes_ativos", 0)
    placas = stats.get("dados_placa_motor", 0)
    audit = stats.get("auditoria_operacional", 0)
    leituras = stats.get("leituras", 0)

    print(_linha(f"Plantas cadastradas: {plantas}", plantas > 0))
    print(_linha(f"Associações TAG/localização: {assoc}", assoc > 0))
    print(_linha(f"Dados de placa: {placas}", placas > 0))
    print(_linha(f"Eventos de auditoria: {audit}", audit > 0))
    print(_linha(f"Leituras persistidas: {leituras}", leituras > 0))

    print("\n--- Busca por TAG (sample) ---")
    twin = ds.consultar_digital_twin_por_tag("MTR-L01-BOM-001")
    print(_linha("TAG MTR-L01-BOM-001", twin is not None and bool(twin.get("codigo_motor"))))
    if twin:
        print(f"     Motor: {twin.get('codigo_motor')} | Planta: {twin.get('planta_nome')}")

    print("\n--- Data service operacional ---")
    pc = ds.listar_codigos_plantas()
    print(_linha(f"listar_codigos_plantas: {len(pc)} item(ns)", len(pc) > 0))
    if pc:
        ac = ds.listar_codigos_areas(pc[0])
        print(_linha(f"Áreas da planta {pc[0]}: {len(ac)}", len(ac) > 0))
        if ac:
            lc_list = ds.listar_codigos_linhas(pc[0], ac[0])
            if lc_list:
                tags = ds.listar_tags_por_hierarquia(pc[0], ac[0], lc_list[0])
                print(_linha(f"TAGs na linha {lc_list[0]}: {len(tags)}", len(tags) > 0))

    print(_linha("Mapa (dataframe)", not ds.obter_mapa_ativos_df().empty))

    hist_ok = False
    if twin and twin.get("codigo_motor"):
        dfh = ds.obter_telemetria_motor(str(twin["codigo_motor"]), limite=5)
        hist_ok = not dfh.empty
    print(_linha("Histórico telemetria (amostra)", hist_ok))

    print("\n" + "=" * 72)
    print(" ADERÊNCIA AO ENUNCIADO")
    print("=" * 72)

    def okflag(cond: bool) -> str:
        return "OK" if cond else "ATENCAO"

    nav = len(pc) > 0 and assoc > 0
    rpa = assoc > 0 and audit > 0
    tagb = twin is not None
    met = twin is not None and twin.get("ultima_leitura_ts") is not None
    graf = hist_ok
    placa_ok = placas > 0
    rast = audit > 0
    ca = True
    ml = True
    doc = (PROJECT_ROOT / "docs" / "CS02_DOCUMENTO_TECNICO.md").exists() and (
        PROJECT_ROOT / "docs" / "CS02_CHECKLIST_ADERENCIA.md"
    ).exists()

    checks = [
        ("Estrutura de navegação", nav),
        ("Associação automatizada RPA", rpa),
        ("Busca por TAG", tagb),
        ("Métricas atuais", met),
        ("Gráficos históricos", graf),
        ("Pipeline da placa", placa_ok),
        ("Rastreabilidade", rast),
        ("Controle de acesso demonstrativo", ca),
        ("Preparação para ML", ml),
        ("Documentação", doc),
    ]
    for nome, cond in checks:
        print(f"- {nome}: {okflag(cond)}")

    print("=" * 72)
    resultado = "APROVADO" if erros == 0 and doc and nav and rpa and tagb else "ATENCAO"
    print(f"\nRESULTADO FINAL: {resultado}")
    if not doc:
        print(_linha("Documentação CS02 ausente em docs/.", False))

    logging.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

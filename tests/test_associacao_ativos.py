"""Testes do RPA de associação Ativo/TAG/Localização (CS02)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.cadastro_ativo.ativo_association_pipeline import executar_associacao_ativos
from src.cadastro_ativo.ativo_validator import validar_linha_cadastro
from src.persistencia.database import get_connection, init_database
from src.persistencia.motor_repository import buscar_motor_por_codigo, inserir_motor


def _seed_motores() -> None:
    motores = [
        ("MTR-001", "M1", "Loc1", "WEG", 15.0),
        ("MTR-002", "M2", "Loc2", "WEG", 11.0),
        ("MTR-003", "M3", "Loc3", "WEG", 18.5),
        ("MTR-004", "M4", "Loc4", "WEG", 7.5),
        ("MTR-005", "M5", "Loc5", "WEG", 5.5),
    ]
    for cod, modelo, loc, fab, pot in motores:
        if not buscar_motor_por_codigo(cod):
            inserir_motor(cod, modelo, loc, fabricante=fab, potencia_kw=pot)


def _csv_padrao() -> str:
    return textwrap.dedent(
        """
        codigo_motor,tag,planta_codigo,planta_nome,area_codigo,area_nome,linha_codigo,linha_nome,localizacao_codigo,localizacao_descricao,coordenada_x,coordenada_y,status_operacional
        MTR-001,TAG-TEST-001,PLT-T,Planta Teste,AR-T,Area Teste,LN-T,Linha Teste,LC-T,Loc teste,1,2,operacional
        MTR-002,TAG-TEST-002,PLT-T,Planta Teste,AR-T,Area Teste,LN-T,Linha Teste,LC-T2,Loc2,3,4,atencao
        """
    ).strip()


@pytest.fixture()
def db_tmp(monkeypatch, tmp_path: Path):
    dbfile = tmp_path / "test_cs02.db"
    monkeypatch.setenv("DATABASE_PATH", str(dbfile))
    init_database(dbfile)
    _seed_motores()
    return dbfile


def test_validador_campo_obrigatorio():
    ok, msg = validar_linha_cadastro({"codigo_motor": "X"})
    assert ok is False
    assert msg and "campo_obrigatorio" in msg


def test_pipeline_cria_hierarquia_e_associacao(db_tmp, tmp_path: Path):
    p = tmp_path / "cad.csv"
    p.write_text(_csv_padrao(), encoding="utf-8")
    r = executar_associacao_ativos(p, arquivar=False)
    assert r["validos"] == 2
    assert r["criados"] == 2

    with get_connection() as conn:
        n_plantas = conn.execute("SELECT COUNT(*) AS c FROM plantas").fetchone()["c"]
        n_assoc = conn.execute("SELECT COUNT(*) AS c FROM associacoes_ativos").fetchone()["c"]
    assert n_plantas >= 1
    assert n_assoc == 2


def test_pipeline_idempotente(db_tmp, tmp_path: Path):
    p = tmp_path / "cad.csv"
    p.write_text(_csv_padrao(), encoding="utf-8")
    r1 = executar_associacao_ativos(p, arquivar=False)
    r2 = executar_associacao_ativos(p, arquivar=False)
    assert r1["criados"] == 2
    assert r2["inalterados"] == 2
    with get_connection() as conn:
        n_assoc = conn.execute("SELECT COUNT(*) AS c FROM associacoes_ativos").fetchone()["c"]
    assert n_assoc == 2


def test_motor_inexistente_ignorado(db_tmp, tmp_path: Path):
    csv = _csv_padrao() + "\nMTR-999,TAG-X,PLT-T,Planta Teste,AR-T,Area Teste,LN-T,Linha Teste,LC-X,Loc,9,9,operacional"
    p = tmp_path / "cad2.csv"
    p.write_text(csv, encoding="utf-8")
    r = executar_associacao_ativos(p, arquivar=False)
    assert r["ignorados"] == 1
    assert r["validos"] == 3


def test_atualiza_coordenadas_localizacao(db_tmp, tmp_path: Path):
    p = tmp_path / "cad.csv"
    p.write_text(_csv_padrao(), encoding="utf-8")
    executar_associacao_ativos(p, arquivar=False)

    csv2 = textwrap.dedent(
        """
        codigo_motor,tag,planta_codigo,planta_nome,area_codigo,area_nome,linha_codigo,linha_nome,localizacao_codigo,localizacao_descricao,coordenada_x,coordenada_y,status_operacional
        MTR-001,TAG-TEST-001,PLT-T,Planta Teste,AR-T,Area Teste,LN-T,Linha Teste,LC-T,Loc teste,10,20,operacional
        MTR-002,TAG-TEST-002,PLT-T,Planta Teste,AR-T,Area Teste,LN-T,Linha Teste,LC-T2,Loc2,3,4,atencao
        """
    ).strip()
    p2 = tmp_path / "cad3.csv"
    p2.write_text(csv2, encoding="utf-8")
    executar_associacao_ativos(p2, arquivar=False)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT coordenada_x, coordenada_y FROM localizacoes WHERE codigo = 'LC-T'"
        ).fetchone()
    assert row is not None
    assert float(row["coordenada_x"]) == 10.0
    assert float(row["coordenada_y"]) == 20.0

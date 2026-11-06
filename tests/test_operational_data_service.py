"""Testes do data service operacional (CS02)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.cadastro_ativo.ativo_association_pipeline import executar_associacao_ativos
from src.dashboard import data_service as ds
from src.persistencia.database import init_database
from src.persistencia.leitura_repository import inserir_leitura
from src.persistencia.motor_repository import buscar_motor_por_codigo, inserir_motor


@pytest.fixture()
def db_ctx(monkeypatch, tmp_path: Path):
    dbf = tmp_path / "ops.db"
    monkeypatch.setenv("DATABASE_PATH", str(dbf))
    init_database(dbf)
    if not buscar_motor_por_codigo("MTR-001"):
        inserir_motor("MTR-001", "M", "L", fabricante="WEG", potencia_kw=10.0)
    csv = textwrap.dedent(
        """
        codigo_motor,tag,planta_codigo,planta_nome,area_codigo,area_nome,linha_codigo,linha_nome,localizacao_codigo,localizacao_descricao,coordenada_x,coordenada_y,status_operacional
        MTR-001,TAG-MAP,PLT-M,Planta M,AR-M,Area M,LN-M,Linha M,LC-M,Loc,5,5,operacional
        """
    ).strip()
    p = tmp_path / "cad.csv"
    p.write_text(csv, encoding="utf-8")
    executar_associacao_ativos(p, arquivar=False)
    m = buscar_motor_por_codigo("MTR-001")
    assert m is not None
    inserir_leitura(
        int(m["id"]),
        temperatura=40.0,
        vibracao=1.0,
        corrente=8.0,
        tensao=220.0,
        rpm=3000.0,
        timestamp="2026-01-15 10:00:00",
    )
    return dbf


def test_listas_hierarquia(db_ctx):
    pc = ds.listar_codigos_plantas()
    assert "PLT-M" in pc
    ac = ds.listar_codigos_areas("PLT-M")
    assert "AR-M" in ac
    lc = ds.listar_codigos_linhas("PLT-M", "AR-M")
    assert "LN-M" in lc
    tags = ds.listar_tags_por_hierarquia("PLT-M", "AR-M", "LN-M")
    assert "TAG-MAP" in tags


def test_mapa_e_ultima_leitura(db_ctx):
    twin = ds.consultar_digital_twin_por_tag("TAG-MAP")
    assert twin is not None
    assert twin.get("ultima_temperatura") is not None
    df = ds.obter_mapa_ativos_df()
    assert not df.empty
    assert "coordenada_x" in df.columns

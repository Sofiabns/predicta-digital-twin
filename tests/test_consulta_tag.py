"""Testes de consulta por TAG (CS02)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.cadastro_ativo.ativo_association_pipeline import executar_associacao_ativos
from src.dashboard import data_service as ds
from src.persistencia.database import init_database
from src.persistencia.motor_repository import buscar_motor_por_codigo, inserir_motor


def _seed():
    for cod, modelo, loc in [("MTR-001", "M", "L"), ("MTR-002", "M2", "L2")]:
        if not buscar_motor_por_codigo(cod):
            inserir_motor(cod, modelo, loc, fabricante="WEG", potencia_kw=10.0)


@pytest.fixture()
def db_populado(monkeypatch, tmp_path: Path):
    dbf = tmp_path / "tag.db"
    monkeypatch.setenv("DATABASE_PATH", str(dbf))
    init_database(dbf)
    _seed()
    csv = textwrap.dedent(
        """
        codigo_motor,tag,planta_codigo,planta_nome,area_codigo,area_nome,linha_codigo,linha_nome,localizacao_codigo,localizacao_descricao,coordenada_x,coordenada_y,status_operacional
        MTR-001,TAG-XYZ,PLT-X,Planta X,AR-X,Area X,LN-X,Linha X,LC-X,Loc,1,1,operacional
        """
    ).strip()
    p = tmp_path / "c.csv"
    p.write_text(csv, encoding="utf-8")
    executar_associacao_ativos(p, arquivar=False)
    return dbf


def test_tag_existe_retorna_contexto(db_populado):
    twin = ds.consultar_digital_twin_por_tag("TAG-XYZ")
    assert twin is not None
    assert twin["codigo_motor"] == "MTR-001"
    assert twin["planta_codigo"] == "PLT-X"
    assert twin["area_codigo"] == "AR-X"
    assert twin["linha_codigo"] == "LN-X"


def test_tag_inexistente_amigavel(db_populado):
    twin = ds.consultar_digital_twin_por_tag("NAO-EXISTE")
    assert twin is None

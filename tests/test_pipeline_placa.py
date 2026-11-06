"""Testes do pipeline de dados da placa (CS02)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cadastro_ativo.placa_pipeline import executar_pipeline_placas
from src.cadastro_ativo.placa_validator import validar_payload_placa
from src.persistencia.database import get_connection, init_database
from src.persistencia.motor_repository import buscar_motor_por_codigo, inserir_motor
from src.persistencia.placa_motor_repository import buscar_placa_por_motor_id


def _seed_um_motor() -> None:
    if not buscar_motor_por_codigo("MTR-001"):
        inserir_motor("MTR-001", "Mod", "Loc", fabricante="WEG", potencia_kw=15.0)


@pytest.fixture()
def db_tmp(monkeypatch, tmp_path: Path):
    dbfile = tmp_path / "placa_test.db"
    monkeypatch.setenv("DATABASE_PATH", str(dbfile))
    init_database(dbfile)
    _seed_um_motor()
    return dbfile


def test_validador_placa():
    ok, msg = validar_payload_placa({"codigo_motor": "MTR-001"})
    assert ok is False


def test_pipeline_placa_insere_e_confiança(db_tmp, tmp_path: Path):
    d = tmp_path / "placas"
    d.mkdir()
    payload = {
        "codigo_motor": "MTR-001",
        "fabricante": "WEG",
        "modelo": "W22",
        "numero_serie": "SN-1",
        "potencia": 15.0,
        "tensao_nominal": 380.0,
        "corrente_nominal": 28.0,
        "rpm_nominal": 3600.0,
        "frequencia": 60.0,
        "fator_servico": 1.15,
        "rendimento": 92.0,
        "origem_imagem": "img.png",
        "confianca_extracao": 0.9,
    }
    (d / "p1.json").write_text(json.dumps(payload), encoding="utf-8")

    r = executar_pipeline_placas(d, arquivar=False)
    assert r["validos"] == 1
    assert r["criados"] == 1

    m = buscar_motor_por_codigo("MTR-001")
    assert m is not None
    placa = buscar_placa_por_motor_id(int(m["id"]))
    assert placa is not None
    assert float(placa["confianca_extracao"]) == pytest.approx(0.9)


def test_motor_inexistente_ignorado(db_tmp, tmp_path: Path):
    d = tmp_path / "placas2"
    d.mkdir()
    payload = {
        "codigo_motor": "MTR-999",
        "fabricante": "WEG",
        "modelo": "W22",
        "numero_serie": "SN-X",
        "origem_imagem": "img.png",
        "confianca_extracao": 0.5,
    }
    (d / "p.json").write_text(json.dumps(payload), encoding="utf-8")
    r = executar_pipeline_placas(d, arquivar=False)
    assert r["ignorados"] == 1


def test_idempotente_atualiza(db_tmp, tmp_path: Path):
    d = tmp_path / "placas3"
    d.mkdir()
    payload = {
        "codigo_motor": "MTR-001",
        "fabricante": "WEG",
        "modelo": "W22",
        "numero_serie": "SN-1",
        "origem_imagem": "img.png",
        "confianca_extracao": 0.8,
    }
    (d / "p.json").write_text(json.dumps(payload), encoding="utf-8")
    r1 = executar_pipeline_placas(d, arquivar=False)
    (d / "p.json").write_text(json.dumps({**payload, "confianca_extracao": 0.99}), encoding="utf-8")
    r2 = executar_pipeline_placas(d, arquivar=False)
    assert r1["criados"] == 1
    assert r2["atualizados"] == 1
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM dados_placa_motor").fetchone()["c"]
    assert n == 1

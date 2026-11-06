"""Fixture compartilhada: ambiente isolado (banco e pastas em tmp_path)."""

from __future__ import annotations

import pytest

from src.analise.base_conhecimento import BaseConhecimento


@pytest.fixture()
def ambiente(monkeypatch, tmp_path):
    base = tmp_path / "data"
    pastas = {
        "PREDICTA_RAW_DIR": base / "raw",
        "PREDICTA_QUARENTENA_DIR": base / "quarentena",
        "PREDICTA_RAG_DIR": base / "rag" / "operacional",
        "PREDICTA_NOTIFICACOES_DIR": tmp_path / "logs" / "notificacoes",
        "PREDICTA_LOGS_DIR": tmp_path / "logs",
        "PREDICTA_EVIDENCIAS_DIR": tmp_path / "evidencias",
    }
    for var, caminho in pastas.items():
        caminho.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(caminho))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("PREDICTA_USAR_LLM", "nao")
    monkeypatch.setenv("PREDICTA_RAG_BACKEND", "lexical")
    # arquivos processados vão para a pasta temporária, não para o projeto
    processed = base / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("src.coleta.loader.PROCESSED_DIR", processed)
    monkeypatch.setattr("src.cadastro_ativo.ativo_loader.PROCESSED_DIR", processed)
    monkeypatch.setattr("src.cadastro_ativo.placa_pipeline.PROCESSED_PLACAS_DIR", processed / "placas_extraidas")
    # sem internet nos testes: a API de clima "falha" na hora, como em uma indisponibilidade real
    monkeypatch.setattr("src.scraping.scraper_motores.buscar_dados_climaticos",
                        lambda *a, **k: {"temperature": 25.0, "error": "sem rede (teste)"})
    BaseConhecimento.reiniciar()
    yield tmp_path
    BaseConhecimento.reiniciar()

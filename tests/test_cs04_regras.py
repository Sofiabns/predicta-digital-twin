"""Regras de negócio, limites, playbook e base de conhecimento (Sprint 4)."""

from __future__ import annotations

from src.analise.base_conhecimento import BaseConhecimento
from src.integracao.avaliacao import avaliar_leitura, zona_iso_10816
from src.integracao.config import Config
from src.integracao.limites import resolver_limites_todos
from src.integracao.migracao import garantir_schema
from src.integracao.suporte_operacional import SuporteOperacional
from src.persistencia.database import get_connection
from src.persistencia.motor_repository import inserir_motor


def test_normal_alerta_critico(ambiente):
    cfg = Config.carregar()
    ok = avaliar_leitura({"temperatura": 60, "vibracao": 1.0}, temp_max=80, vib_max=2.5, cfg=cfg)
    assert ok.severidade == "NORMAL" and not ok.desvios
    al = avaliar_leitura({"temperatura": 73, "vibracao": 1.0}, temp_max=80, vib_max=2.5, cfg=cfg)
    assert al.severidade == "ALERTA" and al.tipos == {"temperatura"}
    cr = avaliar_leitura({"temperatura": 90, "vibracao": 3.0}, temp_max=80, vib_max=2.5, cfg=cfg)
    assert cr.severidade == "CRITICO" and cr.tipos == {"temperatura", "vibracao"}


def test_limite_exato_nao_e_critico(ambiente):
    av = avaliar_leitura({"temperatura": 80, "vibracao": 2.5}, temp_max=80, vib_max=2.5, cfg=Config.carregar())
    assert av.severidade == "ALERTA"          # no limite ainda não excede


def test_corrente_e_tensao(ambiente):
    cfg = Config.carregar()
    av = avaliar_leitura({"corrente": 33.0, "tensao": 380}, temp_max=80, vib_max=2.5,
                         corrente_nominal=28.5, tensao_nominal=380, cfg=cfg)
    assert av.severidade == "CRITICO" and av.tipos == {"corrente"}
    av = avaliar_leitura({"tensao": 350}, temp_max=80, vib_max=2.5, tensao_nominal=380, cfg=cfg)
    assert av.severidade == "ALERTA" and av.tipos == {"tensao"}
    av = avaliar_leitura({"tensao": 330}, temp_max=80, vib_max=2.5, tensao_nominal=380, cfg=cfg)
    assert av.severidade == "CRITICO"
    av = avaliar_leitura({"corrente": 40, "tensao": 100}, temp_max=80, vib_max=2.5, cfg=cfg)  # sem placa: ignora
    assert av.severidade == "NORMAL"


def test_zonas_iso():
    assert [zona_iso_10816(v) for v in (1.0, 2.0, 3.5, 5.0)] == ["A", "B", "C", "D"]


def test_limites_casam_modelo_do_catalogo(ambiente):
    garantir_schema()
    inserir_motor("MTR-001", "WEG W22 IE3 Premium", "x", fabricante="WEG")
    inserir_motor("MTR-009", "Marca Desconhecida X1", "y", fabricante="Foo")
    with get_connection() as c:
        c.execute("INSERT INTO catalogo_especificacoes_externas (modelo_motor, fabricante, temp_max_tolerada, "
                  "vibracao_limite_rms) VALUES ('W22', 'WEG', 85.0, 2.8)")
        c.execute("INSERT INTO catalogo_especificacoes_externas (modelo_motor, fabricante, temp_max_tolerada, "
                  "vibracao_limite_rms) VALUES ('W22', 'WEG', 86.0, 2.9)")   # versão mais recente
    lim = resolver_limites_todos()
    assert lim[1].fonte == "catalogo" and lim[1].temp_max == 86.0
    assert lim[2].fonte == "padrao" and lim[2].temp_max == 80.0


def test_recomendacao_sem_llm_traz_procedimentos_e_referencias(ambiente):
    cfg = Config.carregar()
    av = avaliar_leitura({"temperatura": 90, "vibracao": 5.0}, temp_max=85, vib_max=2.8, cfg=cfg)
    rec = SuporteOperacional(cfg).recomendar(av, tag="MTR-X", modelo="W22")
    assert rec.origem == "regras+rag"
    assert rec.prioridade == "urgente" and rec.prazo_horas == cfg.prazo_critico_h
    assert any("lubrifica" in p["descricao"].lower() for p in rec.procedimentos)      # caso conjunto
    assert {p["tipo"] for p in rec.procedimentos} == {"corretivo", "preventivo"}
    assert rec.referencias and all(r["fonte"] for r in rec.referencias)


def test_recomendacao_funciona_mesmo_sem_base(ambiente, monkeypatch):
    cfg = Config.carregar()
    suporte = SuporteOperacional(cfg)
    monkeypatch.setattr(SuporteOperacional, "base", property(lambda self: None))
    av = avaliar_leitura({"vibracao": 3.0}, temp_max=85, vib_max=2.8, cfg=cfg)
    rec = suporte.recomendar(av, tag="MTR-X")
    assert rec.origem == "regras" and rec.procedimentos and rec.acao_recomendada


def test_base_conhecimento_encontra_manual_e_separa_colecoes(ambiente):
    base = BaseConhecimento()
    assert base.backend == "lexical" and base.total_trechos > 0
    achados = base.buscar_trechos("alinhamento a laser vibração rolamento", top_k=3, colecao="manuais")
    assert achados and all(t.colecao == "manuais" for t in achados)
    assert base.buscar_trechos("zzzz inexistente qwerty", top_k=2) == []

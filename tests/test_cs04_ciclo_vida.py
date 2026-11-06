"""Ciclo de vida dos eventos, sincronização de status e resiliência (Sprint 4)."""

from __future__ import annotations

import shutil

import pytest

from src.integracao import ciclo_vida_eventos as cv
from src.integracao.config import PROJECT_ROOT, Config
from src.integracao.orquestrador import Orquestrador
from src.integracao.resiliencia import Disjuntor, com_retry
from src.integracao.simulador import SimuladorTelemetria
from src.persistencia.database import get_connection

TAG = "MTR-L01-BOM-001"


def _preparar_amostras(cfg: Config) -> None:
    a = PROJECT_ROOT / "data" / "samples"
    for f in a.glob("leituras_*.csv"):
        shutil.copy2(f, cfg.raw_dir / f.name)
    shutil.copy2(a / "cadastro_ativos_sample.csv", cfg.raw_dir / "cadastro_ativos.csv")
    (cfg.raw_dir / "placas_extraidas").mkdir(exist_ok=True)
    for j in (a / "placas_extraidas").glob("*.json"):
        shutil.copy2(j, cfg.raw_dir / "placas_extraidas" / j.name)


def _sql(sql, params=()):
    with get_connection() as c:
        return [tuple(r) for r in c.execute(sql, params).fetchall()]


@pytest.fixture()
def orq(ambiente):
    cfg = Config.carregar()
    _preparar_amostras(cfg)
    sim = SimuladorTelemetria(cfg.raw_dir, modo="cenario", semente=1)
    o = Orquestrador(cfg, modo="teste", simulador=sim)
    o.executar_ciclo(0)           # carga histórica: MTR-001 termina em estado crítico
    return o


def test_alerta_vira_status_evento_os_e_recomendacao(orq):
    ev = _sql("SELECT severidade, status_resolucao, origem_recomendacao, procedimentos_json FROM eventos_operacionais")
    assert len(ev) == 1 and ev[0][0] == "CRITICO" and ev[0][1] == "encaminhado"
    assert ev[0][2] == "regras+rag" and len(ev[0][3]) > 10
    assert _sql("SELECT status_operacional FROM associacoes_ativos WHERE tag=?", (TAG,)) == [("critico",)]
    os_ = _sql("SELECT tipo, prioridade, status, evento_id FROM manutencoes")
    assert os_ == [("corretiva", "urgente", "pendente", 1)]
    assert len(list((Config.carregar().notificacoes_dir).glob("*.html"))) == 1


def test_status_inconsistente_e_sincronizado_e_manutencao_preservada(orq):
    st = dict(_sql("SELECT tag, status_operacional FROM associacoes_ativos"))
    assert st["MTR-ENV-TRP-005"] == "operacional"      # estava 'critico' no cadastro, leitura normal
    assert st["MTR-L01-EST-002"] == "operacional"      # estava 'atencao'
    assert st["MTR-L02-CMP-003"] == "manutencao"       # definido por pessoas: não é sobrescrito


def test_anomalia_persistente_nao_duplica_evento_nem_os(orq):
    orq.executar_ciclo(1)
    orq.executar_ciclo(2)
    assert _sql("SELECT COUNT(*) FROM eventos_operacionais WHERE tag_ativo=?", (TAG,)) == [(1,)]
    assert _sql("SELECT COUNT(*) FROM manutencoes WHERE motor_id=1") == [(1,)]
    assert _sql("SELECT ocorrencias FROM eventos_operacionais WHERE tag_ativo=?", (TAG,)) == [(3,)]


def test_ciclo_sem_leitura_nova_nao_avanca_contagem(orq):
    cfg = Config.carregar()
    orq.simulador.sem_telemetria[1] = {"MTR-001", "MTR-002", "MTR-003", "MTR-004", "MTR-005"}
    r = orq.executar_ciclo(1)
    assert r.etapa("avaliacao").detalhes["sem_leitura_nova"] == 5
    assert _sql("SELECT ocorrencias FROM eventos_operacionais") == [(1,)]


def test_resolucao_automatica_apos_leituras_normais(orq):
    cfg = Config.carregar()
    ciclo = 1
    while ciclo <= 12 and _sql("SELECT status_resolucao FROM eventos_operacionais WHERE tag_ativo=?", (TAG,))[0][0] != "resolvido":
        orq.executar_ciclo(ciclo)
        ciclo += 1
    # ciclos 1-4 mantêm MTR-001 crítico; depois 3 normais seguidos encerram o evento
    ev = _sql("SELECT status_resolucao, encerrado_por, resolucao FROM eventos_operacionais WHERE tag_ativo=?", (TAG,))[0]
    assert ev[0] == "resolvido" and ev[1] == cv.ATOR_RPA and "3 leituras" in ev[2]
    assert _sql("SELECT status_operacional FROM associacoes_ativos WHERE tag=?", (TAG,)) == [("operacional",)]
    assert _sql("SELECT m.status FROM manutencoes m JOIN eventos_operacionais e ON e.manutencao_id=m.id "
                "WHERE e.tag_ativo=?", (TAG,)) == [("concluida",)]


def test_atendimento_humano_bloqueia_resolucao_automatica(orq):
    cv.assumir_evento(TAG, "ana.souza", "em campo")
    for c in range(1, 9):
        orq.executar_ciclo(c)
    assert _sql("SELECT status_resolucao FROM eventos_operacionais WHERE tag_ativo=?", (TAG,)) == [("em_atendimento",)]
    assert _sql("SELECT status_operacional FROM associacoes_ativos WHERE tag=?", (TAG,)) == [("manutencao",)]
    cv.concluir_evento(TAG, "ana.souza", "Rolamento trocado")
    assert _sql("SELECT status_resolucao, encerrado_por FROM eventos_operacionais WHERE tag_ativo=?",
                (TAG,)) == [("resolvido", "tecnico:ana.souza")]
    assert _sql("SELECT status_operacional FROM associacoes_ativos WHERE tag=?", (TAG,)) == [("operacional",)]


def test_concluir_sem_evento_aberto_levanta_erro(orq):
    cv.concluir_evento(TAG, "x", "ok")
    with pytest.raises(ValueError):
        cv.concluir_evento(TAG, "x", "ok")


def test_escalonamento_gera_notificacao_e_atualiza_os(orq):
    for c in range(1, 8):
        orq.executar_ciclo(c)
    ev = _sql("SELECT severidade FROM eventos_operacionais WHERE tag_ativo='MTR-UTIL-EXA-004'")
    assert ev == [("CRITICO",)]
    hist = [r[0] for r in _sql("SELECT acao FROM historico_eventos h JOIN eventos_operacionais e ON e.id=h.evento_id "
                               "WHERE e.tag_ativo='MTR-UTIL-EXA-004' ORDER BY h.id")]
    assert "escalonamento" in hist
    assert _sql("SELECT tipo, prioridade FROM manutencoes WHERE evento_id=(SELECT id FROM eventos_operacionais "
                "WHERE tag_ativo='MTR-UTIL-EXA-004')") == [("corretiva", "urgente")]


def test_auditoria_encadeada_detecta_adulteracao(orq):
    from src.integracao.ciclo_vida_eventos import verificar_cadeia_auditoria
    with get_connection() as c:
        assert verificar_cadeia_auditoria(c)[0] is True
        c.execute("UPDATE auditoria_operacional SET detalhes = REPLACE(detalhes, 'critico', 'operacional') "
                  "WHERE acao = 'ATUALIZACAO_STATUS' AND detalhes LIKE '%critico%'")
    with get_connection() as c:
        assert verificar_cadeia_auditoria(c)[0] is False


# ------------------------------------------------------------------ resiliência
def test_falha_em_uma_etapa_nao_derruba_o_ciclo(orq):
    orq.falhas_injetadas[1] = {"analise", "contexto_rag"}
    r = orq.executar_ciclo(1)
    assert r.status == "parcial"
    assert r.etapa("analise").status == "falha" and r.etapa("contexto_rag").status == "falha"
    assert r.etapa("avaliacao").status == "ok"
    assert _sql("SELECT status FROM execucoes_pipeline WHERE ciclo=1") == [("parcial",)]


def test_arquivos_invalidos_vao_para_quarentena(orq):
    cfg = Config.carregar()
    orq.simulador.arquivos_corrompidos[1] = {"MTR-003"}
    orq.simulador.motores_desconhecidos[1] = ["MTR-099"]
    r = orq.executar_ciclo(1)
    assert r.etapa("coleta").detalhes["quarentena"] == 2
    assert not list(cfg.raw_dir.glob("leituras_MTR-099.csv"))
    assert len(list(cfg.quarentena_dir.glob("*.motivo.json"))) == 2


def test_falha_na_avaliacao_de_um_ativo_nao_impede_os_demais(orq, monkeypatch):
    from src.integracao import processador_ativos as pa
    original = pa._processar_ativo

    def quebra_um(ativo, *a, **k):
        if ativo["tag"] == "MTR-L02-CMP-003":
            raise RuntimeError("erro simulado")
        return original(ativo, *a, **k)

    monkeypatch.setattr(pa, "_processar_ativo", quebra_um)
    r = orq.executar_ciclo(1)
    assert r.etapa("avaliacao").detalhes["falhas"] == 1
    assert r.etapa("avaliacao").detalhes["avaliados"] == 4
    assert r.etapa("avaliacao").status == "degradado"


def test_banco_indisponivel_aborta_o_ciclo_sem_excecao(ambiente, monkeypatch):
    cfg = Config.carregar()
    o = Orquestrador(cfg, modo="teste")
    monkeypatch.setattr("src.integracao.orquestrador.garantir_schema", lambda: (_ for _ in ()).throw(OSError("disco cheio")))
    r = o.executar_ciclo(1)
    assert r.status == "falha" and len(r.etapas) == 1


def test_laco_continuo_sobrevive_a_excecao_e_respeita_limite(ambiente, monkeypatch):
    o = Orquestrador(Config.carregar(), modo="teste")
    chamadas = []

    def instavel(n):
        chamadas.append(n)
        if n == 1:
            raise RuntimeError("falha inesperada")
        from src.integracao.orquestrador import ResumoCiclo
        return ResumoCiclo(n)

    monkeypatch.setattr(o, "executar_ciclo", instavel)
    r = o.executar(ciclos=3, intervalo=0)
    assert chamadas == [1, 2, 3] and [x.status for x in r] == ["falha", "sucesso", "sucesso"]


def test_retry_e_disjuntor(ambiente):
    tentativas = []

    def flaky():
        tentativas.append(1)
        if len(tentativas) < 3:
            raise ConnectionError("rede")
        return "ok"

    assert com_retry(flaky, tentativas=3, espera_s=0) == "ok" and len(tentativas) == 3
    with pytest.raises(ConnectionError):
        com_retry(lambda: (_ for _ in ()).throw(ConnectionError("x")), tentativas=2, espera_s=0)
    d = Disjuntor(limite_falhas=2, pausa_s=60)
    d.falha(); assert d.permitido()
    d.falha(); assert d.aberto
    d.sucesso(); assert d.permitido()


def test_contexto_rag_exporta_historico_para_o_assistente(orq):
    from src.integracao.contexto_rag import montar_contexto_assistente
    cfg = Config.carregar()
    doc = (cfg.rag_dir / f"{TAG}.md").read_text(encoding="utf-8")
    assert "Histórico de eventos" in doc and "CRITICO" in doc and "Ordem 1" in doc
    assert (cfg.rag_dir / "contexto_operacional.jsonl").exists()
    ctx = montar_contexto_assistente("Qual o histórico do MTR-001?")
    assert TAG in ctx


def test_demo_completa_gera_evidencias_validas(ambiente):
    from src.integracao.demo import executar_demo
    from src.integracao.validacao import validar_integridade
    r = executar_demo(ciclos=14, intervalo=0)
    assert all(ok for _, ok, _ in validar_integridade(r["log"])), validar_integridade(r["log"])
    ev = Config.carregar().evidencias_dir
    for nome in ("RELATORIO_EVIDENCIAS.md", "trilha_ponta_a_ponta.csv", "predicta_evidencia.db", "historico_eventos.csv"):
        assert (ev / nome).exists()
    assert _sql("SELECT COUNT(*), SUM(status_resolucao='resolvido') FROM eventos_operacionais") == [(4, 4)]

"""Demonstração controlada da Sprint 4.

Reproduz, em poucos minutos, o que a planta viveria em um dia: alerta crítico
com atendimento humano, alerta de baixa gravidade que se resolve sozinho,
escalonamento de severidade, anomalia elétrica, arquivos defeituosos, sensor
sem sinal e uma etapa que falha. Tudo com semente fixa, para ser reproduzível.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.integracao import ciclo_vida_eventos as cv
from src.integracao.config import PROJECT_ROOT, Config
from src.integracao.evidencias import gerar_evidencias
from src.integracao.orquestrador import Orquestrador, ResumoCiclo
from src.integracao.simulador import SimuladorTelemetria
from src.persistencia.database import get_db_path

TAG_CRITICA = "MTR-L01-BOM-001"


def _limpar(cfg: Config) -> None:
    for sufixo in ("", "-wal", "-shm", "-journal"):
        alvo = Path(str(get_db_path()) + sufixo)
        if alvo.exists():
            alvo.unlink()
    for pasta in (cfg.raw_dir, cfg.raw_dir.parent / "processed", cfg.quarentena_dir, cfg.rag_dir, cfg.notificacoes_dir):
        if pasta.exists():
            shutil.rmtree(pasta)
        pasta.mkdir(parents=True, exist_ok=True)


def preparar_dados_exemplo(cfg: Config) -> None:
    amostras = PROJECT_ROOT / "data" / "samples"
    for csv in amostras.glob("leituras_*.csv"):
        shutil.copy2(csv, cfg.raw_dir / csv.name)
    shutil.copy2(amostras / "cadastro_ativos_sample.csv", cfg.raw_dir / "cadastro_ativos.csv")
    placas = cfg.raw_dir / "placas_extraidas"
    placas.mkdir(exist_ok=True)
    for js in (amostras / "placas_extraidas").glob("*.json"):
        shutil.copy2(js, placas / js.name)


def executar_demo(ciclos: int = 14, intervalo: float = 0.0, semente: int = 42,
                  injetar_falhas: bool = True, gerar_saida: bool = True) -> dict:
    cfg = Config.carregar()
    arquivo_log = cfg.evidencias_dir / "logs" / "execucao.jsonl"
    arquivo_log.parent.mkdir(parents=True, exist_ok=True)
    if arquivo_log.exists():
        arquivo_log.unlink()
    _limpar(cfg)
    preparar_dados_exemplo(cfg)

    sim = SimuladorTelemetria(cfg.raw_dir, modo="cenario", semente=semente)
    orq = Orquestrador(cfg, modo="demo", simulador=sim, arquivo_log=arquivo_log)
    inicio = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=10 * ciclos)
    orq.relogio = lambda ciclo: inicio + timedelta(minutes=10 * ciclo)

    if injetar_falhas:
        sim.arquivos_corrompidos[6] = {"MTR-003"}
        sim.motores_desconhecidos[6] = ["MTR-099"]
        sim.sem_telemetria[8] = {"MTR-005"}
        orq.falhas_injetadas[7] = {"analise"}

    def acoes_humanas(ciclo: int, _r: ResumoCiclo) -> None:
        if ciclo == 3:
            cv.assumir_evento(TAG_CRITICA, "tecnico.turno_a", "Equipe em campo no pedestal A", orq.run_id)
            orq.log.info("humano", "atendimento_iniciado", "Técnico assumiu o evento", ativo=TAG_CRITICA)
        if ciclo == 5:
            cv.concluir_evento(TAG_CRITICA, "tecnico.turno_a",
                               "Realinhado o eixo a laser e trocado o rolamento do lado acoplado; vibração normalizada.",
                               orq.run_id)
            orq.log.info("humano", "resolucao_registrada", "Técnico concluiu o atendimento", ativo=TAG_CRITICA)

    orq.log.ciclo = 0
    orq.log.info("demo", "inicio", f"Demonstração iniciada ({ciclos} ciclos, semente {semente})", run_id_demo=orq.run_id)
    resultados = [orq.executar_ciclo(0)]                   # carga histórica
    resultados += orq.executar(ciclos, intervalo, acoes_humanas, primeiro_ciclo=1)
    orq.log.ciclo = None
    orq.log.info("demo", "fim", "Demonstração concluída")

    saida = gerar_evidencias(cfg, arquivo_log, orq.run_id) if gerar_saida else None
    return {"run_id": orq.run_id, "ciclos": resultados, "evidencias": saida, "log": arquivo_log}

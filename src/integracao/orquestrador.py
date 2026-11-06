"""Orquestrador do pipeline RPA integrado (Sprint 4).

Em cada ciclo executa, nesta ordem, as automações das sprints anteriores e as
novas, cada uma isolada por tratamento de exceção:

    preparo -> telemetria (simulada) -> cadastro -> catálogo -> coleta
            -> análise -> avaliação dos ativos -> contexto do assistente -> fechamento

Se uma etapa falha, o erro é registrado e o ciclo segue com o que for possível.
"""

from __future__ import annotations

import json
import logging
import shutil
import signal
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from src.integracao.config import Config
from src.integracao.contexto_rag import exportar_contexto
from src.integracao.log_estruturado import LogEstruturado
from src.integracao.migracao import garantir_schema
from src.integracao.processador_ativos import avaliar_ativos
from src.integracao.resiliencia import EtapaResultado, com_retry, executar_etapa
from src.integracao.simulador import SimuladorTelemetria
from src.integracao.suporte_operacional import SuporteOperacional
from src.persistencia.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class ResumoCiclo:
    ciclo: int
    status: str = "sucesso"                 # sucesso | parcial | falha
    etapas: list[EtapaResultado] = field(default_factory=list)
    duracao_ms: int = 0

    def etapa(self, nome: str) -> EtapaResultado | None:
        return next((e for e in self.etapas if e.nome == nome), None)


class Orquestrador:
    def __init__(self, cfg: Config | None = None, *, modo: str = "unico", run_id: str | None = None,
                 simulador: SimuladorTelemetria | None = None, arquivo_log: Path | None = None):
        self.cfg = cfg or Config.carregar()
        self.modo = modo
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        self.simulador = simulador
        self.log = LogEstruturado(arquivo_log or self.cfg.logs_dir / "rpa_integrado.jsonl", self.run_id)
        self.suporte = SuporteOperacional(self.cfg)
        self.falhas_injetadas: dict[int, set[str]] = {}
        self.relogio: Callable[[int], datetime] = lambda ciclo: datetime.now()
        self._parar = False

    # ------------------------------------------------------------ ciclo
    def executar_ciclo(self, ciclo: int) -> ResumoCiclo:
        self.log.ciclo = ciclo
        inicio = datetime.now()
        t0 = time.perf_counter()
        resumo = ResumoCiclo(ciclo)
        self.log.info("ciclo", "inicio", f"Ciclo {ciclo} iniciado", modo=self.modo)

        etapas: list[tuple[str, Callable[[], dict[str, Any] | None]]] = [
            ("telemetria", lambda: self._telemetria(ciclo)),
            ("cadastro", self._cadastro),
            ("catalogo", self._catalogo),
            ("coleta", self._coleta),
            ("analise", self._analise),
            ("avaliacao", self._avaliacao),
            ("contexto_rag", self._contexto),
        ]
        preparo = executar_etapa("preparo", self._preparo, self.log)
        resumo.etapas.append(preparo)
        if preparo.status == "falha":
            resumo.status = "falha"
            self.log.erro("ciclo", "abortado", "Banco indisponível: ciclo abortado e será repetido")
        else:
            for nome, fn in etapas:
                if nome == "telemetria" and self.simulador is None:
                    continue
                resumo.etapas.append(executar_etapa(nome, self._com_falha_injetada(ciclo, nome, fn), self.log))
            if any(e.status != "ok" for e in resumo.etapas):
                resumo.status = "parcial"

        resumo.duracao_ms = int((time.perf_counter() - t0) * 1000)
        self._persistir_execucao(resumo, inicio)
        nivel = {"sucesso": "INFO", "parcial": "WARNING", "falha": "ERROR"}[resumo.status]
        self.log.registrar(nivel, "ciclo", "fim", f"Ciclo {ciclo} terminou: {resumo.status}",
                           duracao_ms=resumo.duracao_ms,
                           etapas={e.nome: e.status for e in resumo.etapas})
        return resumo

    def _com_falha_injetada(self, ciclo: int, nome: str, fn):
        def interna():
            if nome in self.falhas_injetadas.get(ciclo, set()):
                raise RuntimeError(f"falha simulada na etapa '{nome}' (teste de resiliência)")
            return fn()
        return interna

    # ------------------------------------------------------------ etapas
    def _preparo(self) -> dict[str, Any]:
        garantir_schema()
        with get_connection() as conn:
            if conn.execute("SELECT COUNT(*) FROM motores").fetchone()[0] == 0:
                from scripts.cadastrar_motores import MOTORES_INICIAIS
                from src.persistencia.motor_repository import inserir_motor
                for m in MOTORES_INICIAIS:
                    inserir_motor(**m)
                self.log.info("preparo", "motores_cadastrados", f"{len(MOTORES_INICIAIS)} motores cadastrados")
        return {}

    def _telemetria(self, ciclo: int) -> dict[str, Any]:
        assert self.simulador is not None
        if ciclo == 0:
            return {"arquivos": 0, "observacao": "carga histórica: sem simulação"}
        gerados = self.simulador.gerar(ciclo, self.relogio(ciclo))
        return {"arquivos": len(gerados)}

    def _cadastro(self) -> dict[str, Any]:
        from src.cadastro_ativo.ativo_association_pipeline import executar_associacao_ativos
        from src.cadastro_ativo.placa_pipeline import executar_pipeline_placas

        det: dict[str, Any] = {"associacoes": 0, "placas": 0}
        if (self.cfg.raw_dir / "cadastro_ativos.csv").exists():
            r = executar_associacao_ativos(self.cfg.raw_dir / "cadastro_ativos.csv", arquivar=True,
                                           origem="rpa_integrado_cadastro")
            det["associacoes"] = r["criados"] + r["atualizados"]
            if r["erros"]:
                det["degradado"] = True
                self.log.aviso("cadastro", "erros_associacao", f"{r['erros']} linha(s) com erro", erros=r["detalhes_erros"][:5])
        placas = self.cfg.raw_dir / "placas_extraidas"
        if placas.exists() and any(placas.glob("*.json")):
            r = executar_pipeline_placas(placas, arquivar=True)
            det["placas"] = r["criados"] + r["atualizados"]
            if r["erros"]:
                det["degradado"] = True
                self.log.aviso("cadastro", "erros_placa", f"{r['erros']} placa(s) com erro", erros=r["detalhes_erros"][:5])
        return det

    def _catalogo(self) -> dict[str, Any]:
        with get_connection() as conn:
            vigente = conn.execute(
                "SELECT COUNT(*) FROM catalogo_especificacoes_externas WHERE data_coleta > datetime('now', ?)",
                (f"-{self.cfg.catalogo_validade_horas} hours",)).fetchone()[0]
        if vigente:
            return {"atualizado": False, "motivo": "catálogo dentro da validade"}

        from src.persistencia.catalogo_repository import salvar_especificacao
        from src.scraping.scraper_motores import buscar_dados_climaticos, raspar_catalogo_motores

        det: dict[str, Any] = {"atualizado": True}
        clima = com_retry(buscar_dados_climaticos, tentativas=2, espera_s=self.cfg.retry_espera_s, nome="clima",
                          log=self.log, etapa="catalogo")
        if "error" in clima:
            det["degradado"] = True
            det["clima"] = "indisponível (usado valor padrão)"
            self.log.aviso("catalogo", "clima_indisponivel", "API de clima indisponível; seguindo sem contexto climático")
        itens = com_retry(lambda: raspar_catalogo_motores(self.cfg.catalogo_url), tentativas=self.cfg.retry_tentativas,
                          espera_s=self.cfg.retry_espera_s, nome="catalogo", log=self.log, etapa="catalogo")
        if not itens:
            raise RuntimeError("nenhuma especificação obtida do catálogo (online ou local)")
        guia = {"temperatura_alta": "Verificar ventilação, inspecionar painel, verificar sobrecarga e limpar aletas.",
                "vibracao_alta": "Verificar alinhamento, inspecionar rolamentos e checar fixação da base na sapata."}
        fonte = self.cfg.catalogo_url or "fallback_local_html"
        for i in itens:
            salvar_especificacao(i["modelo"], i["fabricante"], i["temp_max"], i["vib_max"], guia, clima, fonte)
        det["modelos"] = len(itens)
        return det

    def _coleta(self) -> dict[str, Any]:
        from src.coleta.pipeline import processar_arquivo

        arquivos = sorted(self.cfg.raw_dir.glob("leituras_*.csv")) if self.cfg.raw_dir.exists() else []
        det = {"arquivos": len(arquivos), "leituras_inseridas": 0, "quarentena": 0}
        for arq in arquivos:
            try:
                r = processar_arquivo(arq, arquivar=True)
            except Exception as exc:  # noqa: BLE001
                r = {"status": "erro", "inseridas": 0, "motor": None, "arquivo": arq.name, "detalhe": str(exc)}
            if r["status"] == "ok":
                det["leituras_inseridas"] += r["inseridas"]
                continue
            destino = self._quarentena(arq, r["status"])
            det["quarentena"] += 1
            det["degradado"] = True
            self.log.aviso("coleta", "arquivo_em_quarentena",
                           f"{arq.name} não pôde ser processado ({r['status']}); movido para quarentena",
                           arquivo=arq.name, motivo=r["status"], destino=str(destino.name) if destino else None)
        self._limpar_processados()
        return det

    def _quarentena(self, arq: Path, motivo: str) -> Path | None:
        try:
            self.cfg.quarentena_dir.mkdir(parents=True, exist_ok=True)
            destino = self.cfg.quarentena_dir / f"{arq.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}{arq.suffix}"
            shutil.move(str(arq), str(destino))
            destino.with_suffix(".motivo.json").write_text(
                json.dumps({"arquivo": arq.name, "motivo": motivo, "run_id": self.run_id,
                            "em": datetime.now().isoformat()}, ensure_ascii=False), encoding="utf-8")
            return destino
        except OSError as exc:
            self.log.erro("coleta", "quarentena_falhou", f"Não foi possível isolar {arq.name}: {exc}")
            return None

    def _limpar_processados(self, manter: int = 30) -> None:
        pasta = self.cfg.raw_dir.parent / "processed"
        if not pasta.exists():
            return
        arquivos = sorted(pasta.glob("leituras_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        for velho in arquivos[manter:]:
            try:
                velho.unlink()
            except OSError:
                pass

    def _analise(self) -> dict[str, Any]:
        from src.analise.analisador import executar_analise
        r = executar_analise()
        return {"leituras": r.total_leituras, "normais": r.total_normais, "alertas": r.total_alertas,
                "criticas": r.total_criticas, "anomalias_persistidas": r.total_anomalias_persistidas}

    def _avaliacao(self) -> dict[str, Any]:
        r = avaliar_ativos(self.cfg, self.log, self.run_id, self.suporte)
        r.pop("acoes", None)
        return r

    def _contexto(self) -> dict[str, Any]:
        r = exportar_contexto(self.cfg)
        if r["documentos_alterados"]:
            from src.analise.base_conhecimento import BaseConhecimento
            r["trechos_operacionais"] = BaseConhecimento().reindexar_operacional()
        return r

    # ------------------------------------------------------------ persistência da execução
    def _persistir_execucao(self, resumo: ResumoCiclo, inicio: datetime) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO execucoes_pipeline (run_id, ciclo, modo, inicio, fim, status, resumo_json) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (self.run_id, resumo.ciclo, self.modo, inicio.isoformat(timespec="seconds"),
                     datetime.now().isoformat(timespec="seconds"), resumo.status,
                     json.dumps({e.nome: e.status for e in resumo.etapas})))
                for e in resumo.etapas:
                    conn.execute(
                        "INSERT INTO execucoes_etapas (run_id, ciclo, etapa, status, duracao_ms, detalhes_json, erro) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (self.run_id, resumo.ciclo, e.nome, e.status, e.duracao_ms,
                         json.dumps(e.detalhes, ensure_ascii=False, default=str), e.erro))
        except Exception as exc:  # noqa: BLE001
            self.log.erro("ciclo", "persistencia_falhou", f"Não foi possível gravar o resumo do ciclo: {exc}")

    # ------------------------------------------------------------ laço contínuo
    def executar(self, ciclos: int | None = None, intervalo: float | None = None,
                 apos_ciclo: Callable[[int, ResumoCiclo], None] | None = None, primeiro_ciclo: int = 1) -> list[ResumoCiclo]:
        """Roda `ciclos` ciclos (ou indefinidamente se None) com espera entre eles."""
        intervalo = self.cfg.intervalo_segundos if intervalo is None else intervalo
        resultados: list[ResumoCiclo] = []
        falhas_seguidas = 0
        n = primeiro_ciclo

        def encerrar(*_):
            self._parar = True
            self.log.info("ciclo", "encerramento_solicitado", "Sinal recebido; terminando após o ciclo atual")

        try:
            signal.signal(signal.SIGINT, encerrar)
            signal.signal(signal.SIGTERM, encerrar)
        except ValueError:      # fora da thread principal (ex.: notebook)
            pass

        while not self._parar and (ciclos is None or n < primeiro_ciclo + ciclos):
            try:
                r = self.executar_ciclo(n)
            except Exception as exc:  # noqa: BLE001 - nada derruba o laço
                self.log.erro("ciclo", "excecao_nao_tratada", f"{type(exc).__name__}: {exc}")
                r = ResumoCiclo(n, status="falha")
            resultados.append(r)
            if apos_ciclo:
                try:
                    apos_ciclo(n, r)
                except Exception as exc:  # noqa: BLE001
                    self.log.erro("ciclo", "acao_pos_ciclo_falhou", str(exc))
            falhas_seguidas = falhas_seguidas + 1 if r.status == "falha" else 0
            n += 1
            if ciclos is not None and n >= primeiro_ciclo + ciclos:
                break
            espera = min(intervalo * (2 ** falhas_seguidas) if falhas_seguidas else intervalo,
                         self.cfg.backoff_maximo_segundos)
            if espera:
                for _ in range(int(espera * 10)):
                    if self._parar:
                        break
                    time.sleep(0.1)
        return resultados

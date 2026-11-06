"""Configuração central da Sprint 4.

Todos os parâmetros podem ser ajustados por variável de ambiente (ou pelo
arquivo .env), o que permite rodar a mesma automação no computador do grupo,
no Docker ou no Google Colab sem alterar código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.getenv(nome, padrao))
    except ValueError:
        return padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


def _env_path(nome: str, padrao: Path) -> Path:
    valor = os.getenv(nome)
    if not valor:
        return padrao
    caminho = Path(valor)
    return caminho if caminho.is_absolute() else PROJECT_ROOT / caminho


@dataclass(frozen=True)
class Config:
    # Diretórios de trabalho
    raw_dir: Path
    quarentena_dir: Path
    rag_dir: Path
    manuais_dir: Path
    notificacoes_dir: Path
    logs_dir: Path
    evidencias_dir: Path

    # Regras de negócio
    limiar_alerta: float            # fração do limite que já gera ALERTA
    ciclos_para_resolver: int       # leituras normais seguidas p/ encerrar evento
    corrente_fator_limite: float    # limite de corrente = fator x nominal
    tensao_tol_alerta: float        # desvio de tensão que gera ALERTA
    tensao_tol_critica: float       # desvio de tensão que gera CRITICO
    tensao_nominal_padrao: float    # usada quando a placa do motor não foi cadastrada
    prazo_critico_h: int
    prazo_alerta_h: int

    # Execução contínua
    intervalo_segundos: int
    backoff_maximo_segundos: int

    # Resiliência
    retry_tentativas: int
    retry_espera_s: float

    # IA / base de conhecimento
    usar_llm: str                   # auto | sim | nao
    ollama_modelo: str
    ollama_timeout_s: float
    rag_backend: str                # auto | semantico | lexical

    # Catálogo técnico
    catalogo_url: str | None
    catalogo_validade_horas: int

    @classmethod
    def carregar(cls) -> "Config":
        return cls(
            raw_dir=_env_path("PREDICTA_RAW_DIR", PROJECT_ROOT / "data" / "raw"),
            quarentena_dir=_env_path("PREDICTA_QUARENTENA_DIR", PROJECT_ROOT / "data" / "quarentena"),
            rag_dir=_env_path("PREDICTA_RAG_DIR", PROJECT_ROOT / "data" / "rag" / "operacional"),
            manuais_dir=_env_path("PREDICTA_MANUAIS_DIR", PROJECT_ROOT / "data" / "manuais"),
            notificacoes_dir=_env_path("PREDICTA_NOTIFICACOES_DIR", PROJECT_ROOT / "logs" / "notificacoes"),
            logs_dir=_env_path("PREDICTA_LOGS_DIR", PROJECT_ROOT / "logs"),
            evidencias_dir=_env_path("PREDICTA_EVIDENCIAS_DIR", PROJECT_ROOT / "evidencias"),
            limiar_alerta=_env_float("LIMIAR_ALERTA", 0.9),
            ciclos_para_resolver=_env_int("CICLOS_PARA_RESOLVER", 3),
            corrente_fator_limite=_env_float("CORRENTE_FATOR_LIMITE", 1.10),
            tensao_tol_alerta=_env_float("TENSAO_TOL_ALERTA", 0.05),
            tensao_tol_critica=_env_float("TENSAO_TOL_CRITICA", 0.10),
            tensao_nominal_padrao=_env_float("TENSAO_NOMINAL_PADRAO", 380.0),
            prazo_critico_h=_env_int("PRAZO_CRITICO_H", 4),
            prazo_alerta_h=_env_int("PRAZO_ALERTA_H", 72),
            intervalo_segundos=_env_int("INTERVALO_CICLO_S", 20),
            backoff_maximo_segundos=_env_int("BACKOFF_MAXIMO_S", 300),
            retry_tentativas=_env_int("RETRY_TENTATIVAS", 3),
            retry_espera_s=_env_float("RETRY_ESPERA_S", 1.0),
            usar_llm=os.getenv("PREDICTA_USAR_LLM", "auto").strip().lower(),
            ollama_modelo=os.getenv("OLLAMA_MODELO", "llama3.2"),
            ollama_timeout_s=_env_float("OLLAMA_TIMEOUT_S", 25.0),
            rag_backend=os.getenv("PREDICTA_RAG_BACKEND", "auto").strip().lower(),
            catalogo_url=os.getenv("CATALOGO_URL") or None,
            catalogo_validade_horas=_env_int("CATALOGO_VALIDADE_H", 24),
        )

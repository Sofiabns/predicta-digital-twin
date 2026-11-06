"""
Módulo de conexão e gerenciamento do banco de dados SQLite.

Fornece context manager seguro para conexões e utilitários
de inicialização do schema.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# Caminho raiz do projeto (3 níveis acima deste arquivo)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "database" / "motores.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


def get_db_path() -> Path:
    """Retorna o caminho do banco de dados (via .env ou default)."""
    import os
    db_path = os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))
    return Path(db_path) if Path(db_path).is_absolute() else PROJECT_ROOT / db_path


@contextmanager
def get_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager para conexões SQLite com configurações otimizadas.

    Uso:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM motores")

    Yields:
        sqlite3.Connection: Conexão configurada com row_factory e FK ativas.
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row  # permite acesso por nome de coluna
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # melhor concorrência
    conn.execute("PRAGMA busy_timeout = 5000") # evita OperationalError: database is locked

    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Erro na transação, executando rollback: %s", exc)
        raise
    finally:
        conn.close()


def init_database(db_path: Path | None = None) -> None:
    """
    Inicializa o banco de dados executando o schema.sql.

    Cria as tabelas, índices e views se ainda não existirem.
    Idempotente: pode ser chamado múltiplas vezes sem efeito colateral.
    """
    path = db_path or get_db_path()

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema não encontrado: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_connection(path) as conn:
        conn.executescript(schema_sql)

    # Sprint 4: colunas e tabelas de rastreabilidade (idempotente)
    from src.integracao.migracao import garantir_schema
    garantir_schema(path)

    logger.info("Banco de dados inicializado em: %s", path)


def check_database() -> dict:
    """
    Verifica o estado do banco e retorna estatísticas básicas.

    Returns:
        dict: { 'motores': N, 'leituras': N, 'anomalias': N, 'manutencoes': N }
    """
    tabelas = [
        "motores",
        "leituras",
        "anomalias",
        "manutencoes",
        "plantas",
        "areas",
        "linhas",
        "localizacoes",
        "associacoes_ativos",
        "dados_placa_motor",
        "auditoria_operacional",
        "catalogo_especificacoes_externas",
        "eventos_operacionais",
        "historico_eventos",
        "execucoes_pipeline",
    ]
    stats = {}

    with get_connection() as conn:
        for tabela in tabelas:
            cursor = conn.execute(f"SELECT COUNT(*) AS total FROM {tabela}")
            stats[tabela] = cursor.fetchone()["total"]

    return stats

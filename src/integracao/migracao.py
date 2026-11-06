"""Migração de esquema da Sprint 4.

Funciona tanto para um banco novo quanto para um banco já criado nas
sprints anteriores: só adiciona o que ainda não existe.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from src.persistencia.database import PROJECT_ROOT, get_connection

logger = logging.getLogger(__name__)

SCHEMA_CS04 = PROJECT_ROOT / "database" / "schema_cs04.sql"

COLUNAS_NOVAS: dict[str, list[tuple[str, str]]] = {
    "eventos_operacionais": [
        ("leitura_id", "INTEGER"),
        ("manutencao_id", "INTEGER"),
        ("ocorrencias", "INTEGER DEFAULT 1"),
        ("ciclos_normais", "INTEGER DEFAULT 0"),
        ("procedimentos_json", "TEXT"),
        ("referencias_json", "TEXT"),
        ("origem_recomendacao", "TEXT"),
        ("prioridade", "TEXT"),
        ("prazo_horas", "INTEGER"),
        ("run_id", "TEXT"),
        ("atualizado_em", "TEXT"),
        ("encerrado_em", "TEXT"),
        ("resolucao", "TEXT"),
        ("encerrado_por", "TEXT"),
        ("encaminhado_para", "TEXT"),
    ],
    "associacoes_ativos": [
        ("ultima_leitura_avaliada_id", "INTEGER"),
        ("ultima_avaliacao_em", "TEXT"),
    ],
    "manutencoes": [
        ("evento_id", "INTEGER"),
    ],
}


def _colunas(conn: sqlite3.Connection, tabela: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}


def garantir_schema(db_path: Path | None = None) -> dict[str, list[str]]:
    """Aplica o esquema base, as colunas novas e os objetos da Sprint 4.

    Retorna as colunas adicionadas nesta chamada (vazio se nada mudou).
    """
    from src.persistencia.database import SCHEMA_PATH

    adicionadas: dict[str, list[str]] = {}
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for tabela, colunas in COLUNAS_NOVAS.items():
            existentes = _colunas(conn, tabela)
            for nome, tipo in colunas:
                if nome not in existentes:
                    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
                    adicionadas.setdefault(tabela, []).append(nome)
        conn.executescript(SCHEMA_CS04.read_text(encoding="utf-8"))
    if adicionadas:
        logger.info("Migração Sprint 4 aplicada: %s", adicionadas)
    return adicionadas

"""Resolução dos limites operacionais de cada motor.

O catálogo do fabricante usa nomes curtos de modelo ("W22") enquanto o
cadastro e a placa trazem o nome completo ("WEG W22 IE3 Premium"). Aqui o
casamento é feito pelo fabricante + modelo contido no nome completo, e a
origem do limite (catálogo ou padrão) fica registrada.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass

from src.persistencia.database import get_connection

# Padrões baseados no manual normativo (ISO 10816-3, limite da zona C/D e
# classe de isolamento) para ativos que não existem no catálogo.
TEMP_PADRAO = 80.0
VIB_PADRAO = 2.8


@dataclass(frozen=True)
class Limites:
    temp_max: float
    vib_max: float
    fonte: str                      # "catalogo" | "padrao"
    modelo_catalogo: str | None = None
    guia_troubleshooting: str | None = None


def _norm(texto: str | None) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _escolher(catalogo: list[sqlite3.Row], fabricante: str, *textos: str) -> sqlite3.Row | None:
    fab = _norm(fabricante)
    alvo = " ".join(_norm(t) for t in textos if t)
    melhor, tam = None, 0
    for linha in catalogo:
        if fab and _norm(linha["fabricante"]) != fab:
            continue
        modelo = _norm(linha["modelo_motor"])
        if modelo and modelo in alvo and len(modelo) > tam:
            melhor, tam = linha, len(modelo)
    return melhor


def resolver_limites_todos(conn: sqlite3.Connection | None = None) -> dict[int, Limites]:
    """Limites de todos os motores cadastrados, indexados por motor_id."""
    sql_motores = """
        SELECT m.id, m.modelo AS modelo_cad, m.fabricante AS fab_cad,
               dp.modelo AS modelo_placa, dp.fabricante AS fab_placa
        FROM motores m LEFT JOIN dados_placa_motor dp ON dp.motor_id = m.id
    """
    sql_cat = """
        SELECT c.* FROM catalogo_especificacoes_externas c
        WHERE c.id = (SELECT MAX(id) FROM catalogo_especificacoes_externas x
                      WHERE x.modelo_motor = c.modelo_motor AND x.fabricante = c.fabricante)
    """

    def _calcular(c: sqlite3.Connection) -> dict[int, Limites]:
        catalogo = c.execute(sql_cat).fetchall()
        saida: dict[int, Limites] = {}
        for m in c.execute(sql_motores).fetchall():
            fab = m["fab_placa"] or m["fab_cad"] or ""
            achado = _escolher(catalogo, fab, m["modelo_placa"] or "", m["modelo_cad"] or "")
            if achado and achado["temp_max_tolerada"] and achado["vibracao_limite_rms"]:
                saida[m["id"]] = Limites(
                    float(achado["temp_max_tolerada"]), float(achado["vibracao_limite_rms"]),
                    "catalogo", achado["modelo_motor"], achado["guia_troubleshooting_json"],
                )
            else:
                saida[m["id"]] = Limites(TEMP_PADRAO, VIB_PADRAO, "padrao")
        return saida

    if conn is not None:
        return _calcular(conn)
    with get_connection() as c:
        return _calcular(c)


def resolver_limites(motor_id: int) -> Limites:
    return resolver_limites_todos().get(motor_id, Limites(TEMP_PADRAO, VIB_PADRAO, "padrao"))

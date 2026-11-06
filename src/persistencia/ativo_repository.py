"""Associação operacional motor / TAG / localização (CS02)."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.persistencia import area_repository, linha_repository, localizacao_repository, planta_repository
from src.persistencia.auditoria_repository import registrar_auditoria
from src.persistencia.database import get_connection
from src.persistencia.motor_repository import buscar_motor_por_codigo

logger = logging.getLogger(__name__)


def buscar_associacao_por_motor_id(
    motor_id: int,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM associacoes_ativos WHERE motor_id = ?"
    if conn is not None:
        row = conn.execute(sql, (motor_id,)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (motor_id,)).fetchone()
        return dict(row) if row else None


def buscar_associacao_por_tag(
    tag: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    sql = "SELECT * FROM associacoes_ativos WHERE tag = ?"
    if conn is not None:
        row = conn.execute(sql, (tag,)).fetchone()
        return dict(row) if row else None
    with get_connection() as c:
        row = c.execute(sql, (tag,)).fetchone()
        return dict(row) if row else None


def _liberar_tag_ocupada_por_outro_motor(
    conn: sqlite3.Connection,
    tag: str,
    motor_id: int,
    origem: str,
) -> None:
    rows = conn.execute(
        "SELECT id, motor_id, tag FROM associacoes_ativos WHERE tag = ? AND motor_id != ?",
        (tag, motor_id),
    ).fetchall()
    for r in rows:
        novo_tag = f"{r['tag']}_LEGADO_M{r['motor_id']}"
        conn.execute(
            """
            UPDATE associacoes_ativos
            SET tag = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (novo_tag, r["id"]),
        )
        registrar_auditoria(
            "associacoes_ativos",
            "tag_reatribuida",
            entidade_id=int(r["id"]),
            origem=origem,
            detalhes={
                "acao": "liberacao_tag_para_novo_titular",
                "tag_anterior": r["tag"],
                "tag_nova": novo_tag,
                "motor_id_anterior": r["motor_id"],
                "motor_id_novo": motor_id,
            },
            conn=conn,
        )


def upsert_associacao(
    conn: sqlite3.Connection,
    motor_id: int,
    tag: str,
    localizacao_id: int,
    status_operacional: str,
    origem: str,
) -> str:
    """Cria ou atualiza a associação principal do motor. Retorna criado|atualizado|inalterado."""
    atual = conn.execute(
        "SELECT * FROM associacoes_ativos WHERE motor_id = ?",
        (motor_id,),
    ).fetchone()

    if atual is not None:
        mudou = (
            atual["tag"] != tag
            or int(atual["localizacao_id"]) != int(localizacao_id)
            or atual["status_operacional"] != status_operacional
        )
        if not mudou:
            return "inalterado"

    _liberar_tag_ocupada_por_outro_motor(conn, tag, motor_id, origem)

    atual = conn.execute(
        "SELECT * FROM associacoes_ativos WHERE motor_id = ?",
        (motor_id,),
    ).fetchone()

    if atual is None:
        conn.execute(
            """
            INSERT INTO associacoes_ativos
                (motor_id, tag, localizacao_id, status_operacional, origem_atualizacao)
            VALUES (?, ?, ?, ?, ?)
            """,
            (motor_id, tag, localizacao_id, status_operacional, origem),
        )
        novo = conn.execute(
            "SELECT id FROM associacoes_ativos WHERE motor_id = ?",
            (motor_id,),
        ).fetchone()
        registrar_auditoria(
            "associacoes_ativos",
            "criacao",
            entidade_id=int(novo["id"]) if novo else None,
            origem=origem,
            detalhes={"motor_id": motor_id, "tag": tag, "localizacao_id": localizacao_id},
            conn=conn,
        )
        return "criado"

    mudou = (
        atual["tag"] != tag
        or int(atual["localizacao_id"]) != int(localizacao_id)
        or atual["status_operacional"] != status_operacional
    )
    conn.execute(
        """
        UPDATE associacoes_ativos
        SET tag = ?, localizacao_id = ?, status_operacional = ?,
            origem_atualizacao = ?, data_atualizacao = CURRENT_TIMESTAMP
        WHERE motor_id = ?
        """,
        (tag, localizacao_id, status_operacional, origem, motor_id),
    )
    if mudou:
        registrar_auditoria(
            "associacoes_ativos",
            "atualizacao",
            entidade_id=int(atual["id"]),
            origem=origem,
            detalhes={
                "motor_id": motor_id,
                "tag_anterior": atual["tag"],
                "tag_nova": tag,
                "localizacao_id_anterior": atual["localizacao_id"],
                "localizacao_id_nova": localizacao_id,
                "status_anterior": atual["status_operacional"],
                "status_novo": status_operacional,
            },
            conn=conn,
        )
    return "atualizado"


def sincronizar_cadastro_operacional(
    row: dict[str, Any],
    origem: str,
) -> dict[str, Any]:
    """
    Processa uma linha do CSV de cadastro (já como dict de strings normalizadas).

    Returns:
        dict com chaves: status ('ok'|'ignorado'|'erro'), motivo?, criado/atualizado flags
    """
    codigo_motor = (row.get("codigo_motor") or "").strip()
    motor = buscar_motor_por_codigo(codigo_motor)
    if not motor:
        return {"status": "ignorado", "motivo": "motor_nao_encontrado", "codigo_motor": codigo_motor}

    hierarquia_resumo: dict[str, str] = {}

    with get_connection() as conn:
        pid, stp = planta_repository.upsert_planta(
            (row.get("planta_codigo") or "").strip(),
            (row.get("planta_nome") or "").strip(),
            None,
            conn=conn,
        )
        hierarquia_resumo["planta"] = stp

        aid, sta = area_repository.upsert_area(
            pid,
            (row.get("area_codigo") or "").strip(),
            (row.get("area_nome") or "").strip(),
            None,
            conn=conn,
        )
        hierarquia_resumo["area"] = sta

        lid, stl = linha_repository.upsert_linha(
            aid,
            (row.get("linha_codigo") or "").strip(),
            (row.get("linha_nome") or "").strip(),
            None,
            conn=conn,
        )
        hierarquia_resumo["linha"] = stl

        try:
            cx = float(str(row.get("coordenada_x", "0")).replace(",", "."))
            cy = float(str(row.get("coordenada_y", "0")).replace(",", "."))
        except (TypeError, ValueError):
            cx, cy = 0.0, 0.0

        loc_id, stloc = localizacao_repository.upsert_localizacao(
            lid,
            (row.get("localizacao_codigo") or "").strip(),
            (row.get("localizacao_descricao") or "").strip() or None,
            cx,
            cy,
            conn=conn,
        )
        hierarquia_resumo["localizacao"] = stloc

        tag = (row.get("tag") or "").strip()
        status_op = (row.get("status_operacional") or "operacional").strip().lower()
        # normaliza acentos comuns vindos do CSV
        mapa_status = {
            "operacional": "operacional",
            "atencao": "atencao",
            "atenção": "atencao",
            "manutencao": "manutencao",
            "manutenção": "manutencao",
            "critico": "critico",
            "crítico": "critico",
            "parado": "parado",
        }
        status_op = mapa_status.get(status_op, "operacional")

        resultado_assoc = upsert_associacao(
            conn,
            int(motor["id"]),
            tag,
            loc_id,
            status_op,
            origem,
        )

    return {
        "status": "ok",
        "codigo_motor": codigo_motor,
        "motor_id": motor["id"],
        "associacao": resultado_assoc,
        "hierarquia": hierarquia_resumo,
    }

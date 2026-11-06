"""Ciclo de vida dos eventos operacionais.

Estados de um evento:
    pendente -> encaminhado -> em_atendimento -> resolvido
Toda mudança grava uma linha em ``historico_eventos`` e na auditoria
(com hash encadeado), na mesma transação da mudança de status do ativo.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from src.integracao.suporte_operacional import Recomendacao
from src.persistencia.database import get_connection

ABERTOS = ("pendente", "encaminhado", "em_atendimento")
STATUS_PRESERVADOS = ("manutencao", "parado")   # definidos por pessoas, a automação não sobrescreve
MAPA_STATUS = {"NORMAL": "operacional", "ALERTA": "atencao", "CRITICO": "critico"}
ATOR_RPA = "RPA_PREDICTA"


# ---------------------------------------------------------------- auditoria
def registrar_auditoria_encadeada(conn: sqlite3.Connection, entidade: str, entidade_id: int | None,
                                  acao: str, origem: str, detalhes: dict[str, Any]) -> str:
    """Grava auditoria com hash SHA-256 que inclui o hash do registro anterior."""
    anterior = conn.execute(
        "SELECT detalhes FROM auditoria_operacional WHERE detalhes LIKE '%\"hash\"%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    hash_anterior = "0" * 64
    if anterior:
        try:
            hash_anterior = json.loads(anterior["detalhes"]).get("hash", hash_anterior)
        except (ValueError, TypeError):
            pass
    corpo = {"entidade": entidade, "entidade_id": entidade_id, "acao": acao, "origem": origem, **detalhes}
    payload = json.dumps(corpo, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.sha256((hash_anterior + payload).encode("utf-8")).hexdigest()
    corpo.update({"hash_anterior": hash_anterior, "hash": h})
    conn.execute(
        "INSERT INTO auditoria_operacional (entidade, entidade_id, acao, origem, detalhes) VALUES (?,?,?,?,?)",
        (entidade, entidade_id, acao, origem, json.dumps(corpo, ensure_ascii=False, default=str)),
    )
    return h


def verificar_cadeia_auditoria(conn: sqlite3.Connection) -> tuple[bool, int, str]:
    """Reconstrói os hashes e confirma que nenhum registro foi alterado."""
    linhas = conn.execute(
        "SELECT id, detalhes FROM auditoria_operacional WHERE detalhes LIKE '%\"hash\"%' ORDER BY id"
    ).fetchall()
    esperado = "0" * 64
    for l in linhas:
        corpo = json.loads(l["detalhes"])
        if corpo.get("hash_anterior") != esperado:
            return False, len(linhas), f"cadeia quebrada no registro {l['id']}"
        h = corpo.pop("hash")
        corpo.pop("hash_anterior")
        payload = json.dumps(corpo, sort_keys=True, ensure_ascii=False, default=str)
        if hashlib.sha256((esperado + payload).encode("utf-8")).hexdigest() != h:
            return False, len(linhas), f"conteúdo alterado no registro {l['id']}"
        esperado = h
    return True, len(linhas), "ok"


# ---------------------------------------------------------------- ativo
def atualizar_status_ativo(conn: sqlite3.Connection, motor_id: int, tag: str, novo: str,
                           origem: str, motivo: str, run_id: str | None = None) -> str | None:
    """Atualiza o status operacional e audita. Devolve o status anterior (ou None se igual)."""
    atual = conn.execute("SELECT status_operacional FROM associacoes_ativos WHERE motor_id = ?",
                         (motor_id,)).fetchone()
    if atual is None or atual["status_operacional"] == novo:
        return None
    anterior = atual["status_operacional"]
    conn.execute(
        "UPDATE associacoes_ativos SET status_operacional = ?, origem_atualizacao = ?, "
        "data_atualizacao = CURRENT_TIMESTAMP WHERE motor_id = ?", (novo, origem, motor_id))
    registrar_auditoria_encadeada(conn, "associacoes_ativos", motor_id, "ATUALIZACAO_STATUS", origem,
                                  {"tag": tag, "de": anterior, "para": novo, "motivo": motivo, "run_id": run_id})
    return anterior


# ---------------------------------------------------------------- eventos
def buscar_evento_aberto(conn: sqlite3.Connection, tag: str) -> sqlite3.Row | None:
    marcas = ",".join("?" * len(ABERTOS))
    return conn.execute(
        f"SELECT * FROM eventos_operacionais WHERE tag_ativo = ? AND status_resolucao IN ({marcas}) "
        "ORDER BY id DESC LIMIT 1", (tag, *ABERTOS)).fetchone()


def registrar_transicao(conn: sqlite3.Connection, evento_id: int, de: str | None, para: str, acao: str,
                        ator: str, observacao: str = "", ativo_de: str | None = None,
                        ativo_para: str | None = None, run_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO historico_eventos (evento_id, status_anterior, status_novo, acao, ator, observacao, "
        "status_ativo_anterior, status_ativo_novo, run_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (evento_id, de, para, acao, ator, observacao, ativo_de, ativo_para, run_id))
    conn.execute("UPDATE eventos_operacionais SET status_resolucao = ?, atualizado_em = CURRENT_TIMESTAMP "
                 "WHERE id = ?", (para, evento_id))
    registrar_auditoria_encadeada(conn, "eventos_operacionais", evento_id, acao.upper(), ator,
                                  {"de": de, "para": para, "observacao": observacao, "run_id": run_id})


def abrir_evento(conn: sqlite3.Connection, *, tag: str, codigo_motor: str, severidade: str, descricao: str,
                 rec: Recomendacao, leitura_id: int | None, run_id: str,
                 status_ativo: tuple[str | None, str | None] = (None, None)) -> int:
    cur = conn.execute(
        """INSERT INTO eventos_operacionais
           (tag_ativo, codigo_motor, tipo_evento, severidade, descricao_anomalia, diagnostico_ia,
            acao_recomendada, status_resolucao, leitura_id, ocorrencias, ciclos_normais,
            procedimentos_json, referencias_json, origem_recomendacao, prioridade, prazo_horas,
            run_id, atualizado_em)
           VALUES (?,?,?,?,?,?,?,?,?,1,0,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (tag, codigo_motor, "ANALISE_IA", severidade, descricao, rec.diagnostico, rec.acao_recomendada,
         "pendente", leitura_id, json.dumps(rec.procedimentos, ensure_ascii=False),
         json.dumps(rec.referencias, ensure_ascii=False), rec.origem, rec.prioridade, rec.prazo_horas, run_id))
    evento_id = int(cur.lastrowid)
    registrar_transicao(conn, evento_id, None, "pendente", "abertura", ATOR_RPA,
                        f"Evento aberto ({severidade}): {descricao}", status_ativo[0], status_ativo[1], run_id)
    return evento_id


def abrir_ordem_manutencao(conn: sqlite3.Connection, motor_id: int, evento_id: int, severidade: str,
                           rec: Recomendacao) -> int:
    tipo = "corretiva" if severidade == "CRITICO" else "preventiva"
    descricao = f"{rec.acao_recomendada} (origem: {rec.origem}; evento #{evento_id})"
    cur = conn.execute(
        "INSERT INTO manutencoes (motor_id, tipo, status, prioridade, descricao, data_prevista, evento_id) "
        "VALUES (?, ?, 'pendente', ?, ?, datetime('now', ?), ?)",
        (motor_id, tipo, rec.prioridade, descricao, f"+{rec.prazo_horas} hours", evento_id))
    return int(cur.lastrowid)


def encaminhar_evento(conn: sqlite3.Connection, evento_id: int, manutencao_id: int, destino: str,
                      run_id: str | None = None) -> None:
    atual = conn.execute("SELECT status_resolucao FROM eventos_operacionais WHERE id = ?", (evento_id,)).fetchone()
    conn.execute("UPDATE eventos_operacionais SET manutencao_id = ?, encaminhado_para = ? WHERE id = ?",
                 (manutencao_id, destino, evento_id))
    registrar_transicao(conn, evento_id, atual["status_resolucao"], "encaminhado", "encaminhamento", ATOR_RPA,
                        f"Ordem de manutenção #{manutencao_id} gerada e encaminhada a: {destino}", run_id=run_id)


def registrar_recorrencia(conn: sqlite3.Connection, evento_id: int) -> None:
    """A anomalia continua: apenas conta a ocorrência (descrição e leitura de origem ficam intactas)."""
    conn.execute("UPDATE eventos_operacionais SET ocorrencias = COALESCE(ocorrencias,1) + 1, ciclos_normais = 0, "
                 "atualizado_em = CURRENT_TIMESTAMP WHERE id = ?", (evento_id,))


def escalar_evento(conn: sqlite3.Connection, evento: sqlite3.Row, nova_sev: str, descricao: str,
                   rec: Recomendacao, leitura_id: int | None, run_id: str, status_ativo: tuple[str | None, str | None]) -> None:
    conn.execute(
        """UPDATE eventos_operacionais SET severidade = ?, descricao_anomalia = ?, diagnostico_ia = ?,
           acao_recomendada = ?, procedimentos_json = ?, referencias_json = ?, origem_recomendacao = ?,
           prioridade = ?, prazo_horas = ?, leitura_id = ?, ocorrencias = COALESCE(ocorrencias,1) + 1,
           ciclos_normais = 0 WHERE id = ?""",
        (nova_sev, descricao, rec.diagnostico, rec.acao_recomendada,
         json.dumps(rec.procedimentos, ensure_ascii=False), json.dumps(rec.referencias, ensure_ascii=False),
         rec.origem, rec.prioridade, rec.prazo_horas, leitura_id, evento["id"]))
    registrar_transicao(conn, evento["id"], evento["status_resolucao"], evento["status_resolucao"], "escalonamento",
                        ATOR_RPA, f"Severidade {evento['severidade']} -> {nova_sev}. {descricao}",
                        status_ativo[0], status_ativo[1], run_id)


def reclassificar_evento(conn: sqlite3.Connection, evento: sqlite3.Row, nova_sev: str, descricao: str,
                         leitura_id: int | None, run_id: str, status_ativo: tuple[str | None, str | None]) -> None:
    conn.execute("UPDATE eventos_operacionais SET severidade = ?, descricao_anomalia = ?, leitura_id = ?, "
                 "ocorrencias = COALESCE(ocorrencias,1) + 1, ciclos_normais = 0 WHERE id = ?",
                 (nova_sev, descricao, leitura_id, evento["id"]))
    registrar_transicao(conn, evento["id"], evento["status_resolucao"], evento["status_resolucao"], "reclassificacao",
                        ATOR_RPA, f"Severidade {evento['severidade']} -> {nova_sev}. {descricao}",
                        status_ativo[0], status_ativo[1], run_id)


def contar_normalidade(conn: sqlite3.Connection, evento_id: int) -> int:
    conn.execute("UPDATE eventos_operacionais SET ciclos_normais = COALESCE(ciclos_normais,0) + 1, "
                 "atualizado_em = CURRENT_TIMESTAMP WHERE id = ?", (evento_id,))
    return int(conn.execute("SELECT ciclos_normais FROM eventos_operacionais WHERE id = ?", (evento_id,)).fetchone()[0])


def resolver_evento(conn: sqlite3.Connection, evento: sqlite3.Row, resolucao: str, ator: str,
                    status_ativo: tuple[str | None, str | None], run_id: str | None = None) -> None:
    conn.execute("UPDATE eventos_operacionais SET resolucao = ?, encerrado_em = CURRENT_TIMESTAMP, "
                 "encerrado_por = ? WHERE id = ?", (resolucao, ator, evento["id"]))
    registrar_transicao(conn, evento["id"], evento["status_resolucao"], "resolvido", "resolucao", ator, resolucao,
                        status_ativo[0], status_ativo[1], run_id)
    if evento["manutencao_id"]:
        conn.execute("UPDATE manutencoes SET status = 'concluida', data_conclusao = CURRENT_TIMESTAMP, "
                     "atualizado_em = CURRENT_TIMESTAMP WHERE id = ? AND status != 'concluida'",
                     (evento["manutencao_id"],))


# ---------------------------------------------------------------- ações humanas
def _ativo_do_evento(conn: sqlite3.Connection, tag: str) -> sqlite3.Row:
    r = conn.execute("SELECT motor_id, status_operacional FROM associacoes_ativos WHERE tag = ?", (tag,)).fetchone()
    if r is None:
        raise ValueError(f"TAG não encontrada: {tag}")
    return r


def assumir_evento(tag: str, tecnico: str, observacao: str = "", run_id: str | None = None) -> int:
    """Técnico assume o atendimento: evento em_atendimento e ativo em 'manutencao'."""
    with get_connection() as conn:
        ev = buscar_evento_aberto(conn, tag)
        if ev is None:
            raise ValueError(f"Não há evento aberto para {tag}")
        ativo = _ativo_do_evento(conn, tag)
        novo = atualizar_status_ativo(conn, ativo["motor_id"], tag, "manutencao", f"tecnico:{tecnico}",
                                      "Atendimento iniciado", run_id)
        if ev["manutencao_id"]:
            conn.execute("UPDATE manutencoes SET status = 'em_andamento', tecnico = ?, atualizado_em = CURRENT_TIMESTAMP "
                         "WHERE id = ?", (tecnico, ev["manutencao_id"]))
        registrar_transicao(conn, ev["id"], ev["status_resolucao"], "em_atendimento", "atendimento", f"tecnico:{tecnico}",
                            observacao or "Atendimento iniciado em campo", novo, "manutencao", run_id)
        return int(ev["id"])


def concluir_evento(tag: str, tecnico: str, resolucao: str, run_id: str | None = None) -> int:
    """Técnico registra a resolução: evento resolvido, OS concluída e ativo volta a operacional."""
    with get_connection() as conn:
        ev = buscar_evento_aberto(conn, tag)
        if ev is None:
            raise ValueError(f"Não há evento aberto para {tag}")
        ativo = _ativo_do_evento(conn, tag)
        anterior = atualizar_status_ativo(conn, ativo["motor_id"], tag, "operacional", f"tecnico:{tecnico}",
                                          "Resolução registrada pelo técnico", run_id)
        resolver_evento(conn, ev, f"Resolvido por {tecnico}: {resolucao}", f"tecnico:{tecnico}",
                        (anterior, "operacional"), run_id)
        return int(ev["id"])

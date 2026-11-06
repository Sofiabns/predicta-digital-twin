"""Ferramentas de resiliência: nova tentativa, disjuntor e execução de etapas.

A ideia central é que uma falha pontual (arquivo ruim, API fora do ar, IA
indisponível) seja registrada e contornada, sem derrubar o ciclo inteiro.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from src.integracao.log_estruturado import LogEstruturado


def com_retry(
    funcao: Callable[[], Any],
    *,
    tentativas: int = 3,
    espera_s: float = 1.0,
    fator: float = 2.0,
    excecoes: tuple[type[BaseException], ...] = (Exception,),
    nome: str = "operacao",
    log: LogEstruturado | None = None,
    etapa: str = "resiliencia",
) -> Any:
    """Executa `funcao` com novas tentativas e espera crescente.

    Levanta a última exceção caso todas as tentativas falhem.
    """
    tentativas = max(1, tentativas)
    ultima: BaseException | None = None
    for n in range(1, tentativas + 1):
        try:
            return funcao()
        except excecoes as exc:  # noqa: PERF203
            ultima = exc
            if log:
                log.aviso(
                    etapa, "retry",
                    f"{nome}: tentativa {n}/{tentativas} falhou ({exc})",
                    tentativa=n, erro=str(exc),
                )
            if n < tentativas:
                time.sleep(espera_s * (fator ** (n - 1)))
    assert ultima is not None
    raise ultima


class Disjuntor:
    """Pausa temporariamente um recurso que falha de forma repetida.

    Usado para a IA local: se o Ollama não responde, as próximas chamadas são
    puladas por um tempo em vez de travar cada ciclo esperando timeout.
    """

    def __init__(self, limite_falhas: int = 2, pausa_s: float = 120.0):
        self.limite_falhas = limite_falhas
        self.pausa_s = pausa_s
        self.falhas = 0
        self._aberto_ate = 0.0

    def permitido(self) -> bool:
        return time.monotonic() >= self._aberto_ate

    @property
    def aberto(self) -> bool:
        return not self.permitido()

    def sucesso(self) -> None:
        self.falhas = 0
        self._aberto_ate = 0.0

    def falha(self) -> None:
        self.falhas += 1
        if self.falhas >= self.limite_falhas:
            self._aberto_ate = time.monotonic() + self.pausa_s


@dataclass
class EtapaResultado:
    nome: str
    status: str = "ok"            # ok | degradado | falha
    duracao_ms: int = 0
    detalhes: dict[str, Any] = field(default_factory=dict)
    erro: str | None = None


def executar_etapa(
    nome: str,
    funcao: Callable[[], dict[str, Any] | None],
    log: LogEstruturado,
) -> EtapaResultado:
    """Roda uma etapa do ciclo isolando qualquer exceção.

    A função pode devolver um dicionário de detalhes. Se esse dicionário trouxer
    a chave `degradado`, a etapa é marcada como degradada (concluiu com ressalvas).
    """
    resultado = EtapaResultado(nome=nome)
    inicio = time.perf_counter()
    log.info(nome, "inicio", f"Etapa '{nome}' iniciada")
    try:
        detalhes = funcao() or {}
        resultado.detalhes = detalhes
        if detalhes.get("degradado"):
            resultado.status = "degradado"
    except Exception as exc:  # noqa: BLE001 - a etapa nunca pode derrubar o ciclo
        resultado.status = "falha"
        resultado.erro = f"{type(exc).__name__}: {exc}"
        log.erro(
            nome, "excecao", f"Etapa '{nome}' falhou: {resultado.erro}",
            traceback=traceback.format_exc(limit=4),
        )
    resultado.duracao_ms = int((time.perf_counter() - inicio) * 1000)
    nivel = {"ok": "INFO", "degradado": "WARNING", "falha": "ERROR"}[resultado.status]
    log.registrar(
        nivel, nome, "fim", f"Etapa '{nome}' terminou com status {resultado.status}",
        duracao_ms=resultado.duracao_ms, **{k: v for k, v in resultado.detalhes.items() if k != "degradado"},
    )
    return resultado

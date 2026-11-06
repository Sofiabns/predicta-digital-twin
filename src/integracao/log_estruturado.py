"""Log estruturado em JSON Lines.

Cada linha do arquivo é um objeto JSON independente, o que facilita auditar
uma execução (filtrar por run_id, ciclo, etapa ou ativo) e importar o
resultado em pandas ou em qualquer ferramenta de observabilidade.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

_console = logging.getLogger("predicta.rpa")


class LogEstruturado:
    """Grava eventos da automação em arquivo .jsonl e espelha no console."""

    def __init__(self, caminho: Path, run_id: str):
        self.caminho = Path(caminho)
        self.run_id = run_id
        self.ciclo: int | None = None
        self._trava = threading.Lock()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)

    def registrar(
        self,
        nivel: str,
        etapa: str,
        evento: str,
        mensagem: str = "",
        *,
        ativo: str | None = None,
        duracao_ms: int | None = None,
        **dados: Any,
    ) -> dict[str, Any]:
        linha: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "ciclo": self.ciclo,
            "nivel": nivel.upper(),
            "etapa": etapa,
            "evento": evento,
            "mensagem": mensagem,
        }
        if ativo:
            linha["ativo"] = ativo
        if duracao_ms is not None:
            linha["duracao_ms"] = duracao_ms
        if dados:
            linha["dados"] = dados

        texto = json.dumps(linha, ensure_ascii=False, default=str)
        with self._trava:
            with self.caminho.open("a", encoding="utf-8") as f:
                f.write(texto + "\n")

        nivel_py = getattr(logging, nivel.upper(), logging.INFO)
        prefixo = f"[ciclo {self.ciclo}] " if self.ciclo is not None else ""
        alvo = f" ({ativo})" if ativo else ""
        _console.log(nivel_py, "%s%s/%s%s %s", prefixo, etapa, evento, alvo, mensagem)
        return linha

    def info(self, etapa: str, evento: str, mensagem: str = "", **kw: Any) -> dict[str, Any]:
        return self.registrar("INFO", etapa, evento, mensagem, **kw)

    def aviso(self, etapa: str, evento: str, mensagem: str = "", **kw: Any) -> dict[str, Any]:
        return self.registrar("WARNING", etapa, evento, mensagem, **kw)

    def erro(self, etapa: str, evento: str, mensagem: str = "", **kw: Any) -> dict[str, Any]:
        return self.registrar("ERROR", etapa, evento, mensagem, **kw)


def ler_log(caminho: Path, run_id: str | None = None) -> list[dict[str, Any]]:
    """Lê um arquivo .jsonl (ignorando linhas corrompidas) e filtra por run_id."""
    registros: list[dict[str, Any]] = []
    caminho = Path(caminho)
    if not caminho.exists():
        return registros
    with caminho.open("r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                obj = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if run_id is None or obj.get("run_id") == run_id:
                registros.append(obj)
    return registros

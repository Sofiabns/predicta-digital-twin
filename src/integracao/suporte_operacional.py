"""Suporte operacional: transforma um alerta em uma recomendação técnica.

Fluxo:
  1. cruza os desvios detectados com a base de conhecimento (manuais) e com o
     catálogo do modelo do motor;
  2. monta os procedimentos corretivos e preventivos (playbook);
  3. se o Ollama estiver disponível, pede um texto de diagnóstico mais fluido;
     se não estiver, gera o texto a partir das regras e dos trechos recuperados.

O resultado informa de onde veio a recomendação (`origem`), para que a equipe
saiba o quanto confiar e como auditar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

from src.analise.base_conhecimento import BaseConhecimento
from src.integracao.avaliacao import Avaliacao
from src.integracao.config import Config
from src.integracao.playbook import CAUSAS, CONSULTA_RAG, passos_para
from src.integracao.resiliencia import Disjuntor

logger = logging.getLogger(__name__)

# Compartilhado entre ciclos: evita esperar timeout da IA a cada ativo
_DISJUNTOR_LLM = Disjuntor(limite_falhas=2, pausa_s=180.0)


@dataclass
class Recomendacao:
    diagnostico: str
    acao_recomendada: str
    procedimentos: list[dict[str, Any]] = field(default_factory=list)
    referencias: list[dict[str, Any]] = field(default_factory=list)
    origem: str = "regras+rag"           # llm+rag | regras+rag | regras
    prioridade: str = "media"
    prazo_horas: int = 72

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


class SuporteOperacional:
    def __init__(self, cfg: Config | None = None, base: BaseConhecimento | None = None):
        self.cfg = cfg or Config.carregar()
        self._base = base

    @property
    def base(self) -> BaseConhecimento | None:
        if self._base is None:
            try:
                self._base = BaseConhecimento()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Base de conhecimento indisponível: %s", exc)
        return self._base

    # ------------------------------------------------------------------
    def recomendar(
        self,
        av: Avaliacao,
        *,
        tag: str,
        modelo: str | None = None,
        limites_fonte: str = "padrao",
        guia_catalogo: str | None = None,
    ) -> Recomendacao:
        tipos = av.tipos
        passos = passos_para(tipos)
        procedimentos = [
            {"ordem": i, "tipo": p.tipo, "descricao": p.descricao, "referencia": p.referencia}
            for i, p in enumerate(passos, 1)
        ]

        # 1. Recuperação na base técnica (se falhar, segue só com as regras)
        referencias: list[dict[str, Any]] = []
        trechos_texto: list[str] = []
        origem = "regras"
        if self.base is not None:
            try:
                consulta = " ".join(CONSULTA_RAG[t] for t in sorted(tipos) if t in CONSULTA_RAG)
                if {"temperatura", "vibracao"} <= tipos:
                    consulta += " temperatura e vibração simultâneas lubrificação mancais"
                for t in self.base.buscar_trechos(consulta, top_k=3, colecao="manuais"):
                    referencias.append({"fonte": t.fonte, "secao": t.secao, "trecho": t.texto[:280]})
                    trechos_texto.append(t.texto)
                if referencias:
                    origem = "regras+rag"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Falha na busca de manuais: %s", exc)

        if guia_catalogo:
            referencias.append({"fonte": "catalogo_especificacoes_externas", "secao": modelo or "",
                                "trecho": f"Guia do fabricante: {guia_catalogo[:200]}"})

        # 2. Texto de diagnóstico e ação
        diagnostico, acao = self._texto_por_regras(av, tag, modelo, limites_fonte)
        if self._llm_liberado():
            texto = self._consultar_llm(av, tag, passos, trechos_texto)
            if texto:
                diagnostico, acao = texto
                origem = "llm+rag" if referencias else "llm"

        critico = av.severidade == "CRITICO"
        return Recomendacao(
            diagnostico=diagnostico,
            acao_recomendada=acao,
            procedimentos=procedimentos,
            referencias=referencias,
            origem=origem,
            prioridade="urgente" if critico else "media",
            prazo_horas=self.cfg.prazo_critico_h if critico else self.cfg.prazo_alerta_h,
        )

    # ------------------------------------------------------------------
    def _texto_por_regras(self, av: Avaliacao, tag: str, modelo: str | None, fonte: str) -> tuple[str, str]:
        tipos = av.tipos
        partes = [f"Ativo {tag}" + (f" ({modelo})" if modelo else "") + ": " + av.descricao]
        if {"temperatura", "vibracao"} <= tipos:
            partes.append(
                "Temperatura e vibração elevadas ao mesmo tempo apontam, segundo o manual, para sobrecarga "
                "combinada com desalinhamento ou falta de lubrificação nos mancais."
            )
        else:
            partes.extend(CAUSAS[t] for t in sorted(tipos) if t in CAUSAS)
        if fonte == "padrao":
            partes.append("O modelo não consta no catálogo; foram usados os limites padrão do manual.")
        diagnostico = " ".join(partes)

        passos = passos_para(tipos)
        primeiros = [p.descricao for p in passos if p.tipo == "corretivo"][:2]
        if av.severidade == "CRITICO":
            acao = "Atuar com prioridade: " + " ".join(primeiros)
        else:
            acao = "Programar a intervenção dentro do prazo: " + " ".join(primeiros)
        return diagnostico, acao

    def _llm_liberado(self) -> bool:
        if self.cfg.usar_llm in ("nao", "não", "0", "false"):
            return False
        return _DISJUNTOR_LLM.permitido()

    def _consultar_llm(self, av: Avaliacao, tag: str, passos, trechos: list[str]) -> tuple[str, str] | None:
        prompt = (
            "Você é um engenheiro de manutenção de motores elétricos industriais.\n"
            f"Ativo: {tag}\nDesvios detectados: {av.descricao}\n"
            "Importante: fale somente dos desvios listados acima. Não mencione grandezas que estão normais "
            "e não use procedimentos de outro tipo de falha. Escreva em texto simples, sem negrito.\n\n"
            "Trechos do manual técnico:\n" + "\n---\n".join(trechos[:3]) + "\n\n"
            "Procedimentos previstos:\n" + "\n".join(f"- {p.descricao}" for p in passos) + "\n\n"
            "Responda em português, exatamente neste formato:\n"
            "Diagnóstico: <causa provável em até 3 frases, baseada nos trechos>\n"
            "Ação Recomendada: <o que a equipe deve fazer primeiro, em até 3 frases>"
        )
        try:
            import ollama  # import tardio: biblioteca opcional

            cliente = ollama.Client(timeout=self.cfg.ollama_timeout_s)
            resp = cliente.chat(model=self.cfg.ollama_modelo, messages=[{"role": "user", "content": prompt}])
            texto = (resp.get("message", {}) or {}).get("content", "") if isinstance(resp, dict) else resp.message.content
            if "Ação Recomendada:" not in texto:
                raise ValueError("resposta da IA fora do formato esperado")
            diag, acao = texto.split("Ação Recomendada:", 1)
            _DISJUNTOR_LLM.sucesso()
            limpar = lambda t: t.replace("**", "").replace("Diagnóstico:", "").strip()
            return limpar(diag), limpar(acao)
        except Exception as exc:  # noqa: BLE001 - qualquer falha cai no texto por regras
            _DISJUNTOR_LLM.falha()
            logger.warning("IA generativa indisponível (%s). Usando recomendação por regras.", type(exc).__name__)
            return None

"""Regras de negócio: classifica a leitura de um ativo.

É a única fonte das regras de severidade usada pela automação, pelo motor de
decisão e pelos testes. Parâmetros vêm do catálogo/placa do motor (limites) e
da configuração (tolerâncias).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.integracao.config import Config

ORDEM = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}


@dataclass
class Desvio:
    tipo: str          # temperatura | vibracao | corrente | tensao
    severidade: str    # ALERTA | CRITICO
    valor: float
    limite: float
    texto: str


@dataclass
class Avaliacao:
    severidade: str = "NORMAL"
    desvios: list[Desvio] = field(default_factory=list)

    @property
    def tipos(self) -> set[str]:
        return {d.tipo for d in self.desvios}

    @property
    def descricao(self) -> str:
        return " ".join(d.texto for d in self.desvios) if self.desvios else "Sem anomalias."


def zona_iso_10816(vib: float) -> str:
    """Zona de severidade de vibração (ISO 10816-3, conforme manual do projeto)."""
    if vib < 1.5:
        return "A"
    if vib < 2.8:
        return "B"
    if vib <= 4.5:
        return "C"
    return "D"


def _sev(valor: float, limite: float, alerta: float) -> str | None:
    if valor > limite:
        return "CRITICO"
    if valor >= alerta * limite:
        return "ALERTA"
    return None


def avaliar_leitura(
    leitura: dict[str, Any],
    *,
    temp_max: float,
    vib_max: float,
    corrente_nominal: float | None = None,
    tensao_nominal: float | None = None,
    cfg: Config | None = None,
) -> Avaliacao:
    """Compara a leitura com os limites e devolve severidade e desvios."""
    cfg = cfg or Config.carregar()
    av = Avaliacao()

    def registrar(d: Desvio) -> None:
        av.desvios.append(d)
        if ORDEM[d.severidade] > ORDEM[av.severidade]:
            av.severidade = d.severidade

    temp = leitura.get("temperatura")
    if temp is not None:
        s = _sev(float(temp), temp_max, cfg.limiar_alerta)
        if s:
            rel = "excede o limite" if s == "CRITICO" else "está próxima do limite"
            registrar(Desvio("temperatura", s, float(temp), temp_max,
                             f"Temperatura {float(temp):.1f}°C {rel} de {temp_max:g}°C."))

    vib = leitura.get("vibracao")
    if vib is not None:
        s = _sev(float(vib), vib_max, cfg.limiar_alerta)
        if s:
            rel = "excede o limite" if s == "CRITICO" else "está próxima do limite"
            registrar(Desvio("vibracao", s, float(vib), vib_max,
                             f"Vibração {float(vib):.2f} mm/s {rel} de {vib_max:g} mm/s "
                             f"(zona {zona_iso_10816(float(vib))} da ISO 10816-3)."))

    corrente = leitura.get("corrente")
    if corrente is not None and corrente_nominal:
        limite = corrente_nominal * cfg.corrente_fator_limite
        s = _sev(float(corrente), limite, cfg.limiar_alerta)
        if s:
            rel = "excede" if s == "CRITICO" else "está próxima de"
            registrar(Desvio("corrente", s, float(corrente), limite,
                             f"Corrente {float(corrente):.1f} A {rel} {limite:.1f} A "
                             f"(nominal {corrente_nominal:g} A + {int((cfg.corrente_fator_limite - 1) * 100)}%)."))

    tensao = leitura.get("tensao")
    if tensao is not None and tensao_nominal:
        desvio = abs(float(tensao) - tensao_nominal) / tensao_nominal
        s = "CRITICO" if desvio > cfg.tensao_tol_critica else ("ALERTA" if desvio > cfg.tensao_tol_alerta else None)
        if s:
            faixa = f"{tensao_nominal * (1 - cfg.tensao_tol_alerta):.0f}–{tensao_nominal * (1 + cfg.tensao_tol_alerta):.0f} V"
            registrar(Desvio("tensao", s, float(tensao), tensao_nominal,
                             f"Tensão {float(tensao):.1f} V fora da faixa de {faixa} "
                             f"(desvio de {desvio * 100:.1f}% sobre a nominal de {tensao_nominal:g} V)."))
    return av

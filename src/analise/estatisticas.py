"""Funcoes estatisticas para deteccao de anomalias."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ResumoEstatistico:
    """Resumo estatistico de uma serie numerica."""

    n: int
    media: float
    desvio: float
    minimo: float
    maximo: float
    q1: float
    mediana: float
    q3: float

    @property
    def iqr(self) -> float:
        """Intervalo interquartil (Q3 - Q1)."""
        return self.q3 - self.q1

    @property
    def limite_inferior_iqr(self) -> float:
        """Limite inferior pelo metodo IQR (Q1 - 1.5 * IQR)."""
        return self.q1 - 1.5 * self.iqr

    @property
    def limite_superior_iqr(self) -> float:
        """Limite superior pelo metodo IQR (Q3 + 1.5 * IQR)."""
        return self.q3 + 1.5 * self.iqr


def calcular_resumo(valores: Iterable[float]) -> ResumoEstatistico:
    """Calcula resumo estatistico completo de uma serie."""
    lista = [float(v) for v in valores if v is not None]
    n = len(lista)

    if n == 0:
        return ResumoEstatistico(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    if n == 1:
        v = lista[0]
        return ResumoEstatistico(1, v, 0.0, v, v, v, v, v)

    ordenada = sorted(lista)
    media = statistics.mean(lista)
    desvio = statistics.stdev(lista) if n >= 2 else 0.0

    q1 = _percentil(ordenada, 25)
    mediana = _percentil(ordenada, 50)
    q3 = _percentil(ordenada, 75)

    return ResumoEstatistico(
        n=n,
        media=media,
        desvio=desvio,
        minimo=ordenada[0],
        maximo=ordenada[-1],
        q1=q1,
        mediana=mediana,
        q3=q3,
    )


def _percentil(ordenada: list[float], p: float) -> float:
    """Calcula percentil usando interpolacao linear."""
    if not ordenada:
        return 0.0
    k = (len(ordenada) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordenada) - 1)
    if f == c:
        return ordenada[f]
    return ordenada[f] + (ordenada[c] - ordenada[f]) * (k - f)


def z_score(valor: float, media: float, desvio: float) -> float:
    """Calcula Z-score: (valor - media) / desvio."""
    if desvio == 0:
        return 0.0
    return (valor - media) / desvio


def eh_outlier_iqr(valor: float, resumo: ResumoEstatistico) -> bool:
    """Verifica se o valor e outlier pelo metodo IQR."""
    return valor < resumo.limite_inferior_iqr or valor > resumo.limite_superior_iqr


def eh_outlier_zscore(valor: float, resumo: ResumoEstatistico, limiar: float = 3.0) -> bool:
    """Verifica se o valor e outlier pelo Z-score."""
    z = z_score(valor, resumo.media, resumo.desvio)
    return abs(z) > limiar

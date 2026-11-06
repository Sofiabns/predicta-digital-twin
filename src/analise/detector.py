"""Detector de anomalias com limiares calibrados + deteccao estatistica."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.analise.estatisticas import ResumoEstatistico, z_score

Classe = Literal["normal", "alerta", "critico"]
Severidade = Literal["baixa", "media", "alta", "critica"]
TipoAnomalia = Literal["temperatura", "vibracao", "outlier_estatistico"]

LIMIAR_ZSCORE = 3.0          # desvios padrao para outlier

@dataclass(frozen=True)
class AnomaliaDetectada:
    """Representa uma anomalia detectada pronta para persistencia."""
    motor_id: int
    leitura_id: int
    tipo: TipoAnomalia
    severidade: Severidade
    valor_medido: float
    valor_limite: float
    descricao: str

@dataclass(frozen=True)
class ResultadoAnalise:
    """Resultado completo da analise de uma leitura."""
    leitura_id: int
    motor_id: int
    classe_detectada: Classe
    anomalias: list[AnomaliaDetectada]
    z_score_temp: float
    z_score_vib: float

def classificar(temperatura: float, vibracao: float, temp_max: float, vib_max: float) -> Classe:
    """Classifica a leitura em normal/alerta/critico."""
    if vibracao > vib_max or temperatura > temp_max:
        return "critico"
    if vibracao >= 0.9 * vib_max or temperatura >= 0.9 * temp_max:
        return "alerta"
    return "normal"

def _severidade(valor: float, limite: float) -> Severidade:
    """Mapeia valor para severidade textual."""
    if valor > limite:
        return "critica"
    if valor >= 0.9 * limite:
        return "alta"
    return "media"

def analisar_leitura(
    leitura_id: int,
    motor_id: int,
    temperatura: float,
    vibracao: float,
    temp_max: float,
    vib_max: float,
    resumo_temp: ResumoEstatistico,
    resumo_vib: ResumoEstatistico,
) -> ResultadoAnalise:
    """Analisa uma leitura: classifica e gera lista de anomalias."""
    classe = classificar(temperatura, vibracao, temp_max, vib_max)
    z_temp = z_score(temperatura, resumo_temp.media, resumo_temp.desvio)
    z_vib = z_score(vibracao, resumo_vib.media, resumo_vib.desvio)

    anomalias: list[AnomaliaDetectada] = []

    if temperatura >= 0.9 * temp_max:
        anomalias.append(AnomaliaDetectada(
            motor_id=motor_id,
            leitura_id=leitura_id,
            tipo="temperatura",
            severidade=_severidade(temperatura, temp_max),
            valor_medido=round(temperatura, 2),
            valor_limite=temp_max,
            descricao=f"Temperatura {temperatura:.2f}C em zona de alerta/crítica (Limite {temp_max}C)",
        ))

    if vibracao >= 0.9 * vib_max:
        anomalias.append(AnomaliaDetectada(
            motor_id=motor_id,
            leitura_id=leitura_id,
            tipo="vibracao",
            severidade=_severidade(vibracao, vib_max),
            valor_medido=round(vibracao, 2),
            valor_limite=vib_max,
            descricao=f"Vibracao {vibracao:.2f} mm/s em zona de alerta/crítica (Limite {vib_max})",
        ))

    return ResultadoAnalise(
        leitura_id=leitura_id,
        motor_id=motor_id,
        classe_detectada=classe,
        anomalias=anomalias,
        z_score_temp=round(z_temp, 3),
        z_score_vib=round(z_vib, 3),
    )
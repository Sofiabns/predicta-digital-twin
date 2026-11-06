"""Simulador de telemetria dos motores (substitui os sensores IoT).

Grava um CSV `leituras_<CODIGO>.csv` por motor na pasta de entrada, no mesmo
formato dos arquivos de exemplo. Dois modos:

* ``cenario``   - roteiro determinístico (usado na demonstração e nas evidências)
* ``aleatorio`` - caminhada aleatória com degradação do MTR-001 (modo contínuo)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# (temperatura, vibração) em operação normal
BASE = {
    "MTR-001": (72.0, 1.8),
    "MTR-002": (70.0, 1.7),
    "MTR-003": (65.0, 1.2),
    "MTR-004": (65.0, 1.2),
    "MTR-005": (65.0, 1.2),
}

# Roteiro: ciclo -> {motor: {campo: valor}}. Fora dessas entradas o motor opera normalmente.
CENARIO: dict[int, dict[str, dict[str, float]]] = {
    1: {"MTR-001": {"temperatura": 88.9, "vibracao": 5.06}},
    2: {"MTR-001": {"temperatura": 89.4, "vibracao": 5.12}},
    3: {"MTR-001": {"temperatura": 89.8, "vibracao": 5.18},
        "MTR-002": {"temperatura": 80.2}},
    4: {"MTR-001": {"temperatura": 88.6, "vibracao": 5.01}},
    5: {"MTR-004": {"vibracao": 2.31}},
    6: {"MTR-004": {"temperatura": 71.0, "vibracao": 2.78}},
    7: {"MTR-004": {"vibracao": 2.71}},
    9: {"MTR-005": {"tensao": 352.0}},
    10: {"MTR-005": {"tensao": 350.0}},
}


class SimuladorTelemetria:
    def __init__(self, pasta_saida: Path, modo: str = "cenario", semente: int = 42):
        self.pasta = Path(pasta_saida)
        self.modo = modo
        self.rng = np.random.default_rng(semente)
        self.estado = {k: {"temp": v[0], "vib": v[1]} for k, v in BASE.items()}
        self.sem_telemetria: dict[int, set[str]] = {}     # ciclo -> motores sem arquivo
        self.arquivos_corrompidos: dict[int, set[str]] = {}
        self.motores_desconhecidos: dict[int, list[str]] = {}

    def gerar(self, ciclo: int, momento: datetime) -> list[str]:
        self.pasta.mkdir(parents=True, exist_ok=True)
        ts = momento.strftime("%Y-%m-%d %H:%M:%S")
        gerados: list[str] = []
        for codigo in BASE:
            if codigo in self.sem_telemetria.get(ciclo, set()):
                continue
            if codigo in self.arquivos_corrompidos.get(ciclo, set()):
                (self.pasta / f"leituras_{codigo}.csv").write_text(
                    "sensor;falha\n@@@;leitura ilegivel\n", encoding="utf-8")
                gerados.append(f"leituras_{codigo}.csv (corrompido)")
                continue
            temp, vib, corr, rpm, tensao = self._valores(codigo, ciclo)
            df = pd.DataFrame({
                "timestamp": [ts], "temperatura_C": [round(temp, 2)], "vibracao_mm_s": [round(vib, 2)],
                "corrente_A": [round(corr, 2)], "rpm": [round(rpm, 0)], "tensao_V": [round(tensao, 2)],
                "label_anomalia": [0], "classe_manutencao": ["normal"],
            })
            df.to_csv(self.pasta / f"leituras_{codigo}.csv", index=False)
            gerados.append(f"leituras_{codigo}.csv")
        for codigo in self.motores_desconhecidos.get(ciclo, []):
            pd.DataFrame({"timestamp": [ts], "temperatura_C": [70.0], "vibracao_mm_s": [1.5], "corrente_A": [15.0],
                          "rpm": [1750], "tensao_V": [380.0], "label_anomalia": [0],
                          "classe_manutencao": ["normal"]}).to_csv(self.pasta / f"leituras_{codigo}.csv", index=False)
            gerados.append(f"leituras_{codigo}.csv (motor não cadastrado)")
        return gerados

    def _valores(self, codigo: str, ciclo: int) -> tuple[float, float, float, float, float]:
        r = self.rng
        corr = r.normal(15, 0.8)
        rpm = r.normal(1750, 8)
        tensao = r.normal(380, 3)
        if self.modo == "aleatorio":
            e = self.estado[codigo]
            if codigo == "MTR-001":
                e["temp"] += r.normal(0.6, 0.2)
                e["vib"] += r.normal(0.12, 0.05)
                if e["temp"] > 95:                         # "manutenção" reinicia o ciclo de degradação
                    e["temp"], e["vib"] = BASE[codigo]
            else:
                e["temp"] += r.normal(0, 0.15)
                e["vib"] += r.normal(0, 0.02)
                e["temp"] = float(np.clip(e["temp"], BASE[codigo][0] - 4, BASE[codigo][0] + 4))
                e["vib"] = float(np.clip(e["vib"], BASE[codigo][1] - 0.3, BASE[codigo][1] + 0.3))
            return e["temp"], e["vib"], corr, rpm, tensao
        base_t, base_v = BASE[codigo]
        temp = base_t + r.normal(0, 0.8)
        vib = base_v + r.normal(0, 0.04)
        for campo, valor in CENARIO.get(ciclo, {}).get(codigo, {}).items():
            if campo == "temperatura":
                temp = valor
            elif campo == "vibracao":
                vib = valor
            elif campo == "tensao":
                tensao = valor
        return temp, vib, corr, rpm, tensao

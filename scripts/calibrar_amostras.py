"""
Script utilitário para gerar/calibrar as amostras de telemetria dos motores.
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"

def calibrar_amostras():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Parâmetros base
    start_time = datetime(2026, 8, 18, 8, 0, 0)
    
    def gerar_leituras(motor_code, num_leituras=1000):
        timestamps = [start_time + timedelta(minutes=10 * i) for i in range(num_leituras)]
        
        if motor_code == "MTR-001":
            # Nominal initial, degradando no final (ultimas 40)
            temp = np.random.normal(72, 1.5, num_leituras)
            vib = np.random.normal(1.8, 0.2, num_leituras)
            
            # Degradação
            degrad_idx = num_leituras - 40
            temp[degrad_idx:] = np.linspace(76, 88, 40) + np.random.normal(0, 0.5, 40)
            vib[degrad_idx:] = np.linspace(2.2, 4.8, 40) + np.random.normal(0, 0.1, 40)
            
        elif motor_code == "MTR-002":
            # Normal com picos de temperatura
            temp = np.random.normal(70, 2.0, num_leituras)
            vib = np.random.normal(1.5, 0.2, num_leituras)
            
            # Picos pontuais
            temp[300] = 82.5
            temp[600] = 81.9
            temp[900] = 83.1
            
        else:
            # Saudáveis
            temp = np.random.normal(65, 2.5, num_leituras)
            vib = np.random.normal(1.2, 0.3, num_leituras)
            
        df = pd.DataFrame({
            "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "temperatura_C": temp.round(2),
            "vibracao_mm_s": vib.round(2),
            "corrente_A": np.random.normal(15, 1, num_leituras).round(2),
            "rpm": np.random.normal(1750, 10, num_leituras).round(0),
            "tensao_V": np.random.normal(380, 5, num_leituras).round(2),
            "label_anomalia": 0,
            "classe_manutencao": "normal"
        })
        
        filepath = SAMPLES_DIR / f"leituras_{motor_code}.csv"
        df.to_csv(filepath, index=False)
        print(f"[OK] Calibrado: {filepath.name} com {num_leituras} linhas.")

    print("=" * 60)
    print("CALIBRANDO AMOSTRAS DE TELEMETRIA")
    print("=" * 60)
    for code in ["MTR-001", "MTR-002", "MTR-003", "MTR-004", "MTR-005"]:
        gerar_leituras(code, 1000)
    print("=" * 60)

if __name__ == "__main__":
    calibrar_amostras()

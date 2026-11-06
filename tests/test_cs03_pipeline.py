"""
Testes E2E e unitários para o CS03.
"""

import pytest
from src.analise.base_conhecimento import BaseConhecimento
from src.analise.motor_decisao import MotorDecisao

def test_base_conhecimento_inicializa():
    rag = BaseConhecimento()
    assert rag is not None
    # Como não temos garantia do conteúdo em CI puro, 
    # apenas validamos que a classe instancia sem quebrar.

def test_motor_decisao_normal():
    motor = MotorDecisao()
    leitura = {"temperatura": 50, "vibracao": 1.0}
    catalogo = {"temp_max_tolerada": 80, "vibracao_limite_rms": 2.5}
    
    res = motor.analisar_leitura(leitura, catalogo)
    assert res["severidade"] == "NORMAL"
    assert "sem anomalias" in res["descricao_anomalia"].lower()

def test_motor_decisao_alerta():
    motor = MotorDecisao()
    leitura = {"temperatura": 75, "vibracao": 1.0}
    catalogo = {"temp_max_tolerada": 80, "vibracao_limite_rms": 2.5}
    
    res = motor.analisar_leitura(leitura, catalogo)
    assert res["severidade"] == "ALERTA"
    assert "Temperatura" in res["descricao_anomalia"]

def test_motor_decisao_critico():
    motor = MotorDecisao()
    leitura = {"temperatura": 90, "vibracao": 3.0}
    catalogo = {"temp_max_tolerada": 80, "vibracao_limite_rms": 2.5}
    
    res = motor.analisar_leitura(leitura, catalogo)
    assert res["severidade"] == "CRITICO"
    assert "Temperatura" in res["descricao_anomalia"]
    assert "Vibração" in res["descricao_anomalia"]

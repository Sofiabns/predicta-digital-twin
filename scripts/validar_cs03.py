"""
Validador E2E para a CS03.
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.persistencia.database import get_connection

def testar():
    erros = 0
    print("="*60)
    print("VALIDAÇÃO PONTA-A-PONTA DA CS03")
    print("="*60)
    
    # 1. Checa as novas tabelas
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1 FROM catalogo_especificacoes_externas LIMIT 1")
            conn.execute("SELECT 1 FROM eventos_operacionais LIMIT 1")
            conn.execute("SELECT 1 FROM vw_painel_decisao_operacional LIMIT 1")
        print("[OK] Schema Banco de Dados")
    except sqlite3.OperationalError as e:
        print(f"[FAIL] Schema: {e}")
        erros += 1

    # 2. Testa import do MCP
    try:
        from src.mcp.mcp_server import mcp
        print("[OK] MCP Server")
    except Exception as e:
        print(f"[FAIL] MCP Server: {e}")
        erros += 1

    # 3. Testa RAG
    try:
        from src.analise.base_conhecimento import BaseConhecimento
        rag = BaseConhecimento()
        res = rag.buscar_contexto("temperatura", 1)
        if res is not None:
            print("[OK] Base de Conhecimento (FAISS + sentence-transformers)")
        else:
            print("[FAIL] FAISS retornou tipo inesperado.")
            erros += 1
    except Exception as e:
        print(f"[FAIL] Base de Conhecimento: {e}")
        erros += 1
        
    # 4. Testa Ollama (Motor Decisao)
    try:
        from src.analise.motor_decisao import MotorDecisao
        motor = MotorDecisao()
        leitura = {"temperatura": 90, "vibracao": 3.0}
        catalogo = {"temp_max_tolerada": 80, "vibracao_limite_rms": 2.5}
        # Se Ollama não estiver no SO host, lançará exception. Pegamos no log.
        res = motor.analisar_leitura(leitura, catalogo)
        print(f"[OK] Motor de Decisão -> Severidade {res.get('severidade')}")
    except Exception as e:
        print(f"[FAIL] Motor de Decisão / Ollama: {e}")
        erros += 1

    print("="*60)
    if erros == 0:
        print(">>> STATUS GERAL: [OK] Validado com sucesso.")
    else:
        print(f">>> STATUS GERAL: [FAIL] Encontrados {erros} erro(s).")
    print("="*60)

if __name__ == "__main__":
    testar()

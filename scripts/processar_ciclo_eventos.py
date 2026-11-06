"""
Script CLI para processar lote de eventos e atualizar o estado da planta usando Ollama.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Configura path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.persistencia.database import get_connection
from src.analise.motor_decisao import MotorDecisao
from src.automacao.orquestrador_eventos import orquestrar_transicao

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Iniciando Ciclo de Eventos (CS03) - IA & Apoio à Decisão")
    print("=" * 60)
    
    motor_ia = MotorDecisao()
    
    # Pega os motores para analisar usando explícito JOIN nas tabelas base
    query = """
    SELECT m.id AS motor_id, 
           m.codigo AS codigo_motor, 
           a.tag AS tag_ativo, 
           pl.nome AS planta_nome, 
           ar.nome AS area_nome, 
           li.nome AS linha_nome,
           ul.temperatura AS ultima_temperatura, 
           ul.vibracao AS ultima_vibracao,
           dp.modelo AS placa_modelo, 
           dp.fabricante AS placa_fabricante
    FROM motores m
    JOIN associacoes_ativos a ON a.motor_id = m.id
    JOIN localizacoes loc ON loc.id = a.localizacao_id
    JOIN linhas li ON li.id = loc.linha_id
    JOIN areas ar ON ar.id = li.area_id
    JOIN plantas pl ON pl.id = ar.planta_id
    LEFT JOIN vw_ultimas_leituras_por_ativo ul ON ul.motor_id = m.id
    LEFT JOIN dados_placa_motor dp ON dp.motor_id = m.id
    WHERE ul.temperatura IS NOT NULL
    """
    
    ativos_analisados = 0
    with get_connection() as conn:
        cursor = conn.execute(query)
        ativos = cursor.fetchall()
        
    for ativo in ativos:
        leitura = {
            "temperatura": ativo["ultima_temperatura"],
            "vibracao": ativo["ultima_vibracao"]
        }
        
        # Pega as specs do catalogo (idealmente via catalogo_repository, simplificado aqui)
        q_cat = "SELECT * FROM catalogo_especificacoes_externas WHERE modelo_motor=? AND fabricante=? ORDER BY id DESC LIMIT 1"
        with get_connection() as conn:
            c_cat = conn.execute(q_cat, (ativo["placa_modelo"], ativo["placa_fabricante"]))
            cat = c_cat.fetchone()
            
        catalogo = dict(cat) if cat else {}
        
        # Analisa a leitura usando o LLM (se houver desvio)
        resultado = motor_ia.analisar_leitura(leitura, catalogo)
        
        if resultado["severidade"] != "NORMAL":
            orquestrar_transicao(
                motor_id=ativo["motor_id"],
                tag=ativo["tag_ativo"],
                codigo_motor=ativo["codigo_motor"],
                severidade=resultado["severidade"],
                descricao=resultado["descricao_anomalia"],
                diagnostico=resultado["diagnostico_ia"],
                acao=resultado["acao_recomendada"]
            )
        else:
            logger.info("Ativo %s sem anomalias no momento.", ativo["tag_ativo"])
            
        ativos_analisados += 1
        
    print(f"\n[OK] Ciclo finalizado! {ativos_analisados} ativos analisados.")

if __name__ == "__main__":
    main()

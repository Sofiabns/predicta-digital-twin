"""
Script CLI para executar o processo de Web Scraping e salvar no banco.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Configura path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.persistencia.catalogo_repository import salvar_especificacao
from src.scraping.scraper_motores import buscar_dados_climaticos, raspar_catalogo_motores

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Iniciando Web Scraping de Especificações Técnicas (CS03)")
    print("=" * 60)
    
    # 1. Coleta dados climáticos
    logger.info("Buscando dados climáticos via Open-Meteo...")
    clima = buscar_dados_climaticos()
    logger.info("Clima atual: %s", clima)
    
    # 2. Faz o scraping
    url_simulada = "https://www.weg.net/catalog/invalid" # forçará o fallback se falhar
    dados_tecnicos = raspar_catalogo_motores(url_simulada)
    
    if not dados_tecnicos:
        logger.error("Nenhum dado extraído do catálogo.")
        sys.exit(1)
        
    # 3. Persistência
    guia_troubleshooting = {
        "temperatura_alta": "Verificar ventilação, inspecionar painel, verificar sobrecarga e limpar aletas.",
        "vibracao_alta": "Verificar alinhamento, inspecionar rolamentos e checar fixação da base na sapata."
    }
    
    for item in dados_tecnicos:
        modelo = item["modelo"]
        fabricante = item["fabricante"]
        temp_max = item["temp_max"]
        vib_max = item["vib_max"]
        
        salvar_especificacao(
            modelo_motor=modelo,
            fabricante=fabricante,
            temp_max=temp_max,
            vib_max=vib_max,
            guia_troubleshooting=guia_troubleshooting,
            dados_climaticos=clima,
            fonte_url="fallback_local_html"
        )
        logger.info("Salvo no banco: %s %s (Temp: %s, Vib: %s)", fabricante, modelo, temp_max, vib_max)
        
    print("\n[OK] Scraping concluído com sucesso!")

if __name__ == "__main__":
    main()

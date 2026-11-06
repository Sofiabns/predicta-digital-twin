"""
Módulo de Web Scraping para especificações técnicas de motores.
Utiliza scrapling para maior resiliência e requests para APIs públicas.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def buscar_dados_climaticos(lat: float = -23.5505, lon: float = -46.6333) -> Dict[str, Any]:
    """Busca dados climáticos da API Open-Meteo."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get("current_weather", {})
    except Exception as e:
        logger.error("Erro ao buscar API Open-Meteo: %s", e)
        return {"temperature": 25.0, "error": str(e)}

def raspar_catalogo_motores(url: str | None = None) -> List[Dict[str, Any]]:
    """Raspa especificações do catálogo usando scrapling. Faz fallback local se falhar."""
    dados_extraidos = []
    html_content = ""
    
    if url:
        try:
            logger.info("Tentando extrair dados online de %s via scrapling...", url)
            from scrapling.fetchers import Fetcher  # import tardio: dependência opcional
            fetcher = Fetcher()
            response = fetcher.get(url)
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            tabela = soup.find("table", id="tabela-especificacoes")
            if not tabela:
                logger.warning("Tabela não encontrada na URL online. Ativando fallback...")
                url = None
        except Exception as e:
            logger.warning("Falha ao raspar URL online (%s). Ativando fallback local...", e)
            url = None
    
    if not url:
        # Fallback para o arquivo local
        logger.info("Usando catálogo de fallback local...")
        project_root = Path(__file__).resolve().parents[2]
        fallback_path = project_root / "data" / "samples" / "catalogo_fabricante.html"
        if fallback_path.exists():
            html_content = fallback_path.read_text(encoding="utf-8")
        else:
            logger.error("Arquivo de fallback não encontrado!")
            return []
            
        soup = BeautifulSoup(html_content, "html.parser")
        tabela = soup.find("table", id="tabela-especificacoes")
        
    if not tabela:
        logger.error("Tabela de especificações não encontrada no HTML.")
        return []
        
    for linha in tabela.find("tbody").find_all("tr"):
        colunas = linha.find_all("td")
        if len(colunas) >= 4:
            dados_extraidos.append({
                "fabricante": colunas[0].get_text(strip=True),
                "modelo": colunas[1].get_text(strip=True),
                "temp_max": float(colunas[2].get_text(strip=True)),
                "vib_max": float(colunas[3].get_text(strip=True)),
            })
            
    return dados_extraidos

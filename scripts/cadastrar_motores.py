"""
Cadastra motores iniciais no banco de dados.

Populacao inicial (seed) da tabela 'motores' com os ativos que
serao monitorados pelo pipeline de coleta. Idempotente: se o
motor ja existe, ignora e nao duplica.

Uso:
    python scripts/cadastrar_motores.py
"""

import sys
from pathlib import Path

# Adiciona raiz do projeto ao sys.path para importar 'src.*'
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.persistencia.motor_repository import (
    inserir_motor,
    buscar_motor_por_codigo,
)


# ============================================================
# MOTORES A CADASTRAR (CS01 + amostra CS02 com 5 ativos)
# ============================================================

MOTORES_INICIAIS = [
    {
        "codigo": "MTR-001",
        "modelo": "WEG W22 IE3 Premium",
        "fabricante": "WEG",
        "localizacao": "Galpao A - Linha 1",
        "potencia_kw": 15.0,
    },
    {
        "codigo": "MTR-002",
        "modelo": "ABB M3AA 132M",
        "fabricante": "ABB",
        "localizacao": "Galpao A - Estamparia",
        "potencia_kw": 11.0,
    },
    {
        "codigo": "MTR-003",
        "modelo": "Siemens SIMOTICS SD",
        "fabricante": "Siemens",
        "localizacao": "Sala compressores",
        "potencia_kw": 18.5,
    },
    {
        "codigo": "MTR-004",
        "modelo": "WEG W21",
        "fabricante": "WEG",
        "localizacao": "Utilidades - exaustao",
        "potencia_kw": 7.5,
    },
    {
        "codigo": "MTR-005",
        "modelo": "Baldor Super-E",
        "fabricante": "Baldor",
        "localizacao": "Envasamento - transportador",
        "potencia_kw": 5.5,
    },
]


# ============================================================
# EXECUCAO
# ============================================================

def main():
    print("=" * 60)
    print("CADASTRO DE MOTORES INICIAIS")
    print("=" * 60)

    inseridos = 0
    existentes = 0

    for dados in MOTORES_INICIAIS:
        existente = buscar_motor_por_codigo(dados["codigo"])
        if existente:
            print(f"[SKIP] {dados['codigo']} ja cadastrado (ID={existente['id']})")
            existentes += 1
        else:
            motor_id = inserir_motor(**dados)
            print(f"[OK]   {dados['codigo']} cadastrado com ID={motor_id}")
            inseridos += 1

    print("\n" + "=" * 60)
    print(f"RESUMO: {inseridos} inseridos | {existentes} ja existentes")
    print("=" * 60)


if __name__ == "__main__":
    main()

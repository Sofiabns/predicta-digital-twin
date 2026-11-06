#!/bin/bash
echo "==================================================="
echo "Predicta Sprint 4 - Startup Automation (Mac/Linux)"
echo "==================================================="
echo ""

echo "[Verificando Python...]"
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python3 nao encontrado! Instale o Python 3.10+."
    exit 1
fi

echo "[Verificando Ollama...]"
if ! command -v ollama &> /dev/null; then
    echo "ATENCAO: Ollama nao encontrado. Instale o Ollama e baixe o llama3.2 para ter acesso as funcoes de IA."
else
    if ! ollama list | grep -q "llama3.2"; then
        echo "ATENCAO: Modelo llama3.2 nao encontrado no Ollama. Execute 'ollama pull llama3.2'."
    fi
fi

echo "[1/4] Criando ambiente virtual (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    echo "Ambiente virtual ja existe."
fi

echo "[2/4] Ativando ambiente virtual e instalando dependencias..."
source .venv/bin/activate
pip install -r requirements.txt

echo "[3/4] Inicializando banco de dados..."
echo "Recriando o banco e executando a demonstração integrada (14 ciclos, ~1 min)..."
python scripts/executar_rpa_integrado.py --demo

echo "[4/4] Inicializando os servicos do Predicta Sprint 4..."
echo ""
echo "Iniciando o RPA integrado com simulador IoT em background..."
python scripts/simulador_iot_stream.py &
IOT_PID=$!

echo "Iniciando o Dashboard..."
python scripts/run_dashboard.py

# Ao fechar o dashboard (Ctrl+C), mata o simulador também
kill $IOT_PID

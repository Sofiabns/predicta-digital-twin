@echo off
echo ===================================================
echo Predicta Sprint 4 - Startup Automation (Windows)
echo ===================================================
echo.

echo [Verificando Python...]
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Python nao encontrado! Instale o Python 3.10+ e adicione ao PATH.
    pause
    exit /b
)

echo [Verificando Ollama...]
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo ATENCAO: Ollama nao parece estar rodando ou instalado.
    echo Certifique-se de que o Ollama esta iniciado e com o modelo llama3.2 instalado.
    echo O Dashboard abrira normalmente, porem o assistente de IA podera apresentar timeout.
    echo.
)

echo [1/4] Criando ambiente virtual (.venv)...
if not exist .venv (
    python -m venv .venv
) else (
    echo Ambiente virtual ja existe.
)

echo [2/4] Ativando ambiente virtual e instalando dependencias...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/4] Inicializando banco de dados...
echo Recriando o banco e executando a demonstracao integrada (14 ciclos)...
python scripts\executar_rpa_integrado.py --demo

echo [4/4] Inicializando os servicos do Predicta Sprint 4...
echo.
echo Iniciando o RPA integrado com simulador IoT em uma nova janela...
start "Predicta IoT Stream" cmd /k "call .venv\Scripts\activate.bat && python scripts\simulador_iot_stream.py"

echo Iniciando o Dashboard em uma nova janela...
start "Predicta Dashboard" cmd /k "call .venv\Scripts\activate.bat && python scripts\run_dashboard.py"

echo ===================================================
echo Tudo pronto! O dashboard estara online no navegador.
echo Acesse: http://localhost:7860
echo ===================================================
pause

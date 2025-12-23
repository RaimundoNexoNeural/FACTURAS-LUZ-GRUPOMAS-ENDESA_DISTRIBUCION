#!/bin/bash
# filepath: setup_and_run.sh

# --- CONFIGURACIÓN Y VARIABLES ---
PROJECT_DIR=$(pwd)
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="9998"
PYTHON_BIN="python3"

echo "======================================================="
echo " 🚀 CONFIGURACIÓN COMPLETA Y ARRANQUE DE LA API 🚀 "
echo "======================================================="

# 1. Validación de Credenciales
if [ -z "$ENDESA_USER" ] || [ -z "$ENDESA_PASSWORD" ]; then
    echo " ❌ ERROR: Credenciales no detectadas. Abortando."
    exit 1
fi

# 2. Instalación de paquetes del sistema (sudo)
echo "1. Verificando paquetes base (venv, lsof)..."
sudo apt update && sudo apt install -y python3-venv python3-pip lsof

# 3. Preparación del Entorno Virtual
echo "2. Configurando entorno virtual..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate

# 4. Instalación de Dependencias de Python
echo "3. Instalando librerías de Python..."
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# 5. Configuración de Playwright (Navegadores y Dependencias)
echo "4. Configurando Playwright y Chromium..."
# Instalamos las librerías de sistema necesarias para Chromium
sudo ./$VENV_DIR/bin/playwright install-deps
# Instalamos el binario de Chromium
playwright install chromium

# 6. Preparación de Carpetas
echo "5. Creando directorios de logs y descargas..."
mkdir -p logs csv temp_endesa_downloads/Facturas_Endesa_PDFs temp_endesa_downloads/Facturas_Endesa_XMLs

# 7. Limpieza de Procesos (Método Seguro)
echo "6. Limpiando puerto $UVICORN_PORT..."
CURRENT_PID=$(lsof -t -i :$UVICORN_PORT 2>/dev/null || true)
if [ ! -z "$CURRENT_PID" ]; then
    echo "   Deteniendo proceso anterior (PID: $CURRENT_PID)..."
    kill -9 $CURRENT_PID 2>/dev/null || true
    sleep 2
fi

# 8. Lanzamiento Persistente
echo "7. Desplegando API en segundo plano..."
# Usamos python3 -m uvicorn para máxima compatibilidad con el venv
nohup python3 -m uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT > api_output.log 2>&1 &

# Guardar el PID y desvincular
NEW_PID=$!
echo $NEW_PID > api_server.pid
disown $NEW_PID


echo "======================================================="
echo " ✅ PROCESO FINALIZADO CON ÉXITO "
echo " PID ACTUAL: $NEW_PID"
echo " URL: http://93.93.64.20:9998/docs"
echo "======================================================="

deactivate
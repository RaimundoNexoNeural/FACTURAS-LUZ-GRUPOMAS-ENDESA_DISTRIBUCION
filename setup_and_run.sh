#!/bin/bash
# filepath: setup_and_run.sh

# Salir inmediatamente si un comando falla
set -e

# --- CONFIGURACIÓN Y VARIABLES DE ENTORNO ---
PROJECT_DIR=$(pwd)
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="8000" # Puerto definido por el usuario (8000)

# 🚨 VARIABLES DE CREDENCIALES (MODIFICAR)
# Se utilizan para configurar las variables de entorno para el proceso de Uvicorn.
ENDESA_USER="TU_USUARIO_REAL_ENDESA"
ENDESA_PASSWORD="TU_PASSWORD_REAL_ENDESA"

# -----------------------------------------------
echo "======================================================="
echo "🚀 INICIANDO CONFIGURACIÓN Y ARRANQUE DE LA API 🚀"
echo "======================================================="

# 1. Verificar Requisitos Base
echo "1. Verificando la presencia de archivos clave..."
if [ ! -f "$REQUIREMENTS_FILE" ] || [ ! -f "api.py" ]; then
    echo "❌ ERROR: Asegúrate de ejecutar este script desde el directorio raíz del proyecto."
    exit 1
fi

if ! python3 -c 'import sys; exit(sys.version_info >= (3, 9))'; then
    echo "Python 3.9 o superior es requerido. Por favor instálalo antes de continuar."
    exit 1
fi

# 2. Instalación de Dependencias del Sistema (CRUCIAL para Playwright)
echo ""
echo "2. ⚙️ Instalando dependencias del sistema (librerías de Linux para Playwright)..."
# Este comando usa el módulo de Python de Playwright para detectar e instalar
# las librerías necesarias para ejecutar Chromium en Linux (requiere sudo).
sudo python3 -m playwright install-deps

# 3. Crear y Activar Entorno Virtual
echo ""
echo "3. 🐍 Configurando entorno virtual '$VENV_DIR'..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi

# Activación del entorno
source $VENV_DIR/bin/activate

# 4. Instalar Dependencias de Python
echo "4. 📦 Instalando dependencias de Python desde $REQUIREMENTS_FILE..."
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# 5. Configurar e Instalar Navegador de Playwright
echo "5. 🌐 Instalando el navegador Chromium para Playwright..."
# Instala el binario del navegador necesario.
playwright install chromium

# 6. Preparación de Directorios de Trabajo
echo "6. 📂 Creando directorios de logs y descargas si no existen..."
mkdir -p logs
mkdir -p csv
mkdir -p temp_endesa_downloads/Facturas_Endesa_PDFs
mkdir -p temp_endesa_downloads/Facturas_Endesa_XMLs
mkdir -p temp_endesa_downloads/Facturas_Endesa_HTMLs


# 7. Desplegar la API con Uvicorn (Persistencia con nohup)
echo ""
echo "7. 🚀 Desplegando la API en http://$UVICORN_HOST:$UVICORN_PORT en segundo plano (nohup)..."

# A. Detener procesos anteriores que usen el puerto
echo "   Deteniendo procesos anteriores en el puerto $UVICORN_PORT..."
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "   Proceso Uvicorn anterior (PID $PID) detenido."
fi

# B. Ejecución con nohup y variables de entorno
# 'nohup' previene que el proceso se detenga al cerrar la terminal.
# 'env' pasa las credenciales como variables de entorno al proceso de Uvicorn.
# '&' ejecuta el comando en segundo plano.
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
      uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT > api_output.log 2>&1 &

# C. Guardar el PID para la gestión posterior (detener, reiniciar)
echo $! > api_server.pid

echo "✅ CONFIGURACIÓN Y ARRANQUE COMPLETADO."
echo "La API se está ejecutando en segundo plano. PID: $(<api_server.pid)"
echo "Revisa 'api_output.log' para la salida de Uvicorn."
echo "======================================================="

# Desactivar el entorno virtual
deactivate
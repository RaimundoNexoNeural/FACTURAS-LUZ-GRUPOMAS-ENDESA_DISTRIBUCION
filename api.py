from fastapi import FastAPI, HTTPException, Query
from typing import List, Dict, Any
from modelos_datos import FacturaEndesaDistribucion
# Cambiamos ejecutar_robot_multiempresa por ejecutar_robot_api
from robotEndesa import ejecutar_robot_api 
from robotEndesa import obtener_pdf_local_base64 
import asyncio
import re
import os
import shutil
from logs import escribir_log

# Inicializar la aplicación de FastAPI
app = FastAPI(
    title="API de Extracción de Facturas e-distribución",
    description="API que automatiza la descarga de facturas del portal e-distribución recorriendo todos los roles."
)


@app.get("/")
def read_root():
    return {"message": "Servicio de Extracción e-distribución activo. Visite /docs"}

# --- Funciones de Validación ---

def validar_fecha(fecha: str):
    """Validación de formato de fecha DD/MM/YYYY."""
    fecha_pattern = r'^\d{2}/\d{2}/\d{4}$'
    if not re.match(fecha_pattern, fecha):
        raise HTTPException(
            status_code=400, 
            detail="El formato de fecha es inválido. Use DD/MM/YYYY (ej: 01/10/2025)."
        )

# --- Endpoint de Salud ---
@app.get("/")
def read_root():
    """Endpoint de salud (Health Check)"""
    return {"message": "Servicio de Extracción e-distribución activo. Visite /docs."}

# --- Endpoint para Limpiar Archivos Temporales y Logs ---
@app.get("/clear_files")
async def clear_files():
    escribir_log("\nAPI llamada: /clear_files - Iniciando limpieza.", pretexto="")
    carpetas = ["temp_endesa_downloads", "csv"]
    archivo_logs = "logs/log.txt"

    for carpeta in carpetas:
        try:
            if os.path.exists(carpeta):
                shutil.rmtree(carpeta)
                escribir_log(f"Carpeta '{carpeta}' eliminada.")
            os.makedirs(carpeta, exist_ok=True)
            escribir_log(f"Carpeta '{carpeta}' recreada.")
        except Exception as e:
            escribir_log(f"Error al limpiar {carpeta}: {e}")

    try:
        if os.path.exists(archivo_logs):
            with open(archivo_logs, "w") as f: pass
            escribir_log("Archivo de logs vaciado.")
    except Exception as e:
        escribir_log(f"Error al vaciar logs: {e}")

    return {"message": "Limpieza de archivos temporales, logs y CSVs completada."}

# --- Endpoint de Extracción de Facturas (GET) ---
@app.get(
    "/facturas", 
    response_model=List[FacturaEndesaDistribucion],
    summary="Extrae facturas de todos los roles para un rango de fechas."
)
async def get_facturas(
    fecha_desde: str, # Formato DD/MM/YYYY
    fecha_hasta: str  # Formato DD/MM/YYYY
):
    escribir_log(f"\nAPI llamada GET /facturas: Desde={fecha_desde}, Hasta={fecha_hasta}\n", pretexto="\n")
    
    validar_fecha(fecha_desde)
    validar_fecha(fecha_hasta)

    try:
        # Usamos el nombre de función que existe en robotEndesa.py
        facturas = await ejecutar_robot_api(
            fecha_desde=fecha_desde, 
            fecha_hasta=fecha_hasta
        )

        escribir_log(f"\n[API] ÉXITO: {len(facturas)} facturas procesadas.\n")
        return facturas

    except Exception as e:
        error_msg = f"Fallo crítico en el proceso RPA: {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

# --- Endpoint de Lectura de PDF Local ---
@app.get(
    "/pdf-local/{cups}/{numero_factura}",
    response_model=Dict[str, Any],
    summary="Obtiene el PDF en Base64 desde el disco local."
)
def get_pdf_local(cups: str, numero_factura: str):
    escribir_log(f"API llamada (PDF Local): CUPS={cups}, Factura={numero_factura}")
    resultado = obtener_pdf_local_base64(
        cups=cups,
        numero_factura=numero_factura,
    )
    return resultado
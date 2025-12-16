from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from modelos_datos import FacturaEndesaCliente
# Importamos la función ASÍNCRONA para la extracción de datos
from robotEndesa import ejecutar_robot_api 
# Importamos la función SÍNCRONA para la lectura de PDF local
from robotEndesa import obtener_pdf_local_base64 
import asyncio
import re
import os # Necesario para manejar FileNotFoundError
import shutil
from logs import escribir_log

# Inicializar la aplicación de FastAPI
app = FastAPI(
    title="API de Extracción de Facturas Endesa",
    description="API que automatiza la búsqueda y extracción de datos detallados de facturas de Endesa."
)

# --- Funciones de Validación ---

def validar_cups(cups: str):
    """Simple validación de formato de CUPS (ajustar según sea necesario)."""
    cups_pattern = r'^ES[A-Z0-9]{20}$' 
    if not re.match(cups_pattern, cups):
        raise HTTPException(
            status_code=400, 
            detail=f"El formato del código CUPS '{cups}' es inválido. Debe seguir el patrón ESXX... y tener 22 caracteres."
        )

def validar_fecha(fecha: str):
    """Simple validación de formato de fecha DD/MM/YYYY."""
    fecha_pattern = r'^\d{2}/\d{2}/\d{4}$'
    if not re.match(fecha_pattern, fecha):
        raise HTTPException(
            status_code=400, 
            detail="El formato de fecha es inválido. Use DD/MM/YYYY (ej: 01/10/2025)."
        )

# --- Endpoint de Extracción de Metadatos ---

@app.get("/")
def read_root():
    """Endpoint de salud (Health Check)"""
    return {"message": "Servicio de Extracción de Facturas Endesa activo. Visite /docs para la documentación."}

# --- Endpoint para Limpiar Archivos Temporales y Logs ---
@app.get(
    "/clear_files"
)
async def clear_files():
    """ Endpoint para limpiar archivos temporales y logs 
    Elimina:
    - La carpeta de archivos temporales "temp_endesa_downloads" (y su contenido).
    - La carpeta de CSVs "csv" (y su contenido).
    - Vacía el archivo de logs "logs/log.txt".
    """
    escribir_log("\nAPI llamada: /clear_files - Iniciando limpieza de archivos temporales, logs y CSVs.",pretexto="")
    carpeta_archivos_temporales = "temp_endesa_downloads"
    archivo_logs = "logs/log.txt"
    carpeta_cvs = "csv" # Corregido a 'carpeta_cvs' para consistencia

    
    # 1. Eliminar la carpeta de archivos temporales (y todo su contenido)
    try:   
        if os.path.exists(carpeta_archivos_temporales):
            # Usamos rmtree para eliminar la carpeta y todo lo que contenga.
            shutil.rmtree(carpeta_archivos_temporales)
            escribir_log(f"Carpeta '{carpeta_archivos_temporales}' y su contenido eliminados.")
            
            # Opcional: Recrear la carpeta raíz vacía inmediatamente para prevenir colisiones en la siguiente llamada a /facturas
            os.makedirs(carpeta_archivos_temporales, exist_ok=True)
            escribir_log(f"Carpeta '{carpeta_archivos_temporales}' raíz recreada vacía.")

        else:
            escribir_log(f"Carpeta '{carpeta_archivos_temporales}' no existe. Omitiendo borrado.")

    except Exception as e:
        error_msg = f"Error crítico al eliminar/recrear '{carpeta_archivos_temporales}': {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


    # 2. Eliminar la carpeta de CSVs (y su contenido), y recrearla vacía
    try:
        if os.path.exists(carpeta_cvs):
            # Eliminamos la carpeta y su contenido
            shutil.rmtree(carpeta_cvs)
            escribir_log(f"Carpeta '{carpeta_cvs}' y su contenido eliminados.")
        
        # Recrear la carpeta vacía para que el RPA pueda guardar el log CSV
        os.makedirs(carpeta_cvs, exist_ok=True)
        escribir_log(f"Carpeta '{carpeta_cvs}' recreada vacía.")
        
    except Exception as e:
        error_msg = f"Error crítico al eliminar/recrear '{carpeta_cvs}': {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


    # 3. Limpiar (vaciar) el archivo de logs
    try:
        # Abrir en modo 'w' para truncar (vaciar) el archivo. Si no existe, lo crea.
        with open(archivo_logs, "w") as f:
             pass 
        escribir_log("\nAPI llamada: /clear_files - Completada\n",pretexto="")
    except Exception as e:
        escribir_log(f"Error al limpiar el archivo de logs: {e}")
        # Este error no es crítico, solo se registra.

    return {"message": "Limpieza de archivos temporales, logs y CSVs completada."}

# --- Endpoint de Extracción de Metadatos ---

@app.get(
    "/facturas", 
    response_model=List[FacturaEndesaCliente],
    summary="Busca y extrae los datos de facturas para un CUPS en un rango de fechas."
)
async def get_facturas(
    cups: str, 
    fecha_desde: str, # Formato DD/MM/YYYY
    fecha_hasta: str  # Formato DD/MM/YYYY
):
    """
    Realiza el proceso completo de Login -> Búsqueda -> Descarga -> Extracción XML.
    Devuelve una lista de objetos FacturaEndesaCliente con el campo 'descarga_selector' 
    que se usará para la descarga de PDF local.
    """
    
    # Validaciones iniciales
    validar_cups(cups)
    validar_fecha(fecha_desde)
    validar_fecha(fecha_hasta)

    escribir_log(f"\nAPI llamada (Metadata): CUPS={cups}, Desde={fecha_desde}, Hasta={fecha_hasta}\n",pretexto="")

    try:
        facturas = await ejecutar_robot_api(
            cups=cups, 
            fecha_desde=fecha_desde, 
            fecha_hasta=fecha_hasta
        )

        if not facturas:
             escribir_log(f"Advertencia: No se encontraron facturas para el CUPS {cups} en el rango.")
             return []

        escribir_log(f"ÉXITO (Metadata): {len(facturas)} facturas extraídas.")
        return facturas

    except HTTPException:
        raise
        
    except Exception as e:
        error_msg = f"Fallo crítico en el proceso RPA para CUPS {cups}: {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


# --- Endpoint de Lectura de PDF Local ---

@app.get(
    "/pdf-local/{cups}/{numero_factura}",
    response_model=Dict[str, Any], # Devolvemos un diccionario que incluye el Base64
    summary="Accede y codifica un PDF previamente descargado del servidor."
)
def get_pdf_local(
    cups: str,
    numero_factura: str,
):
    """
    Lee el PDF del disco local (temp_endesa_downloads/Facturas_Endesa_PDFs/) 
    usando el CUPS y el número de factura.

    - **cups**: Código CUPS.
    - **numero_factura**: Número de factura (ej: P25CON050642974).

    Devuelve un JSON con el contenido del PDF codificado en Base64 bajo la clave 'pdf_base64'.
    """
    
    # Validación básica de los parámetros entrantes
    if not numero_factura:
         raise HTTPException(status_code=400, detail="Falta el parámetro 'numero_factura'.")
    validar_cups(cups)
    
    escribir_log(f"\nAPI llamada (PDF Local): CUPS={cups}, Factura={numero_factura}\n",pretexto="")
    
    try:
        # Llamamos a la función síncrona de acceso a disco local
        # No necesitamos la descarga_selector ya que el archivo está en el disco.
        pdf_data = obtener_pdf_local_base64(
            cups=cups,
            numero_factura=numero_factura,
        )

        escribir_log(f"ÉXITO (PDF Local): PDF para {numero_factura} codificado.")
        return pdf_data
        
    except FileNotFoundError as e:
        error_msg = f"Archivo no encontrado. Asegúrese de que la factura se haya extraído previamente. Detalle: {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=404, detail=error_msg)
        
    except Exception as e:
        error_msg = f"Fallo crítico al leer el PDF para {numero_factura}: {e}"
        escribir_log(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
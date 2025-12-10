from fastapi import FastAPI, HTTPException
from typing import List
from modelos_datos import FacturaEndesaCliente
from robotEndesa import ejecutar_robot_api
import asyncio
import re

# Inicializar la aplicación de FastAPI
app = FastAPI(
    title="API de Extracción de Facturas Endesa",
    description="API que automatiza la búsqueda y extracción de datos detallados de facturas de Endesa."
)

def validar_cups(cups: str):
    """Simple validación de formato de CUPS (ajustar según sea necesario)."""
    # Patrón corregido: ES (2 chars) seguido de 20 caracteres alfanuméricos (total 22 chars),
    # que coincide con el CUPS de ejemplo.
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

@app.get("/")
def read_root():
    """Endpoint de salud (Health Check)"""
    return {"message": "Servicio de Extracción de Facturas Endesa activo. Visite /docs para la documentación."}

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
    Realiza el proceso completo de Login -> Búsqueda -> Descarga -> Extracción XML 
    usando Playwright. Los datos son devueltos en formato JSON.

    - **cups**: Código CUPS (ej: ES0034111300275021NX0F).
    - **fecha_desde**: Fecha de inicio de emisión (DD/MM/YYYY, ej: 01/10/2025).
    - **fecha_hasta**: Fecha de fin de emisión (DD/MM/YYYY, ej: 31/10/2025).
    """
    
    # Validaciones iniciales
    validar_cups(cups)
    validar_fecha(fecha_desde)
    validar_fecha(fecha_hasta)
    
    print(f"API llamada: CUPS={cups}, Desde={fecha_desde}, Hasta={fecha_hasta}")
    
    try:
        # 1. Ejecución del robot asíncrono
        facturas = await ejecutar_robot_api(
            cups=cups, 
            fecha_desde=fecha_desde, 
            fecha_hasta=fecha_hasta
        )

        if not facturas:
             # Si no hay facturas, devolvemos una lista JSON vacía (código 200)
             print(f"Advertencia: No se encontraron facturas para el CUPS {cups} en el rango.")
             return []

        print(f"ÉXITO: {len(facturas)} facturas extraídas.")
        # FastAPI automáticamente convierte List[FacturaEndesaCliente] a JSON
        return facturas

    except HTTPException:
        # Re-lanza las excepciones HTTP ya definidas (ej. 400 por validación)
        raise
        
    except Exception as e:
        # Manejo de errores críticos del robot (ej. fallo de login, fallo de Playwright)
        error_msg = f"Fallo crítico en el proceso RPA para CUPS {cups}: {e}"
        print(f"ERROR: {error_msg}")
        # Lanza un error 500 para el cliente
        raise HTTPException(status_code=500, detail=error_msg)
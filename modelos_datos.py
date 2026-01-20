from pydantic import BaseModel
from typing import Optional # Usamos Optional para los campos que pueden ser None

# Reemplazamos @dataclass por herencia de BaseModel
class FacturaEndesaDistribucion(BaseModel):
    """
    Estructura de datos para almacenar la metadata de una factura extraída de la web.
    Se utiliza Pydantic para la validación y serialización automática en FastAPI.
    """

    # Campo para indicar si hubo un error en el proceso RPA
    error_RPA: Optional[bool] = False
    
    # === 1. Metadata extraída directamente de la TABLA de Endesa ===
    
    fecha_emision: Optional[str] = "N/A"
    numero_factura: Optional[str] = "N/A"
    fecha_inicio_periodo: Optional[str] = "N/A"
    fecha_fin_periodo: Optional[str] = "N/A"
    importe_total_tabla: Optional[float] = 0.0
    contrato: Optional[str] = "N/A"
    cups: str  # El CUPS lo mantenemos obligatorio para saber a quién pertenece el error
    secuencial: Optional[str] = "N/A"
    estado_factura: Optional[str] = "N/A"
    fraccionamiento: Optional[str] = "N/A"
    tipo_factura: Optional[str] = "N/A"
    
    
    # === 2. Enlaces/Selectores de Descarga (Para el proceso RPA) ===
    
    descarga_selector: Optional[str] = "N/A"
    
    # === 3. Datos DETALLADOS extraídos del XML/HTML ===
    
    # Campos generales
    mes_facturado: Optional[str] = None
    direccion_suministro: Optional[str] = None
    
    # Datos de Potencia
    potencia_p1: Optional[float] = 0.0
    potencia_p2: Optional[float] = 0.0
    potencia_p3: Optional[float] = 0.0
    potencia_p4: Optional[float] = 0.0
    potencia_p5: Optional[float] = 0.0
    potencia_p6: Optional[float] = 0.0

    termino_de_potencia_peaje: Optional[float] = 0.0
    termino_de_potencia_cargos: Optional[float] = 0.0
    importe_de_potencia: Optional[float] = 0.0
    
    # Datos de Consumo
    num_dias: Optional[int] = None

    termino_de_energia_peaje: Optional[float] = 0.0
    termino_de_energia_cargos: Optional[float] = 0.0
    importe_atr: Optional[float] = 0.0

    # Impuestos, conceptos y totales
    importe_impuesto_electrico: Optional[float] = 0.0
    importe_alquiler_equipos: Optional[float] = 0.0
    importe_otros_conceptos: Optional[float] = 0.0
    importe_exceso_potencia: Optional[float] = 0.0
    importe_reactiva: Optional[float] = 0.0
    importe_base_imponible: Optional[float] = 0.0
    
    # Totales y fechas de pago
    importe_facturado: Optional[float] = 0.0
    fecha_de_vencimiento: Optional[str] = None

    fecha_de_cobro_en_banco: Optional[str] = None
    
   
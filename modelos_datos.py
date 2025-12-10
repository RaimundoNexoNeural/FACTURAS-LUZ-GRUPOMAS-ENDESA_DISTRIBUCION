from pydantic import BaseModel
from typing import Optional # Usamos Optional para los campos que pueden ser None

# Reemplazamos @dataclass por herencia de BaseModel
class FacturaEndesaCliente(BaseModel):
    """
    Estructura de datos para almacenar la metadata de una factura extraída de la web.
    Se utiliza Pydantic para la validación y serialización automática en FastAPI.
    """
    
    # === 1. Metadata extraída directamente de la TABLA de Endesa ===
    
    fecha_emision: str
    numero_factura: str 
    fecha_inicio_periodo: str
    fecha_fin_periodo: str
    importe_total_tabla: float
    contrato: str
    cups: str
    secuencial: str
    estado_factura: str
    fraccionamiento: str
    tipo_factura: str
    
    # === 2. Enlaces/Selectores de Descarga (Para el proceso RPA) ===
    
    descarga_selector: str
    
    # === 3. Datos DETALLADOS extraídos del XML/HTML ===
    
    # Campos generales
    mes_facturado: Optional[str] = None
    tarifa: Optional[str] = None
    direccion_suministro: Optional[str] = None
    
    # Datos de Potencia
    potencia_p1: Optional[float] = None
    potencia_p2: Optional[float] = None
    potencia_p3: Optional[float] = None
    potencia_p4: Optional[float] = None
    potencia_p5: Optional[float] = None
    potencia_p6: Optional[float] = None
    importe_de_potencia: Optional[float] = None
    
    # Datos de Consumo
    num_dias: Optional[int] = None
    consumo_kw_p1: Optional[float] = None
    consumo_kw_p2: Optional[float] = None
    consumo_kw_p3: Optional[float] = None
    consumo_kw_p4: Optional[float] = None
    consumo_kw_p5: Optional[float] = None
    consumo_kw_p6: Optional[float] = None
    kw_totales: Optional[float] = None

    importe_consumo_p1: Optional[float] = None
    importe_consumo_p2: Optional[float] = None
    importe_consumo_p3: Optional[float] = None
    importe_consumo_p4: Optional[float] = None
    importe_consumo_p5: Optional[float] = None
    importe_consumo_p6: Optional[float] = None

    energia_precio_indexado_p1: Optional[float] = None
    energia_precio_indexado_p2: Optional[float] = None
    energia_precio_indexado_p3: Optional[float] = None
    energia_precio_indexado_p4: Optional[float] = None
    energia_precio_indexado_p5: Optional[float] = None
    energia_precio_indexado_p6: Optional[float] = None
    importe_consumo: Optional[float] = None
    
    # Impuestos, conceptos y totales
    importe_bono_social: Optional[float] = None
    importe_impuesto_electrico: Optional[float] = None
    importe_alquiler_equipos: Optional[float] = None
    importe_otros_conceptos: Optional[float] = None

    importe_exceso_potencia_p1: Optional[float] = None
    importe_exceso_potencia_p2: Optional[float] = None
    importe_exceso_potencia_p3: Optional[float] = None
    importe_exceso_potencia_p4: Optional[float] = None
    importe_exceso_potencia_p5: Optional[float] = None
    importe_exceso_potencia_p6: Optional[float] = None
    importe_exceso_potencia: Optional[float] = None
    
    importe_reactiva: Optional[float] = None
    importe_base_imponible: Optional[float] = None
    
    # Totales y fechas de pago
    importe_facturado: Optional[float] = None
    fecha_de_vencimiento: Optional[str] = None
    importe_total_final: Optional[float] = None 
    fecha_de_cobro_en_banco: Optional[str] = None
    
    # === 4. Eliminación de campos no utilizados en el modelo (opcional) ===
    # data_base64: str | None = None
    # archivo_nombre: str | None = None
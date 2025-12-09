from dataclasses import dataclass

@dataclass
class FacturaEndesaCliente:
    """
    Estructura de datos para almacenar la metadata de una factura extraída de la web
    y preparar el contenido binario para ser enviado a la API de n8n.
    
    Esta clase contiene tanto la metadata de la tabla de Endesa como los campos 
    detallados que se extraerán del contenido del PDF/XML/HTML.
    """
    
    # === 1. Metadata extraída directamente de la TABLA de Endesa (Saldrá en la Tarea 4) ===
    
    fecha_emision: str
    numero_factura: str # También llamado 'Nº de factura' en la tabla
    fecha_inicio_periodo: str
    fecha_fin_periodo: str
    importe_total_tabla: float # Renombrado para diferenciar del 'Importe Total' final
    contrato: str
    cups: str
    secuencial: str
    estado_factura: str
    fraccionamiento: str
    tipo_factura: str
    
    # === 2. Enlaces/Selectores de Descarga (Para el proceso RPA) ===
    
    # Campo que nos permitirá hacer clic para descargar (el 'value' o el selector del botón PDF)
    descarga_selector: str
    
    # URL completa para el HTML y XML (si existen)
    # url_descarga_pdf: str | None = None
    # url_descarga_html: str | None = None 
    # url_descarga_xml: str | None = None
    
    # === 3. Datos DETALLADOS extraídos del PDF/XML/HTML (Solo disponibles después del OCR/Procesamiento) ===
    
    # Campos generales
    mes_facturado: str | None = None
    tarifa: str | None = None
    direccion_suministro: str | None = None
    
    # Datos de Potencia (Se asume float, pueden ser None si no aplica o no se encuentra)
    potencia_p1: float | None = None
    potencia_p2: float | None = None
    potencia_p3: float | None = None
    potencia_p4: float | None = None
    potencia_p5: float | None = None
    potencia_p6: float | None = None
    importe_de_potencia: float | None = None
    
    # Datos de Consumo
    num_dias: int | None = None
    consumo_kw_p1: float | None = None
    consumo_kw_p2: float | None = None
    consumo_kw_p3: float | None = None
    consumo_kw_p4: float | None = None
    consumo_kw_p5: float | None = None
    consumo_kw_p6: float | None = None
    kw_totales: float | None = None

    importe_consumo_p1: float | None = None
    importe_consumo_p2: float | None = None
    importe_consumo_p3: float | None = None
    importe_consumo_p4: float | None = None
    importe_consumo_p5: float | None = None
    importe_consumo_p6: float | None = None

    energia_precio_indexado_p1: float | None = None
    energia_precio_indexado_p2: float | None = None
    energia_precio_indexado_p3: float | None = None
    energia_precio_indexado_p4: float | None = None
    energia_precio_indexado_p5: float | None = None
    energia_precio_indexado_p6: float | None = None
    importe_consumo: float | None = None
    
    # Impuestos, conceptos y totales
    importe_bono_social: float | None = None
    importe_impuesto_electrico: float | None = None
    importe_alquiler_equipos: float | None = None
    importe_otros_conceptos: float | None = None

    importe_exceso_potencia_p1: float | None = None
    importe_exceso_potencia_p2: float | None = None
    importe_exceso_potencia_p3: float | None = None
    importe_exceso_potencia_p4: float | None = None
    importe_exceso_potencia_p5: float | None = None
    importe_exceso_potencia_p6: float | None = None
    importe_exceso_potencia: float | None = None
    
    importe_reactiva: float | None = None
    importe_base_imponible: float | None = None
    
    # Totales y fechas de pago
    importe_facturado: float | None = None
    fecha_de_vencimiento: str | None = None
    importe_total_final: float | None = None # El importe total real del PDF
    fecha_de_cobro_en_banco: str | None = None
    
    # === 4. Contenido Binario (Para la API) ===
    
    # data_base64: str | None = None
    # archivo_nombre: str | None = None
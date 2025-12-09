import re
import os
from datetime import datetime
from modelos_datos import FacturaEndesaCliente 

# --------------------------------------------------------------------------------
# --- FUNCIONES AUXILIARES PARA LECTURA POR REGEX ---
# --------------------------------------------------------------------------------

# Usamos re.DOTALL (re.S) para que el punto coincida con saltos de línea,
RE_FLAG = re.DOTALL

def _clean_text(text: str) -> str:
    """Limpia el texto, eliminando los prefijos de Namespace para simplificar el Regex."""
    # Reemplaza nsX:Tag con Tag. Este paso es crucial para la robustez del Regex.
    return re.sub(r'</?\w+:', '<', text)

def _extract_simple_value(file_content: str, tag_name: str, is_float: bool = False, is_date: bool = False, default=None):
    """Extrae la primera ocurrencia de un valor basado en su etiqueta (ignorando Namespaces)."""
    # Patrón: <TagNombre>(Valor)</TagNombre>
    pattern = r"<" + re.escape(tag_name) + r">([\s\S]*?)</" + re.escape(tag_name) + r">"
    
    match = re.search(pattern, file_content, RE_FLAG)
    if match:
        value = match.group(1).strip()
        if is_float:
            try:
                # Limpiamos el valor numérico (quitando cualquier cosa que no sea dígito o punto)
                return float(re.sub(r'[^\d.]', '', value.replace(',', '.')))
            except ValueError:
                return 0.0
        return value
    
    return default if default is not None else (0.0 if is_float else None)


def _extract_cost_by_description(file_content: str, item_description: str) -> float:
    """
    Busca una ItemDescription específica dentro del XML y captura el TotalCost inmediatamente
    después dentro del mismo bloque InvoiceLine.
    """
    # Patrón: <ItemDescription>DESCRIPCION</ItemDescription>.*?<TotalCost>VALOR</TotalCost>
    pattern = (
        r"<ItemDescription>\s*" + re.escape(item_description) + r"\s*</ItemDescription>"
        r"[\s\S]*?<TotalCost>([0-9.]+)</TotalCost>"
    )
    
    match = re.search(pattern, file_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        cost_str = match.group(1).strip()
        try:
            return float(cost_str)
        except ValueError:
            return 0.0
            
    return 0.0


# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO (REGEX) ---
# --------------------------------------------------------------------------------

def procesar_xml_local(factura: FacturaEndesaCliente, filepath: str):
    """
    Lee el archivo XML como texto plano y extrae los datos usando Regex.
    """
    
    # 1. Lectura y limpieza del archivo
    try:
        # !!! CAMBIO CLAVE: Cambiar 'utf-8' por 'latin-1' o 'cp1252' !!!
        with open(filepath, 'r', encoding='latin-1') as f:
            raw_content = f.read()
            content = _clean_text(raw_content) # Eliminamos NS para facilitar el Regex
            
    except FileNotFoundError:
        print(f"   -> [ERROR XML] Archivo no encontrado en: {filepath}")
        return
    except Exception as e:
        print(f"   -> [ERROR XML] Error al leer el archivo (código): {e}")
        return

    # --- INICIALIZACIÓN DE VARIABLES PARA CÁLCULO ---
    total_importe_potencia = 0.0
    total_kw_consumo = 0.0
    total_importe_consumo = 0.0
    total_exceso_potencia = 0.0
    
    # --- 2. EXTRACCIÓN DE DATOS DE CABECERA Y GENERALES ---
    
    factura.tarifa = _extract_simple_value(content, 'CodigoTarifa', default='N/A')
    factura.direccion_suministro = _extract_simple_value(content, 'Direccion', default='N/A')
    
    # Mes Facturado (de TransactionDate)
    transaction_date = _extract_simple_value(content, 'TransactionDate')
    if transaction_date:
        try:
            dt = datetime.strptime(transaction_date, '%Y-%m-%d')
            factura.mes_facturado = dt.strftime('%Y-%m')
        except ValueError:
            pass # Se queda en None
    
    # Base Imponible: <TotalGrossAmountBeforeTaxes>
    factura.importe_base_imponible = _extract_simple_value(content, 'TotalGrossAmountBeforeTaxes', is_float=True)
    
    # Totales Finales
    factura.importe_facturado = _extract_simple_value(content, 'InvoiceTotal', is_float=True)
    factura.importe_total_final = _extract_simple_value(content, 'InstallmentAmount', is_float=True)
    factura.fecha_de_cobro_en_banco = _extract_simple_value(content, 'InstallmentDueDate', default='')
    
    # --- 3. EXTRACCIÓN Y CÁLCULO DE COSTES DETALLADOS (TotalCost por descripción) ---
    
    # A. Potencia (Pot. Px)
    for i in range(1, 7):
        attr = f'potencia_p{i}'
        desc = f'Pot. P{i}'
        cost = _extract_cost_by_description(content, desc)
        setattr(factura, attr, cost)
        total_importe_potencia += cost
    factura.importe_de_potencia = round(total_importe_potencia, 2)
    
    # B. Consumo (Importe_consumo_Px y Energia precio indexado Px)
    total_importe_consumo = 0.0
    
    # B1/B2: Consumo Fijo y Energía Indexada
    for i in range(1, 7):
        # Consumo Fijo
        desc_consumo = f'Consumo P{i}'
        cost_consumo = _extract_cost_by_description(content, desc_consumo)
        setattr(factura, f'importe_consumo_p{i}', cost_consumo)
        total_importe_consumo += cost_consumo
        
        # Energía Precio Indexado
        desc_index = f'Energia precio indexado P{i}'
        cost_index = _extract_cost_by_description(content, desc_index)
        setattr(factura, f'energia_precio_indexado_p{i}', cost_index)
        total_importe_consumo += cost_index
        
    factura.importe_consumo = round(total_importe_consumo, 2)
    
    # C. Exceso de Potencia (Exceso Pot. Px)
    total_exceso_potencia = 0.0
    for i in range(1, 7):
        attr = f'importe_exceso_potencia_p{i}'
        desc = f'Exceso Pot. P{i}'
        cost = _extract_cost_by_description(content, desc)
        setattr(factura, attr, cost)
        total_exceso_potencia += cost
    factura.importe_exceso_potencia = round(total_exceso_potencia, 2)
    
    # D. Conceptos Únicos
    factura.importe_impuesto_electrico = _extract_cost_by_description(content, 'Impuesto Electricidad')
    factura.importe_alquiler_equipos = _extract_cost_by_description(content, 'Alquiler del contador')
    # Nota: Usamos la versión de búsqueda que contiene 'Bono Social' para la robustez
    factura.importe_bono_social = _extract_cost_by_description(content, 'Bono Social') 

    # --- 4. EXTRACCIÓN DE CONSUMOS (kWh) ---
    
    consumo_kw_fields = {f'consumo_kw_p{i}': f'AEA{i}' for i in range(1, 7)}
    total_kw = 0.0
    
    # Patrón: <CodigoDH>DH_CODE</CodigoDH>.*?<ConsumoCalculado>VALOR</ConsumoCalculado>
    for attr, dh_code in consumo_kw_fields.items():
        pattern = (
            r"<CodigoDH>" + re.escape(dh_code) + r"</CodigoDH>"
            r"[\s\S]*?<ConsumoCalculado>([0-9.]+)</ConsumoCalculado>"
        )
        
        match = re.search(pattern, content, RE_FLAG)
        if match:
            consumo = float(match.group(1).strip())
            setattr(factura, attr, consumo)
            total_kw += consumo
        else:
            setattr(factura, attr, 0.0) 
            
    factura.kw_totales = round(total_kw, 2)
    
    # Días (Extraído del alquiler del contador)
    # Patrón para CodigoDH y ConsumoCalculado
    try:
        # Extraemos la cantidad de días del tag <Quantity> asociado a 'Alquiler del contador'
        quantity_match = re.search(
            r"<ItemDescription>\s*Alquiler del contador\s*</ItemDescription>[\s\S]*?<Quantity>([0-9.]+)</Quantity>",
            content,
            RE_FLAG
        )
        if quantity_match:
            factura.num_dias = int(float(quantity_match.group(1).strip()))
    except Exception:
        # Si falla el parseo, se queda en None o 0 (ya que es un int)
        pass


    print(f"   -> [PARSE XML/REGEX] Éxito. Base Imponible: {factura.importe_base_imponible}, Consumo Total: {factura.kw_totales}")
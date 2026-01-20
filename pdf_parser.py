import os
import json
from logs import escribir_log
from openai import OpenAI
from modelos_datos import FacturaEndesaDistribucion
from datetime import datetime

def procesar_pdf_local(factura_obj: FacturaEndesaDistribucion, ruta_pdf: str) -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] No se encontró la variable de entorno OPENAI_API_KEY")
        return False

    client = OpenAI(api_key=api_key)
    file_id = None

    try:
        # 1. Preparar esquema dinámico compatible con Strict Mode
        esquema_pydantic = FacturaEndesaDistribucion.model_json_schema()
        
        # SOLUCIÓN AL ERROR: 
        # 1. Forzar additionalProperties a False
        # 2. Poner TODOS los campos de 'properties' dentro de 'required'
        esquema_pydantic["additionalProperties"] = False
        esquema_pydantic["required"] = list(esquema_pydantic["properties"].keys())

        # 2. Cargar prompt y subir archivo (se asume que existen)
        with open("prompt_distribucion.txt", "r", encoding="utf-8") as f:
            prompt_text = f.read()

        with open(ruta_pdf, "rb") as f:
            file_upload = client.files.create(file=f, purpose="assistants")
            file_id = file_upload.id

        # 3. Llamada a la API
        response = client.responses.create(
            model="gpt-4o",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file_id},
                        {"type": "input_text", "text": prompt_text}
                    ]
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "extraccion_factura_electrica",
                    "strict": True,
                    "schema": esquema_pydantic
                }
            }
        )

        # 4. Mezcla inteligente de datos
        datos_extraidos = json.loads(response.output_text)

        for campo, valor_ocr in datos_extraidos.items():
            # Saltamos si el OCR no devolvió nada útil
            if valor_ocr is None or str(valor_ocr).lower() == "null" or valor_ocr == "":
                # escribir_log(
                #         f"\t->[!] Valor no extraido {factura_obj.numero_factura} \n\t\t\t\t\t\t\t| Campo: '{campo}' | "
                #         f"Valor: '{valor_ocr}'"
                #     )
                continue

            # Obtenemos el valor que tiene el objeto actualmente
            valor_actual = getattr(factura_obj, campo)
            
            # Obtenemos el valor por defecto definido en el modelo Pydantic para ese campo
            valor_por_defecto = FacturaEndesaDistribucion.model_fields[campo].default

            # CASO A: El objeto tiene el valor por defecto (no ha sido registrado aún)
            if valor_actual == valor_por_defecto:
                setattr(factura_obj, campo, valor_ocr)
                # escribir_log(
                #         f"\t->[OK] Valor incluido {factura_obj.numero_factura} \n\t\t\t\t\t\t\t| Campo: '{campo}' | "
                #         f"Valor Incluido: '{valor_ocr}'"
                #     )
            
            # CASO B: El objeto YA tiene un valor distinto al por defecto
            else:
                # Comparamos si el valor extraído coincide con el que ya teníamos
                if valor_actual != valor_ocr:
                    # escribir_log(
                    #     f"\t->[!] Discrepancia en Factura {factura_obj.numero_factura} \n\t\t\t\t\t\t\t| Campo: '{campo}' | "
                    #     f"Valor en Objeto: '{valor_actual}' VS Valor OCR: '{valor_ocr}'"
                    # )
                    # Opcional: Aquí podrías decidir si sobreescribir o no. 
                    # Por ahora, mantenemos el valor del objeto y solo avisamos.
                    pass
        
        # === 5. POST-PROCESAMIENTO Y CÁLCULOS AUTOMÁTICOS ===
        
        # A. Cálculo del Mes Facturado y Número de Días
        if factura_obj.fecha_fin_periodo and factura_obj.fecha_fin_periodo != "N/A":
            try:
                nombres_meses = {
                    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
                    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
                    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
                }
                
                # Normalizamos formatos de fecha (DD-MM-YYYY)
                f_fin_str = factura_obj.fecha_fin_periodo.replace("/", "-")
                dt_fin = datetime.strptime(f_fin_str, '%d-%m-%Y')
                
                # Asignar nombre del mes 
                factura_obj.mes_facturado = nombres_meses.get(dt_fin.month, "DESCONOCIDO")

                # Calcular num_dias si existe fecha de inicio 
                if factura_obj.fecha_inicio_periodo and factura_obj.fecha_inicio_periodo != "N/A":
                    f_ini_str = factura_obj.fecha_inicio_periodo.replace("/", "-")
                    dt_ini = datetime.strptime(f_ini_str, '%d-%m-%Y')
                    
                    # Diferencia de días (valor absoluto) 
                    diferencia = abs((dt_fin - dt_ini).days)
                    factura_obj.num_dias = diferencia
                    
            except Exception as e:
                escribir_log(f"Error en cálculos de fechas/días: {e}")

        # B. Cálculo de Importe de Potencia (Peaje + Cargos) 
        p_peaje = factura_obj.termino_de_potencia_peaje or 0.0
        p_cargos = factura_obj.termino_de_potencia_cargos or 0.0
        factura_obj.importe_de_potencia = round(p_peaje + p_cargos, 2)

        # C. Cálculo de Importe ATR (Energía Peaje + Energía Cargos) 
        e_peaje = factura_obj.termino_de_energia_peaje or 0.0
        e_cargos = factura_obj.termino_de_energia_cargos or 0.0
        factura_obj.importe_atr = round(e_peaje + e_cargos, 2)

        
        return True

    except Exception as e:
        print(f"[ERROR] Fallo en procesar_pdf_local: {str(e)}")
        return False
    finally:
        if file_id:
            client.files.delete(file_id)
from navegador import NavegadorAsync, TEMP_DOWNLOAD_ROOT # Importamos la clase base y la ruta de descarga
import asyncio
import re
import csv # Necesario para exportar los logs
import os # Necesario para manejar rutas de archivos
from playwright.async_api import Page, TimeoutError, Locator # Importamos Page, TimeoutError, Locator
from modelos_datos import FacturaEndesaCliente # Importamos la clase modelo de datos (AHORA ES PYDANTIC)
# IMPORTACIÓN DEL PARSER XML
from xml_parser import procesar_xml_local 

# --- CONSTANTES DE ENDESA ---
URL_LOGIN = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 
URL_BUSQUEDA_FACTURAS = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"

# Credenciales REALES proporcionadas por el usuario
USER = "pfombellav@somosgrupomas.com" 
PASSWORD = "Guillena2024*" 
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN" # Constante para el filtro siempre aplicado

# LÍMITE DE FILAS Y ROBUSTEZ
TABLE_LIMIT = 50 
MAX_LOGIN_ATTEMPTS = 5 # NÚMERO MÁXIMO DE INTENTOS DE LOGIN

# Selector que aparece SÓLO después de un login exitoso (El botón de cookies)
SUCCESS_INDICATOR_SELECTOR = '#truste-consent-button' 

# --- CONSTANTE DE LOGGING Y CARPETAS DE DESCARGA ---
LOG_FILE_NAME_TEMPLATE = "facturas_endesa_log_{cups}.csv"

# Definición de las subcarpetas usando la constante TEMP_DOWNLOAD_ROOT de navegador.py
DOWNLOAD_FOLDERS = {
    'PDF': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Endesa_PDFs'),
    'XML': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Endesa_XMLs'),
    'HTML': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Endesa_HTMLs')
}
# Aseguramos que todas las carpetas existan
for folder in DOWNLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)
print(f"[INFO] Carpetas de descarga configuradas en: {TEMP_DOWNLOAD_ROOT}")


# --- FUNCIONES DE UTILIDAD PARA EXTRACCIÓN Y LOGGING (INALTERADAS) ---

def _clean_and_convert_float(text: str) -> float:
    """Limpia una cadena de texto de importe (ej. '4697.73 €') y la convierte a float."""
    cleaned_text = re.sub(r'[^\d,\.]', '', text).replace(',', '.')
    try:
        return float(cleaned_text)
    except ValueError:
        return 0.0

async def _extraer_texto_de_td(td: Locator) -> str:
    """Extrae texto de una celda de tabla."""
    try:
        lightning_element = td.locator("lightning-formatted-date-time, button, a")
        if await lightning_element.count() > 0:
            return (await lightning_element.first.inner_text()).strip() 
        
        text = await td.inner_text() 
        return text.strip() if "No hay resultados" not in text else ""
    except Exception:
        return ""

def _exportar_log_csv(facturas: list[FacturaEndesaCliente], filepath: str):
    """
    Exporta TODA la metadata y datos detallados de las facturas 
    extraídas (incluyendo el parseo XML) a un archivo CSV.
    """
    # Se recomienda que esta función se mantenga igual o se elimine si el log 
    # se gestiona fuera de la API, pero la mantenemos por ahora.
    fieldnames = [
        # Metadata de la tabla
        'fecha_emision', 'numero_factura', 'fecha_inicio_periodo', 'fecha_fin_periodo', 
        'importe_total_tabla', 'contrato', 'cups', 'secuencial', 'estado_factura', 
        'fraccionamiento', 'tipo_factura', 'descarga_selector',
        # Datos detallados (XML/OCR)
        'mes_facturado', 'tarifa', 'direccion_suministro', 
        'potencia_p1', 'potencia_p2', 'potencia_p3', 'potencia_p4', 
        'potencia_p5', 'potencia_p6', 'importe_de_potencia', 'num_dias', 
        'consumo_kw_p1', 'consumo_kw_p2', 'consumo_kw_p3', 'consumo_kw_p4', 
        'consumo_kw_p5', 'consumo_kw_p6', 'kw_totales', 'importe_consumo', 
        'importe_bono_social', 'importe_impuesto_electrico', 'importe_alquiler_equipos', 
        'importe_otros_conceptos', 'importe_exceso_potencia', 'importe_reactiva', 
        'importe_base_imponible', 'importe_facturado', 'fecha_de_vencimiento', 
        'importe_total_final', 'fecha_de_cobro_en_banco'
    ]
    
    # NOTA: Pydantic.BaseModel tiene un método .dict() o .model_dump()
    # que simplifica esto, pero usamos getattr para la compatibilidad con el código original.
    data_to_write = [{key: getattr(f, key, '') for key in fieldnames} for f in facturas]

    try:
        print(f"[DEBUG_CSV] Intentando escribir {len(data_to_write)} filas en {filepath}")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(data_to_write)
        print(f"✅ Log CSV exportado exitosamente a: {os.path.abspath(filepath)}")
    except Exception as e:
        print(f"❌ Error al exportar el log CSV a {filepath}: {e}")

async def _wait_for_data_load(page: Page, timeout: int = 20000):
    """Espera a que los datos dinámicos de la primera fila estén cargados y estables."""
    importe_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(5)'
    estado_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(9)'
    
    await page.locator(importe_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator(estado_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator('span.pagination-flex-central').wait_for(state="visible", timeout=5000)


# --- LÓGICA DE DESCARGA LOCAL Y EXTRACCIÓN (INALTERADA) ---

async def _descargar_archivo_fila(page: Page, row_locator: Locator, factura: FacturaEndesaCliente, doc_type: str) -> str | None:
    """
    Intenta descargar un tipo de archivo (PDF, XML, HTML) haciendo clic en el botón de la fila
    y guardándolo localmente.
    """
    
    doc_type = doc_type.upper() # PDF, XML, HTML
    
    if doc_type == 'PDF':
        button_col_index = 13
        file_ext = 'pdf'
        button_locator_selector = f'button[value*="{factura.descarga_selector}"]' 
    elif doc_type == 'HTML':
        button_col_index = 12
        file_ext = 'html'
        button_locator_selector = 'button:has-text("HTML")' 
    elif doc_type == 'XML':
        button_col_index = 11
        file_ext = 'xml'
        button_locator_selector = 'button:has-text("@")' 
    else:
        return None

    try:
        button_locator = row_locator.locator(f'td').nth(button_col_index).locator(button_locator_selector)
        target_folder = DOWNLOAD_FOLDERS[doc_type]
        filename = f"{factura.cups}_{factura.numero_factura}.{file_ext}"
        save_path = os.path.join(target_folder, filename)
        
        async with page.expect_download(timeout=30000) as download_info:
            await button_locator.click(timeout=10000)
            
        download = await download_info.value
        await download.save_as(save_path)
        
        print(f"   -> [DESCARGA {doc_type}] Guardado en: {save_path}")
        
        return save_path
        
    except TimeoutError:
        print(f"   -> [ADVERTENCIA {doc_type}] Timeout (30s) al hacer clic o iniciar la descarga. Omitiendo.")
        return None
    except Exception as e:
        print(f"   -> [ERROR {doc_type}] Fallo inesperado en la descarga: {e}")
        return None


async def _extraer_pagina_actual(page: Page) -> list[FacturaEndesaCliente]:
    """
    Extrae los datos de todas las filas visibles en la página actual de la tabla de resultados.
    Esta función también activa la descarga local e INTEGRA EL PARSEO XML.
    """
    facturas_pagina: list[FacturaEndesaCliente] = []
    rows = page.locator('table#example1 tbody tr')
    row_count = await rows.count()
    if row_count == 0:
        return facturas_pagina

    print(f"-> Extrayendo {row_count} filas de la tabla actual...")
    
    for i in range(row_count):
        row = rows.nth(i)
        tds = row.locator('td')
        
        try:
            # Extracción de metadata
            pdf_value = await tds.nth(13).locator('button').get_attribute("value") or ""
            
            # 1. Crear instancia de Factura (solo metadata)
            factura = FacturaEndesaCliente(
                fecha_emision=await _extraer_texto_de_td(tds.nth(0)),
                numero_factura=await _extraer_texto_de_td(tds.nth(1)),
                fecha_inicio_periodo=await _extraer_texto_de_td(tds.nth(2)),
                fecha_fin_periodo=await _extraer_texto_de_td(tds.nth(3)),
                importe_total_tabla=_clean_and_convert_float(await _extraer_texto_de_td(tds.nth(4))),
                contrato=await _extraer_texto_de_td(tds.nth(5)),
                cups=await _extraer_texto_de_td(tds.nth(6)),
                secuencial=await _extraer_texto_de_td(tds.nth(7)),
                estado_factura=await _extraer_texto_de_td(tds.nth(8)),
                fraccionamiento=await _extraer_texto_de_td(tds.nth(9)),
                tipo_factura=await _extraer_texto_de_td(tds.nth(10)),
                descarga_selector=pdf_value, 
            )
            
            # 2. Descargar localmente los 3 archivos
            print(f"[INFO] Iniciando descarga para {factura.numero_factura} ({factura.cups})...")
            
            xml_save_path = await _descargar_archivo_fila(page, row, factura, 'XML')
            await _descargar_archivo_fila(page, row, factura, 'PDF')
            await _descargar_archivo_fila(page, row, factura, 'HTML')
            
            # 3. INTEGRACIÓN DEL PARSEO XML: Si el XML se descargó, lo procesamos.
            if xml_save_path:
                print(f"[INFO] Procesando XML para {factura.numero_factura}...")
                procesar_xml_local(factura, xml_save_path)
            
            facturas_pagina.append(factura)
            
        except Exception as e:
            print(f"[DEBUG_EXTRACTION] Fallo al procesar fila {i}: {e}")
            continue

    return facturas_pagina

async def leer_tabla_facturas(page: Page) -> list[FacturaEndesaCliente]:
    """Bucle principal para leer TODAS las páginas de la tabla de resultados."""
    facturas_totales: list[FacturaEndesaCliente] = []
    page_num = 1
    
    tabla_selector = 'div.style-table.contenedorGeneral table#example1'
    await page.wait_for_selector(tabla_selector, timeout=30000)
    print("Tabla de resultados cargada. Iniciando paginación defensiva...")
    
    next_button_selector = 'button.pagination-flex-siguiente'
    
    while True:
        print(f"\n--- Procesando Página {page_num} ---")
        
        try:
            await _wait_for_data_load(page, timeout=10000) 
        except TimeoutError:
            print("Advertencia: Los datos dinámicos no cargaron en el tiempo esperado. Extrayendo datos incompletos.")
            
        facturas_pagina = await _extraer_pagina_actual(page)
        
        print(f"[DEBUG_LOOP] Página {page_num} extrajo {len(facturas_pagina)} filas.")
        
        facturas_totales.extend(facturas_pagina)
        
        next_button = page.locator(next_button_selector)
        is_disabled = await next_button.is_disabled()
        
        if is_disabled:
            print(f"Final de la tabla alcanzado en la página {page_num}.")
            break
            
        try:
            await next_button.click(timeout=10000)
            await page.wait_for_timeout(500) 
            page_num += 1
        except TimeoutError:
            print("Error: Fallo al hacer clic en 'SIGUIENTE' (Timeout). Finalizando bucle.")
            break
            
    print(f"[DEBUG_LOOP_END] Retornando {len(facturas_totales)} elementos.")
    return list(facturas_totales)


# --- FUNCIONES AUXILIARES DE FLUJO (INALTERADAS) ---

async def _iniciar_sesion(page: Page, username: str, password: str) -> bool:
    """Función interna para manejar la lógica de autenticación en Endesa."""
    print(f"Intentando iniciar sesión con usuario: {username}")
    
    try:
        await page.wait_for_selector('form.slds-form', timeout=10000)

        # 1. Rellenar campos
        await page.fill('input[name="Username"]', username)
        await page.fill('input[name="password"]', password)
        
        # 2. Hacer click en el botón de iniciar sesión
        login_button_selector = 'button:has-text("ACCEDER")'
        await page.click(login_button_selector)
        
        # 3. Esperar el indicador de éxito (el botón de cookies) en la nueva página
        await page.wait_for_selector(SUCCESS_INDICATOR_SELECTOR, timeout=10000)
        
        print(f"Login exitoso. Página de destino cargada.")
        return True

    except TimeoutError:
        print("Fallo en el Login: El tiempo de espera para cargar el indicador de éxito (cookies o dashboard) ha expirado.")
        final_url = page.url
        if final_url.startswith(URL_LOGIN) and await page.is_visible('div[class*="error"]'):
             print("Razón: Credenciales incorrectas.")
        return False
    except Exception as e:
        print(f"Error inesperado durante la autenticación: {e}")
        return False


async def _aceptar_cookies(page: Page):
    """Función interna para aceptar el banner de cookies si está presente."""
    cookie_button_selector = '#truste-consent-button'
    
    try:
        await page.wait_for_selector(cookie_button_selector, timeout=5000)
        await page.click(cookie_button_selector)
        print("Cookies aceptadas.")
        await page.wait_for_timeout(500) 
        
    except TimeoutError:
        print("Banner de cookies no detectado. Continuando...")
        pass
    except Exception as e:
        print(f"Error al intentar aceptar las cookies: {e}")


async def realizar_busqueda_facturas(page: Page, grupo_empresarial: str, cups: str, fecha_desde: str, fecha_hasta: str):
    """
    Navega al asistente de búsqueda y aplica el filtro del grupo empresarial, el CUPS
    y el rango de fechas.
    """
    print(f"\n--- INICIO DE BÚSQUEDA: {cups} ({grupo_empresarial}) ---")
    
    await page.goto(URL_BUSQUEDA_FACTURAS, wait_until="domcontentloaded")
    print("Navegación al asistente de búsqueda completada.")

    main_filter_container_selector = 'div.filter-padd-container'
    await page.wait_for_selector(main_filter_container_selector, timeout=20000)
    print("Contenedor de filtros detectado. Iniciando interacción...")

    # --- FILTRO 1: GRUPO EMPRESARIAL ---
    grupo_empresarial_button = 'button[name="periodo"]:has-text("Grupo empresarial")'
    await page.wait_for_selector(grupo_empresarial_button, timeout=15000)
    await page.click(grupo_empresarial_button)

    input_selector = 'input[placeholder="Buscar"]'
    await page.wait_for_selector(input_selector, timeout=10000)
    await page.fill(input_selector, grupo_empresarial)

    opcion_selector = f'span[role="option"] >> text="{grupo_empresarial}"'
    await page.wait_for_timeout(500) 
    await page.wait_for_selector(opcion_selector, timeout=10000)
    await page.click(opcion_selector)
    print(f"Filtro aplicado: Grupo empresarial '{grupo_empresarial}'.")

    # --- FILTRO 2: CUPS ---
    cups_button = 'button[name="periodo"]:has-text("CUPS20/CUPS22")'
    await page.click(cups_button)

    await page.wait_for_selector(input_selector, timeout=10000) 
    await page.fill(input_selector, cups)

    cups_opcion_selector = f'span[role="option"] >> text="{cups}"'
    await page.wait_for_timeout(500) 
    await page.wait_for_selector(cups_opcion_selector, timeout=10000)
    await page.click(cups_opcion_selector)
    print(f"Filtro aplicado: CUPS '{cups}'.")
    
    # --- FILTRO 3: FECHA DE EMISIÓN (DESDE / HASTA) ---
    selector_fecha_desde = page.get_by_label("Desde", exact=True).nth(1)
    selector_fecha_hasta = page.get_by_label("Hasta", exact=True).nth(1)

    await selector_fecha_desde.wait_for(timeout=10000)
    await selector_fecha_desde.fill(fecha_desde)
    await selector_fecha_hasta.fill(fecha_hasta)
    print(f"Filtro aplicado: Fechas Desde '{fecha_desde}' hasta '{fecha_hasta}'.")

    # --- AJUSTAR LÍMITE DE RESULTADOS ---
    slider_input = page.get_by_label("Limite")
    await slider_input.wait_for(timeout=10000) 
    await slider_input.fill(str(TABLE_LIMIT)) 
    await page.wait_for_selector(f'span.slds-slider__value:has-text("{TABLE_LIMIT}")', timeout=5000)
    
    # --- CLIC EN BOTÓN BUSCAR ---
    buscar_button_selector = 'button.slds-button_brand:has-text("Buscar")'
    await page.wait_for_selector(buscar_button_selector, timeout=10000)
    await page.click(buscar_button_selector)
    
    tabla_selector = 'div.style-table.contenedorGeneral table#example1'
    await page.wait_for_selector(tabla_selector, timeout=60000)
    
    print("--- FILTRADO COMPLETADO. LISTO PARA LA LECTURA DE DATOS ---")


# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL PARA LA API (Acepta Parámetros) ---
# --------------------------------------------------------------------------------

async def ejecutar_robot_api(cups: str, fecha_desde: str, fecha_hasta: str) -> list[FacturaEndesaCliente]:
    """
    Función principal que orquesta el robot completo: login, búsqueda, lectura de datos
    y parseo XML, usando los parámetros provistos por la llamada API.
    """
    robot = NavegadorAsync()
    facturas_extraidas = []
    login_successful = False
    
    try:
        # 1. Bucle de Reintentos de Login
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            print(f"\n[Intento {attempt}/{MAX_LOGIN_ATTEMPTS}] Iniciando sesión...")
            
            await robot.iniciar()
            await robot.goto_url(URL_LOGIN)

            login_successful = await _iniciar_sesion(robot.get_page(), USER, PASSWORD)

            if login_successful:
                break
            
            # Si falla, cerramos el navegador y esperamos antes de reintentar
            await robot.cerrar()
            if attempt < MAX_LOGIN_ATTEMPTS:
                print(f"Login fallido en el intento {attempt}. Esperando 5 segundos antes de reintentar.")
                await asyncio.sleep(5) 
            else:
                # Si falla el último intento, lanzamos un error que la API manejará
                raise Exception(f"Fallo crítico: No se pudo iniciar sesión después de {MAX_LOGIN_ATTEMPTS} intentos.")

        if not login_successful:
            # Esto no debería ejecutarse si la excepción se lanza arriba, pero es un seguro
            raise Exception("Fallo crítico: El robot terminó el bucle de intentos de login sin éxito.")
            
        page = robot.get_page()

        # 2. Manejo de Cookies
        await _aceptar_cookies(page)
        
        # 3. Navegación y Búsqueda (Usando los parámetros cups, fecha_desde, fecha_hasta)
        await realizar_busqueda_facturas(page, GRUPO_EMPRESARIAL, cups, fecha_desde, fecha_hasta)
        
        # 4. Extracción de datos de la tabla (Descarga y Parseo XML incluidos)
        facturas_metadata = await leer_tabla_facturas(page) 
        facturas_extraidas = facturas_metadata

        # 5. Log y Resumen (Opcional, para la consola del servidor)
        if facturas_metadata:
            log_filepath_dynamic = LOG_FILE_NAME_TEMPLATE.format(cups=cups)
            _exportar_log_csv(facturas_metadata, log_filepath_dynamic)
            print(f"RESUMEN: {len(facturas_extraidas)} facturas procesadas para {cups}.")

        # Devolver la lista de objetos FacturaEndesaCliente
        return facturas_extraidas

    except Exception as e:
        print(f"Ocurrió un error crítico en la orquestación del robot: {e}")
        # Relanzamos la excepción para que el endpoint de FastAPI la capture y devuelva un error HTTP 500
        raise e
    finally:
        # ** IMPORTANTE: Cerramos el navegador siempre, ya que está ejecutando en un servidor **
        if hasattr(robot, 'browser') and robot.browser:
            await robot.cerrar()
            print("\nSesión de navegador cerrada.")
        else:
             print("\nEl navegador ya está cerrado.")


# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
# ELIMINAMOS LA LÓGICA DE EJECUCIÓN MANUAL PARA EVITAR CONFLICTOS CON UVICORN
if __name__ == "__main__":
    print("robotEndesa.py se está ejecutando en modo manual, pero se detiene la ejecución asíncrona automática.")
    print("Para probar, llame a 'ejecutar_robot_api' manualmente con 'asyncio.run()'.")
from navegador import NavegadorAsync, TEMP_DOWNLOAD_ROOT # Importamos la clase base y la ruta de descarga
import asyncio
import re
import csv # Necesario para exportar los logs
import os # Necesario para manejar rutas de archivos
from playwright.async_api import Page, TimeoutError, Locator # Importamos Page, TimeoutError, Locator
from modelos_datos import FacturaEndesaCliente # Importamos la clase modelo de datos (asumiendo que existe)

# --- CONSTANTES DE ENDESA ---
URL_LOGIN = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 
URL_BUSQUEDA_FACTURAS = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"

# Credenciales REALES proporcionadas por el usuario
USER = "pfombellav@somosgrupomas.com" 
PASSWORD = "Guillena2024*" 
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN" # Constante para el filtro siempre aplicado

# Datos de Filtro para la prueba (Formato DD/MM/YYYY)
FECHA_DESDE = "01/10/2025" 
FECHA_HASTA = "31/10/2025" 

# LÍMITE DE FILAS Y ROBUSTEZ
TABLE_LIMIT = 50 
MAX_LOGIN_ATTEMPTS = 5 # NÚMERO MÁXIMO DE INTENTOS DE LOGIN

# CUPS DE PRUEBA (Para la ejecución manual: un valor real del cliente)
TEST_CUPS = "ES0034111300275021NX0F" 

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


# --- FUNCIONES DE UTILIDAD PARA EXTRACCIÓN Y LOGGING ---

def _clean_and_convert_float(text: str) -> float:
    """Limpia una cadena de texto de importe (ej. '4697.73 €') y la convierte a float."""
    cleaned_text = re.sub(r'[^\d,\.]', '', text).replace(',', '.')
    try:
        return float(cleaned_text)
    except ValueError:
        return 0.0

async def _extraer_texto_de_td(td: Locator) -> str:
    """
    Extrae texto de una celda de tabla, manejando casos con <lightning-formatted-date-time>, 
    botones o enlaces.
    """
    try:
        lightning_element = td.locator("lightning-formatted-date-time, button, a")
        if await lightning_element.count() > 0:
            return (await lightning_element.first.inner_text()).strip() 
        
        text = await td.inner_text() 
        return text.strip() if "No hay resultados" not in text else ""
    except Exception:
        return ""

def _exportar_log_csv(facturas: list[FacturaEndesaCliente], filepath: str):
    """Exporta la metadata de las facturas extraídas a un archivo CSV."""
    fieldnames = [
        'numero_factura', 'cups', 'fecha_emision', 'fecha_inicio_periodo', 
        'fecha_fin_periodo', 'importe_total_tabla', 'contrato', 'secuencial',
        'estado_factura', 'fraccionamiento', 'tipo_factura', 
        'url_descarga_pdf', 'url_descarga_html', 'url_descarga_xml'
    ]
    
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
    """
    Espera a que los datos dinámicos de la primera fila estén cargados y estables.
    """
    importe_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(5)'
    estado_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(9)'
    
    await page.locator(importe_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator(estado_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator('span.pagination-flex-central').wait_for(state="visible", timeout=5000)
    
    # print("   -> Datos de la página cargados y estables.") # Reducimos el output


# --- LÓGICA DE DESCARGA LOCAL Y EXTRACCIÓN ---

async def _descargar_archivo_fila(page: Page, row_locator: Locator, factura: FacturaEndesaCliente, doc_type: str):
    """
    Intenta descargar un tipo de archivo (PDF, XML, HTML) haciendo clic en el botón de la fila
    y guardándolo localmente en la carpeta designada.
    """
    
    doc_type = doc_type.upper() # PDF, XML, HTML
    
    if doc_type == 'PDF':
        button_col_index = 13
        file_ext = 'pdf'
        # Usamos el valor del atributo (descarga_selector) para el locator, ya que el texto no es único.
        button_locator_selector = f'button[value*="{factura.descarga_selector}"]' 
    elif doc_type == 'HTML':
        button_col_index = 12
        file_ext = 'html'
        # Usamos el texto visible 'HTML'
        button_locator_selector = 'button:has-text("HTML")' 
    elif doc_type == 'XML':
        button_col_index = 11
        file_ext = 'xml'
        # Usamos el texto visible '@' (asumimos que es el que activa el XML/Digital)
        button_locator_selector = 'button:has-text("@")' 
    else:
        return False

    try:
        # 1. Localizar el botón de descarga
        button_locator = row_locator.locator(f'td').nth(button_col_index).locator(button_locator_selector)
        
        # 2. Definir la ruta de guardado local
        target_folder = DOWNLOAD_FOLDERS[doc_type]
        # Formato de nombre: [CUPS]_[Nº Factura].[ext]
        filename = f"{factura.cups}_{factura.numero_factura}.{file_ext}"
        save_path = os.path.join(target_folder, filename)
        
        # 3. Interceptar la descarga y hacer clic
        async with page.expect_download(timeout=30000) as download_info:
            await button_locator.click(timeout=10000)
            
        download = await download_info.value
        
        # 4. Guardar el archivo localmente
        await download.save_as(save_path)
        
        print(f"   -> [DESCARGA {doc_type}] Guardado en: {save_path}")
        
        return True
        
    except TimeoutError:
        print(f"   -> [ADVERTENCIA {doc_type}] Timeout (30s) al hacer clic o iniciar la descarga. Omitiendo.")
        return False
    except Exception as e:
        print(f"   -> [ERROR {doc_type}] Fallo inesperado en la descarga: {e}")
        return False


async def _extraer_pagina_actual(page: Page) -> list[FacturaEndesaCliente]:
    """
    Extrae los datos de todas las filas visibles en la página actual de la tabla de resultados.
    Esta función también activa la descarga local.
    """
    facturas_pagina: list[FacturaEndesaCliente] = []
    rows = page.locator('table#example1 tbody tr')
    row_count = await rows.count()
    if row_count == 0:
        return facturas_pagina

    print(f"-> Extrayendo {row_count} filas de la tabla actual...")
    
    BASE_URL = "https://endesa-atenea.my.site.com"

    for i in range(row_count):
        row = rows.nth(i)
        tds = row.locator('td')
        
        try:
            # Extracción de metadata
            pdf_button = tds.nth(13).locator('button')
            pdf_value = await pdf_button.get_attribute("value") or ""
            
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
                url_descarga_pdf=BASE_URL + pdf_value if pdf_value.startswith('/') else BASE_URL + '/...',
                url_descarga_html=f"{BASE_URL}/html-visor?id={await tds.nth(12).locator('button').get_attribute('id')}&cups={await tds.nth(12).locator('button').get_attribute('value')}",
                url_descarga_xml=f"{BASE_URL}/xml-download?id={await tds.nth(11).locator('button').get_attribute('id')}", 
            )
            
            # 2. Descargar localmente los 3 archivos
            print(f"[INFO] Iniciando descarga para {factura.numero_factura} ({factura.cups})...")
            await _descargar_archivo_fila(page, row, factura, 'PDF')
            await _descargar_archivo_fila(page, row, factura, 'XML')
            await _descargar_archivo_fila(page, row, factura, 'HTML')
            
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


# --- FUNCIONES DE FLUJO DE TRABAJO ---

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
        
        # Si la ejecución llega aquí sin timeout, el login fue exitoso.
        print(f"Login exitoso. Página de destino cargada.")
        return True

    except TimeoutError:
        print("Fallo en el Login: El tiempo de espera para cargar el indicador de éxito (cookies o dashboard) ha expirado.")
        # Lógica de comprobación de errores (mantener para debug)
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
        # Espera un máximo de 5 segundos a que el botón sea visible
        await page.wait_for_selector(cookie_button_selector, timeout=5000)
        
        # Si el selector se encuentra, hacemos clic
        await page.click(cookie_button_selector)
        print("Cookies aceptadas.")
        
        await page.wait_for_timeout(500) # Pequeña pausa para que el banner desaparezca
        
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
    
    # 1. Navegar a la página de búsqueda
    await page.goto(URL_BUSQUEDA_FACTURAS, wait_until="domcontentloaded")
    print("Navegación al asistente de búsqueda completada.")

    # NUEVA ESPERA: Asegurar que el contenedor principal de filtros ha cargado
    main_filter_container_selector = 'div.filter-padd-container'
    await page.wait_for_selector(main_filter_container_selector, timeout=20000)
    print("Contenedor de filtros detectado. Iniciando interacción...")

    # --- FILTRO 1: GRUPO EMPRESARIAL ---

    # 2. Pulsar en el botón 'Grupo empresarial' para abrir el desplegable
    grupo_empresarial_button = 'button[name="periodo"]:has-text("Grupo empresarial")'
    await page.wait_for_selector(grupo_empresarial_button, timeout=15000)
    await page.click(grupo_empresarial_button)
    print("Click en el botón 'Grupo empresarial'.")

    # 3. Rellenar el campo de búsqueda con el texto
    input_selector = 'input[placeholder="Buscar"]'
    await page.wait_for_selector(input_selector, timeout=10000)
    await page.fill(input_selector, grupo_empresarial)
    print(f"Texto introducido: '{grupo_empresarial}'.")

    # 4. Seleccionar la opción de la lista desplegable
    opcion_selector = f'span[role="option"] >> text="{grupo_empresarial}"'
    await page.wait_for_timeout(500) 
    await page.wait_for_selector(opcion_selector, timeout=10000)
    await page.click(opcion_selector)
    print(f"Seleccionado '{grupo_empresarial}' en el desplegable.")

    # --- FILTRO 2: CUPS ---
    
    # 5. Pulsar en el botón CUPS20/CUPS22 para abrir el desplegable
    cups_button = 'button[name="periodo"]:has-text("CUPS20/CUPS22")'
    await page.click(cups_button)
    print("Click en el botón 'CUPS'.")

    # 6. Rellenar el campo de búsqueda con el CUPS
    await page.wait_for_selector(input_selector, timeout=10000) # Reutilizamos el selector de búsqueda
    await page.fill(input_selector, cups)
    print(f"CUPS introducido: '{cups}'.")

    # 7. Seleccionar la opción CUPS de la lista desplegable
    cups_opcion_selector = f'span[role="option"] >> text="{cups}"'
    await page.wait_for_timeout(500) 
    await page.wait_for_selector(cups_opcion_selector, timeout=10000)
    await page.click(cups_opcion_selector)
    print(f"Seleccionado '{cups}' en el desplegable.")
    
    # --- FILTRO 3: FECHA DE EMISIÓN (DESDE / HASTA) ---
    print("\nAplicando filtros de Fecha de Emisión...")
    
    # Usamos get_by_label() y nth(1) para apuntar al segundo par 'Desde/Hasta'
    selector_fecha_desde = page.get_by_label("Desde", exact=True).nth(1)
    selector_fecha_hasta = page.get_by_label("Hasta", exact=True).nth(1)

    # 8. Rellenar campos de fecha
    await selector_fecha_desde.wait_for(timeout=10000)
    await selector_fecha_desde.fill(fecha_desde)
    print(f"Fecha Desde (Emisión) establecida a: {fecha_desde}")
    
    await selector_fecha_hasta.fill(fecha_hasta)
    print(f"Fecha Hasta (Emisión) establecida a: {fecha_hasta}")

    # --- AJUSTAR LÍMITE DE RESULTADOS ---
    print("\nAjustando límite de resultados...")
    # 9. Ajustar el valor del slider al valor de la constante
    slider_input = page.get_by_label("Limite")
    
    await slider_input.wait_for(timeout=10000) 
    
    # Aplicamos el valor de la constante TABLE_LIMIT
    await slider_input.fill(str(TABLE_LIMIT)) 
    # Esperamos a que el valor en el span adyacente se actualice para confirmar la acción del slider
    await page.wait_for_selector(f'span.slds-slider__value:has-text("{TABLE_LIMIT}")', timeout=5000)
    
    print(f"Límite de resultados establecido a {TABLE_LIMIT}.")
    
    # --- CLIC EN BOTÓN BUSCAR ---
    
    # 10. Pulsar el botón de 'Buscar'
    buscar_button_selector = 'button.slds-button_brand:has-text("Buscar")'
    
    await page.wait_for_selector(buscar_button_selector, timeout=10000)
    await page.click(buscar_button_selector)
    print("Click en el botón 'Buscar'.")
    
    # 11. Esperar a que la búsqueda se aplique y cargue el listado (listado de facturas)
    # Esperamos el contenedor general de la tabla
    tabla_selector = 'div.style-table.contenedorGeneral table#example1'
    await page.wait_for_selector(tabla_selector, timeout=60000)
    
    print("--- FILTRADO COMPLETADO. LISTO PARA LA LECTURA DE DATOS ---")


async def ejecutar_robot() -> list:
    """
    Función principal que orquesta el robot completo: login, búsqueda y lectura de datos.
    Retorna la lista de FacturaEndesaCliente con la metadata extraída.
    """
    robot = NavegadorAsync()
    facturas_extraidas = []
    login_successful = False
    
    try:
        # 1. Bucle de Reintentos de Login
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            print(f"\n[Intento {attempt}/{MAX_LOGIN_ATTEMPTS}] Iniciando sesión...")
            
            # Navegar a la página de login (o recargar si no es el primer intento)
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
                raise Exception(f"Fallo crítico: No se pudo iniciar sesión después de {MAX_LOGIN_ATTEMPTS} intentos.")

        # Si salimos del bucle con éxito:
        if not login_successful:
            raise Exception("Fallo crítico: El robot terminó el bucle de intentos de login sin éxito.")
            
        page = robot.get_page()

        # 2. Manejo de Cookies
        await _aceptar_cookies(page)
        
        # 3. Navegación y Búsqueda (Implementa el filtrado por CUPS aquí)
        await realizar_busqueda_facturas(page, GRUPO_EMPRESARIAL, TEST_CUPS, FECHA_DESDE, FECHA_HASTA)
        
        # 4. Extracción de datos de la tabla (Paginación incluida)
        facturas_metadata = await leer_tabla_facturas(page) 
        facturas_extraidas = facturas_metadata

        # 5. Log y Resumen (Corrección del Output)
        
        # 5.1. Exportar a CSV (Log)
        if facturas_metadata:
            log_filepath_dynamic = LOG_FILE_NAME_TEMPLATE.format(cups=TEST_CUPS)
            _exportar_log_csv(facturas_metadata, log_filepath_dynamic)
            
        # 5.2. Imprimir resumen detallado en consola
        if facturas_extraidas:
            print("\n========================================================")
            print(f"RESUMEN FINAL DE {len(facturas_extraidas)} FACTURAS LEÍDAS DE LA TABLA:")
            print("========================================================")
            
            # Campos que queremos mostrar en el resumen de la consola
            campos_a_mostrar = [
                'numero_factura', 'cups', 'fecha_emision', 
                'importe_total_tabla', 'contrato', 'descarga_selector'
            ]

            for f in facturas_extraidas:
                status = "METADATA OK" 
                print(f"--- Factura: {f.numero_factura} (Estado: {status}) ---")
                
                # Iterar sobre los atributos de la dataclass y solo mostrar los de la tabla
                for field in ['numero_factura', 'cups', 'fecha_emision', 'fecha_inicio_periodo', 'fecha_fin_periodo', 'importe_total_tabla', 'contrato', 'descarga_selector']:
                    value = getattr(f, field)
                    if value is not None and value != "" and value != 0.0:
                        print(f"| {field.replace('_', ' ').title().ljust(20)}: {value}")
                print("-" * 30)
            
            print("========================================================\n")
        
        return facturas_extraidas

    except Exception as e:
        print(f"Ocurrió un error crítico en la orquestación del robot: {e}")
        return []
    finally:
        if hasattr(robot, 'browser') and robot.browser:
            input("\nPresiona Enter para cerrar la sesión del navegador...")
            await robot.cerrar()
            print("\nSesión de navegador cerrada.")
        else:
             print("\nEl navegador ya está cerrado.")


# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
if __name__ == "__main__":
    print("--- INICIO DE PRUEBA MANUAL DEL ROBOT ENDESA (ORQUESTACIÓN) ---")
    
    try:
        # Ejecutamos la función principal asíncrona
        facturas = asyncio.run(ejecutar_robot())
        
        # Se asume que si la lista no está vacía, la extracción fue un éxito
        if facturas:
            print(f"\nRESULTADO FINAL: ✅ {len(facturas)} facturas preparadas para n8n.")
        else:
            print("\nRESULTADO FINAL: ❌ No se encontraron facturas para el filtro actual.")

    except KeyboardInterrupt:
        print("\nEjecución manual interrumpida por el usuario.")
    print("--- FIN DE PRUEBA MANUAL ---")
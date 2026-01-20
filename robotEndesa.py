from navegador import NavegadorAsync, TEMP_DOWNLOAD_ROOT # Importamos la clase base y la ruta de descarga
import asyncio
import re
import csv # Necesario para exportar los logs
import base64 # Necesario para la codificación Base64
import os # Necesario para manejar rutas de archivos
from playwright.async_api import Page, TimeoutError, Locator # Importamos Page, TimeoutError, Locator
from modelos_datos import FacturaEndesaDistribucion # Importamos la clase modelo de datos (AHORA ES PYDANTIC)
# IMPORTACIÓN DE LA FUNCIÓN DE LOGGING
from logs import escribir_log
from pdf_parser import procesar_pdf_local

# --- CONSTANTES DE E-DISTRIBUCIÓN ---
URL_LOGIN = "https://zonaprivada.edistribucion.com/areaprivada/s/login/?language=es"
URL_FACTURAS = "https://zonaprivada.edistribucion.com/areaprivada/s/wp-billingchecking"

# Credenciales REALES (Prioriza variables de entorno si existen)
USER = os.environ.get("DISTRIBUCION_USER", "27298340P") 
PASSWORD = os.environ.get("DISTRIBUCION_PASSWORD", "z5!tWZWzTDQ6rx9")

MAX_LOGIN_ATTEMPTS = 5 # NÚMERO MÁXIMO DE INTENTOS DE LOGIN

# --- CONSTANTE DE LOGGING Y CARPETAS DE DESCARGA ---
LOG_FILE_NAME_TEMPLATE = "csv/facturas_edistribucion_log.csv"

# Definición de las subcarpetas usando la constante TEMP_DOWNLOAD_ROOT de navegador.py
DOWNLOAD_FOLDERS = {
    'PDF': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Edistribucion_PDFs')
}
# Aseguramos que la carpeta exista
for folder in DOWNLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

escribir_log(f"[INFO] Carpetas de descarga configuradas en: {TEMP_DOWNLOAD_ROOT}")


# --- FUNCIONES DE UTILIDAD PARA EXTRACCIÓN Y LOGGING ---

def _clean_and_convert_float(text: str) -> float:
    """
    Limpia importes complejos como '-631.04€ / 0€'.
    1. Toma la parte antes de la barra.
    2. Captura el signo negativo y los números.
    3. Maneja correctamente los separadores decimales.
    """
    try:
        # 1. Nos quedamos solo con la parte antes de la barra '/' si existe
        parte_interesante = text.split('/')[0].strip()

        # 2. Regex que busca el signo negativo opcional y la cifra
        # Buscamos: signo opcional, dígitos, y opcionalmente (punto o coma seguido de más dígitos)
        match = re.search(r'(-?[\d\.,]+)', parte_interesante)
        
        if not match:
            return 0.0

        val_str = match.group(1)

        # 3. Lógica de limpieza de formato europeo/americano:
        # Si hay puntos y comas (ej: 1.250,50), quitamos el punto y cambiamos coma por punto.
        if ',' in val_str and '.' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        # Si solo hay coma (ej: 631,04), la cambiamos por punto.
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
        
        # 4. En el caso de tu HTML '-631.04€', el punto ya es el decimal.
        # No debemos hacer .replace('.', '') si es el único separador.
        
        return float(val_str)
    except Exception as e:
        escribir_log(f"Error al convertir importe '{text}': {e}")
        return 0.0

def _exportar_log_csv(facturas: list[FacturaEndesaDistribucion], filepath: str):
    """
    Exporta TODA la metadata de las facturas extraídas a un archivo CSV.
    """
    if not facturas: return
    fieldnames = list(FacturaEndesaDistribucion.model_fields.keys())
    
    try:
        escribir_log(f"[CSV]")
        file_exists = os.path.isfile(filepath)
        # Usamos 'a' (append) para ir acumulando las facturas de todos los roles en el mismo fichero
        with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            if not file_exists:
                writer.writeheader()
            for f in facturas:
                writer.writerow(f.model_dump())
        escribir_log(f"    -> [OK] Log CSV exportado a: {filepath}")
    except Exception as e:
        escribir_log(f"    -> [ERROR CSV] Fallo al exportar CSV: {e}")


# --- LÓGICA DE DESCARGA LOCAL Y EXTRACCIÓN ---

async def _descargar_archivo_fila(page: Page, row_locator: Locator, factura: FacturaEndesaDistribucion) -> str | None:
    """
    Intenta descargar el archivo PDF haciendo clic en el botón de la fila.
    """
    # En Edistribución el botón se identifica por name="PDF"
    button_locator = row_locator.locator('button[name="PDF"]')
    
    if await button_locator.count() == 0:
        return None

    try:
        target_folder = DOWNLOAD_FOLDERS['PDF']
        filename = f"{factura.cups}_{factura.numero_factura}.pdf"
        save_path = os.path.join(target_folder, filename)
        
        async with page.expect_download(timeout=5000) as download_info:
            await button_locator.click(timeout=5000)
            
        download = await download_info.value
        await download.save_as(save_path)
        
        escribir_log(f"    -> [OK] [DESCARGA PDF] Guardado en: {save_path}")
        return save_path
    
    except TimeoutError:
        raise Exception("TIMEOUT: El botón PDF no respondió o no es visible.")
        
    except Exception as e:
        escribir_log(f"   -> [ERROR PDF] Fallo inesperado en la descarga")
        error_limpio = str(e).split('\n')[0]
        raise Exception(f"FALLO_DESCARGA: {error_limpio}")

async def _extraer_pagina_actual(page: Page) -> list[FacturaEndesaDistribucion]:
    """
    Extrae los datos de todas las filas visibles en la tabla y descarga el PDF.
    """
    facturas_pagina: list[FacturaEndesaDistribucion] = []
    # Selector de filas basado en la tabla de Salesforce
    rows = page.locator('table[lwc-392cvb27u8q] tbody tr')
    row_count = await rows.count()

    if row_count == 0:
        return facturas_pagina
    
    for i in range(row_count):
        escribir_log(f"{'='*40} [ROW {i+1}]", mostrar_tiempo=False)
        row = rows.nth(i)

        # Inicializamos la factura con valores por defecto
        factura = FacturaEndesaDistribucion(
            cups="PENDIENTE", 
            error_RPA=False,
            secuencial=str(i))

        try:
            # Extracción de datos de la fila
            cups_val = (await row.locator('th[data-label="CUPS"]').inner_text()).strip()
            f_fiscal = (await row.locator('td[data-label="FACTURA FISCAL"]').inner_text()).strip()
            fecha_em = (await row.locator('td[data-label="FECHA"]').inner_text()).strip()
            imp_raw = await row.locator('td[data-label="TOTAL/PDTE"]').inner_text()
            est = (await row.locator('td[data-label="Estado"]').inner_text()).strip()
            tipo_f = (await row.locator('td[data-label="Tipo"]').inner_text()).strip()

            # Asignamos los datos extraídos al objeto factura 
            factura.cups = cups_val
            factura.numero_factura = f_fiscal
            factura.fecha_emision = fecha_em
            factura.importe_total_tabla = _clean_and_convert_float(imp_raw)
            factura.estado_factura = est
            factura.tipo_factura = tipo_f
            factura.descarga_selector = f_fiscal

            escribir_log(f"    [OK] Datos extraídos: Factura {factura.numero_factura} ({factura.cups})")

            # Validación de Importe Negativo (Requisito de negocio)
            if factura.importe_total_tabla < 0:
                factura.error_RPA = True
                factura.direccion_suministro = "NOTIFICACIÓN: Factura rectificativa o importe negativo."
                escribir_log("    [!] Importe negativo detectado.")
            
            # Proceso de Descarga de PDF (Solo si no hay error previo)
            escribir_log(f"[FILES]")
            try:
                ruta_pdf = await _descargar_archivo_fila(page, row, factura)
                if not ruta_pdf:
                    raise Exception("NO_DISPONIBLE: No existe botón PDF.")
                # === INTEGRACION OCR ===
                if not factura.error_RPA and factura.importe_total_tabla >= 0:
                    escribir_log(f"    -> [OCR]")
                    exito_ocr = procesar_pdf_local(factura, ruta_pdf)
                    if exito_ocr:
                        escribir_log(f"        -> [OK] OCR completado para {factura.numero_factura}")
                    else:
                        escribir_log(f"        -> [!] [OCR] No se pudieron extraer datos adicionales.")

            except Exception as e_pdf:
                factura.error_RPA = True
                # Concatenamos el error del PDF al mensaje existente (si lo hay)
                msg_error = str(e_pdf).split("Call log:")[0].strip()
                
                # Concatenamos de forma limpia
                prefijo = (factura.direccion_suministro + " | ") if factura.direccion_suministro else ""
                factura.direccion_suministro = f"{prefijo}ERROR_PDF: {msg_error}"
                
                escribir_log(f"    -> [!] {msg_error}", mostrar_tiempo=False)
        

        except Exception as e_critico:
            # Este bloque captura errores si falla la lectura de la propia tabla (selectores)
            factura.error_RPA = True
            factura.direccion_suministro = f"ERROR_ESTRUCTURA_TABLA: {str(e_critico)}"
            escribir_log(f"    [CRÍTICO] Fallo estructural en fila {i+1}: {e_critico}")
        
        facturas_pagina.append(factura)

    return facturas_pagina


# --- FUNCIONES AUXILIARES DE FLUJO ---

async def _iniciar_sesion(page: Page, username: str, password: str) -> bool:
    try:
        await page.wait_for_selector('input[name="username"]', timeout=20000)
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        await page.click('button:has-text("ENTRAR")')
        await page.wait_for_load_state("networkidle")
        return True
    except Exception as e:
        escribir_log(f"Error en la autenticación: {e}")
        return False

async def obtener_todos_los_roles(page: Page) -> list[str]:
    """Extrae los nombres de todos los roles del desplegable filtrando valores nulos."""
    escribir_log("Obteniendo lista de roles disponibles...")
    await page.locator('button[title="Cambio de rol"]').click()
    # Esperamos a que los elementos del menú sean visibles
    await page.wait_for_selector('a[role="menuitem"]', timeout=15000)
    
    roles_elements = page.locator('a[role="menuitem"]')
    count = await roles_elements.count()
    roles = []
    
    for i in range(count):
        # Obtenemos el atributo title
        nombre = await roles_elements.nth(i).get_attribute("title")
        
        # CORRECCIÓN: Solo añadimos a la lista si el nombre existe y no es una cadena vacía o "None"
        if nombre and str(nombre).strip().lower() != "none" and str(nombre).strip() != "":
            roles.append(nombre.strip())
            escribir_log(f"   - Empresa detectada: {nombre.strip()}", mostrar_tiempo=False)
    
    # Cerramos el menú volviendo a pulsar el botón para que no bloquee la pantalla
    await page.locator('button[title="Cambio de rol"]').click()
    
    escribir_log(f"Total de empresas válidas a procesar: {len(roles)}")
    return roles

async def seleccionar_rol_especifico(page: Page, nombre_rol: str):

    await page.locator('button[title="Cambio de rol"]').click()
    opcion = page.locator(f'a[role="menuitem"][title="{nombre_rol}"]')
    await opcion.wait_for(state="visible")
    
    clases = await opcion.get_attribute("class")
    if "wp-roleSelected" in (clases or ""):
        await page.locator('button[title="Cambio de rol"]').click()
    else:
        await opcion.click()
        await page.wait_for_load_state("networkidle")

async def aplicar_filtros_fechas(page: Page, f_desde, f_hasta):
    await page.goto(URL_FACTURAS, wait_until="networkidle")
    
    # Activar radio de rango
    await page.locator('span.slds-form-element__label:has-text("Rango de fechas")').click()
    await page.wait_for_timeout(1000)
    
    await page.fill('.filter-date-from input', "")
    await page.type('.filter-date-from input', f_desde, delay=60)
    await page.fill('.filter-date-to input', "")
    await page.type('.filter-date-to input', f_hasta, delay=60)
    
    await page.locator('button:has-text("Aplicar")').last.click()
    escribir_log("Filtros Aplicados. Esperando carga de tabla (Máx 60s)...")

    for i in range(30):
        if await page.locator('lightning-primitive-cell-factory').first.is_visible():
            escribir_log("    [OK] Tabla cargada con éxito.")
            return True
        if await page.is_visible('div:has-text("No se encuentran resultados")'):
            escribir_log("    [INFO] Sin resultados para este periodo.")
            return False
        await asyncio.sleep(2)
    return False


# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL PARA LA API ---
# --------------------------------------------------------------------------------

async def ejecutar_robot_api(fecha_desde: str, fecha_hasta: str) -> list[FacturaEndesaDistribucion]:
    robot = NavegadorAsync()
    todas_las_facturas = []
    login_successful = False
    
    try:
        escribir_log(f"    [INICIO] Proceso RPA Edistribución. Desde={fecha_desde}, Hasta={fecha_hasta}", pretexto="\n")
        escribir_log(f"{'='*40} ", mostrar_tiempo=False)
        
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...", pretexto="\n\t")
            await robot.iniciar()
            await robot.goto_url(URL_LOGIN)
            
            login_successful = await _iniciar_sesion(robot.get_page(), USER, PASSWORD)
            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                break
            
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            await robot.cerrar()

            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")

        page = robot.get_page()
        roles = await obtener_todos_los_roles(page)

        for rol in roles:
            escribir_log(f"{'='*40}", pretexto="\n", mostrar_tiempo=False)
            escribir_log(f"PROCESANDO EMPRESA: {rol}")
            escribir_log(f"{'='*80}", mostrar_tiempo=False)
            
            try:
                await seleccionar_rol_especifico(page, rol)
                
                escribir_log(f"[BUSQUEDA]")
                hay_datos = await aplicar_filtros_fechas(page, fecha_desde, fecha_hasta)
                
                if hay_datos:
                    escribir_log(f"[EXTRACCIÓN]")
                    facturas_rol = await _extraer_pagina_actual(page)
                    todas_las_facturas.extend(facturas_rol)
                    # Guardamos el CSV acumulado
                    _exportar_log_csv(facturas_rol, LOG_FILE_NAME_TEMPLATE)
                    escribir_log(f"{'='*80}", mostrar_tiempo=False)
                    escribir_log(f"[OK] {len(facturas_rol)} facturas procesadas para {rol}.")
                
            except Exception as e:
                escribir_log(f"[ERROR] Fallo en ROL {rol}: {e}")
                continue

        escribir_log(f"[OK][FIN] Proceso completado. Total facturas: {len(todas_las_facturas)}")
        return todas_las_facturas

    finally:
        await robot.cerrar()
        escribir_log("[SISTEMA] Navegador cerrado.\n")

def obtener_pdf_local_base64(cups: str, numero_factura: str) -> dict:
    """Lee el PDF descargado y lo devuelve en Base64."""
    target_folder = DOWNLOAD_FOLDERS['PDF']
    filename = f"{cups}_{numero_factura}.pdf"
    file_path = os.path.join(target_folder, filename)
    
    respuesta = {"filename": filename, "cups": cups, "numero_factura": numero_factura, "pdf_base64": ""}

    try:
        if not os.path.exists(file_path):
            escribir_log(f"⚠️ PDF no encontrado: {filename}")
            respuesta["pdf_base64"] = "ERROR: ARCHIVO_NO_ENCONTRADO"
            return respuesta

        with open(file_path, 'rb') as f:
            respuesta["pdf_base64"] = base64.b64encode(f.read()).decode('utf-8')
        
        escribir_log(f"✅ PDF '{filename}' codificado con éxito.")
        return respuesta
    except Exception as e:
        respuesta["pdf_base64"] = f"ERROR: {str(e)}"
        return respuesta
    

# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
if __name__ == "__main__":
    import sys
    escribir_log("\n" + "!"*60, mostrar_tiempo=False)
    escribir_log("ADVERTENCIA: robotEndesa.py se está ejecutando de forma directa.", mostrar_tiempo=False)
    escribir_log("Este script está diseñado para ser invocado desde la API (FastAPI).", mostrar_tiempo=False)
    escribir_log("Para realizar pruebas, inicie la API y use Swagger (/docs).", mostrar_tiempo=False)
    escribir_log("!"*60 + "\n", mostrar_tiempo=False)
    
    # Opcional: Podrías descomentar esto para una prueba rápida de 1 solo rol sin API
    # asyncio.run(ejecutar_robot_api("01/10/2025", "31/10/2025"))
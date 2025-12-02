from navegador import NavegadorAsync # Importamos la clase base del navegador
import asyncio
from playwright.async_api import Page, TimeoutError # Importamos Page para tipado y TimeoutError para manejo de errores

# --- CONSTANTES DE ENDESA ---
URL_LOGIN = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 
URL_BUSQUEDA_FACTURAS = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"

# Credenciales REALES proporcionadas por el usuario
USER = "pfombellav@somosgrupomas.com" 
PASSWORD = "Guillena2024*" 
GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN" # Constante para el texto de búsqueda

# Selector que aparece SÓLO después de un login exitoso (El botón de cookies)
SUCCESS_INDICATOR_SELECTOR = '#truste-consent-button' 


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
        await page.wait_for_selector(SUCCESS_INDICATOR_SELECTOR, timeout=30000)
        
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


async def realizar_busqueda_facturas(page: Page, grupo_empresarial: str):
    """
    Navega al asistente de búsqueda y aplica el filtro del grupo empresarial.
    """
    print(f"\n--- INICIO DE BÚSQUEDA DE FACTURAS para {grupo_empresarial} ---")
    
    # 1. Navegar a la página de búsqueda (CORRECCIÓN: Se relaja la espera a domcontentloaded)
    await page.goto(URL_BUSQUEDA_FACTURAS, wait_until="domcontentloaded")
    print("Navegación al asistente de búsqueda completada.")

    # NUEVA ESPERA: Asegurar que el contenedor principal de filtros ha cargado
    main_filter_container_selector = 'div.filter-padd-container'
    await page.wait_for_selector(main_filter_container_selector, timeout=20000)
    print("Contenedor de filtros detectado. Iniciando interacción...")

    # 2. Pulsar en el botón 'Grupo empresarial' para abrir el desplegable
    # Usamos el atributo 'name' en la clase slds-button para ser robustos
    grupo_empresarial_button = 'button[name="periodo"]:has-text("Grupo empresarial")'
    await page.wait_for_selector(grupo_empresarial_button, timeout=15000)
    await page.click(grupo_empresarial_button)
    print("Click en el botón 'Grupo empresarial'.")

    # 3. Rellenar el campo de búsqueda con el texto
    # El input tiene un placeholder 'Buscar'
    input_selector = 'input[placeholder="Buscar"]'
    await page.wait_for_selector(input_selector, timeout=10000)
    await page.fill(input_selector, grupo_empresarial)
    print(f"Texto introducido: '{grupo_empresarial}'.")

    # 4. Seleccionar la opción de la lista desplegable
    # La opción aparece en un <li> y el span contiene el texto exacto.
    opcion_selector = f'span[role="option"] >> text="{grupo_empresarial}"'
    
    # Esperamos un breve tiempo a que la lista se filtre (500ms es una estimación)
    await page.wait_for_timeout(500) 

    # Esperamos y hacemos clic en la opción que contiene el nombre del grupo
    await page.wait_for_selector(opcion_selector, timeout=10000)
    await page.click(opcion_selector)
    print(f"Seleccionado '{grupo_empresarial}' en el desplegable.")
    
    # 5. Esperar a que la búsqueda se aplique y cargue el listado (listado de facturas)
    # Pendiente de Tarea 2: Selector del Listado de Facturas
    print("Filtro aplicado. Esperando la carga del listado de facturas...")
    # await page.wait_for_selector("AQUÍ_VA_EL_SELECTOR_DEL_LISTADO", timeout=20000)
    
    print("--- BÚSQUEDA DE FACTURAS FINALIZADA. LISTO PARA DESCARGA ---")


async def ejecutar_robot():
    """
    Función principal que orquesta el robot completo: login, búsqueda y descarga.
    """
    robot = NavegadorAsync()
    facturas_descargadas = []
    
    try:
        await robot.iniciar()
        page = robot.get_page()

        # 1. Login
        await robot.goto_url(URL_LOGIN)
        login_successful = await _iniciar_sesion(page, USER, PASSWORD)
        
        if not login_successful:
            return [] # Termina si el login falla

        # 2. Manejo de Cookies (Aparece inmediatamente después del login)
        await _aceptar_cookies(page)
        
        # 3. Navegación y Búsqueda (Filtro por Grupo Empresarial)
        await realizar_busqueda_facturas(page, GRUPO_EMPRESARIAL)
        
        # 4. Descarga de Facturas (Lógica de Tarea 3 pendiente de selectores)
        # facturas_descargadas = await descargar_facturas(page) 
        
        return facturas_descargadas

    except Exception as e:
        print(f"Ocurrió un error crítico en la orquestación del robot: {e}")
        return []
    finally:
        # 5. Cierre
        input("\nPresiona Enter para cerrar la sesión del navegador...")
        await robot.cerrar()
        print("\nSesión de navegador cerrada.")


# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
if __name__ == "__main__":
    print("--- INICIO DE PRUEBA MANUAL DEL ROBOT ENDESA (ORQUESTACIÓN) ---")
    
    try:
        # Ejecutamos la función principal asíncrona
        facturas = asyncio.run(ejecutar_robot())
        
        if facturas:
            print(f"\nRESULTADO FINAL: ✅ {len(facturas)} facturas preparadas para n8n.")
        else:
            print("\nRESULTADO FINAL: ❌ No se descargaron facturas.")

    except KeyboardInterrupt:
        print("\nEjecución manual interrumpida por el usuario.")
    print("--- FIN DE PRUEBA MANUAL ---")
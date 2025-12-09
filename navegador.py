from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext # Importamos las clases para mejor tipado
import asyncio # Necesario para ejecutar funciones asíncronas
import os # Necesario para gestionar directorios

# Directorio raíz donde Playwright guardará temporalmente los archivos.
TEMP_DOWNLOAD_ROOT = "temp_endesa_downloads" 

class NavegadorAsync:
    """
    Clase que encapsula la inicialización, uso y cierre de una sesión 
    de Playwright Asíncrona.
    """
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        
        # Aseguramos que el directorio exista
        os.makedirs(TEMP_DOWNLOAD_ROOT, exist_ok=True)

    async def iniciar(self):
        """Inicializa la sesión de Playwright y lanza el navegador."""
        self.playwright = await async_playwright().start()
        
        # En preproducción usamos headless=False (visual)
        self.browser = await self.playwright.chromium.launch(headless=False) 
        
        # Creamos un nuevo contexto de navegador CON el directorio de descarga configurado
        self.context = await self.browser.new_context(
            accept_downloads=True, # Permitimos descargas
            # Nota: Playwright usará su propia ubicación temporal, pero al usar save_as, 
            # podemos definir la ruta absoluta localmente.
        )
        self.page = await self.context.new_page()
        
        return self 

    async def goto_url(self, url: str, timeout_ms: int = 60000) -> Page:
        """
        Navega a la URL especificada. 
        Retorna el objeto Page para interactuar.
        """
        await self.page.goto(
            url, 
            wait_until="domcontentloaded", 
            timeout=timeout_ms
        ) 
        return self.page

    async def cerrar(self):
        """Cierra el navegador y detiene el contexto de Playwright de forma segura."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    # Función para obtener la página activa, útil para el robot
    def get_page(self) -> Page:
        """Devuelve el objeto Page actual para su uso por el robot."""
        if not self.page:
            raise RuntimeError("El navegador no ha sido inicializado. Ejecute 'iniciar()' primero.")
        return self.page
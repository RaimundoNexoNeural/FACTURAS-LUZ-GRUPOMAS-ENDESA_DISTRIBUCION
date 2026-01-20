# FACTURAS-LUZ-GRUPOMAS

## Descripción del Proyecto

El proyecto **FACTURAS-LUZ-GRUPOMAS** automatiza la búsqueda, descarga, procesamiento y análisis de facturas eléctricas desde el portal Endesa Distribución (e-distribución). Utiliza tecnologías como **Playwright**, **FastAPI**, **Pydantic** y modelos de lenguaje de OpenAI (**GPT-4o**).

---

## Estructura del Proyecto

```plaintext
DESCARGA FACTURAS MAS/
├── api.py                # API REST con FastAPI
├── robotEndesa.py        # Lógica RPA y flujo de navegación
├── pdf_parser.py         # Procesamiento de PDFs con IA
├── modelos_datos.py      # Modelos de datos con Pydantic
├── navegador.py          # Manejo de sesiones Playwright
├── logs.py               # Registro de eventos
├── prompt_distribucion.txt # Instrucciones para el modelo IA
├── setup_and_run.sh      # Script de configuración y ejecución
├── requirements.txt      # Dependencias del proyecto
├── .env                  # Variables de entorno
├── .gitignore            # Exclusión de archivos sensibles
├── csv/                  # Registros de facturas en CSV
├── logs/                 # Carpeta de logs
└── temp_endesa_downloads/ # Descargas temporales
```

---

## Funcionalidades Principales

### 1. Automatización del Navegador (RPA)
- **Acceso Seguro**: Login automático con credenciales seguras.
- **Navegación Eficiente**: Gestión asíncrona con `NavegadorAsync`.
- **Modo Invisible (Headless)**: Operación sin interfaz gráfica.
- **Descarga Masiva**: Obtención de facturas en múltiples formatos.

### 2. Procesamiento Inteligente de Datos
- **Extracción con IA**: Uso de GPT-4o para extraer datos técnicos (CUPS, potencias, consumos, impuestos).
- **Validación de Esquema**: Garantía de integridad con modelos estrictos.
- **Cálculos Automáticos**: Procesamiento de fechas y sumatorios.

### 3. API REST
- **GET /facturas**: Extrae facturas en un rango de fechas.
- **GET /pdf-local/{cups}/{numero_factura}**: Acceso al contenido del PDF en Base64.
- **GET /clear_files**: Limpieza de descargas temporales y logs.

### 4. Gestión de Logs y Reportes
- **Trazabilidad**: Registro detallado en `logs/log.txt`.
- **Reportes CSV**: Generación de logs tabulares para análisis.

---

## Requisitos y Configuración

### Requisitos Técnicos
- **Python**: 3.9 o superior.
- **Playwright**: Binarios de navegador instalados.
- **OpenAI API Key**: Acceso a modelos GPT-4o.

### Instalación

1. **Clonación del repositorio**:
    ```bash
    git clone https://github.com/RaimundoNexoNeural/FACTURAS-LUZ-GRUPOMAS.git
    cd FACTURAS-LUZ-GRUPOMAS
    ```

2. **Configuración del entorno (.env)**:
    ```plaintext
    ENDESA_DISTRIBUCION_USER=tu_usuario
    ENDESA_DISTRIBUCION_PASSWORD=tu_password
    OPENAI_API_KEY=tu_api_key_de_openai
    ```

3. **Ejecución del Setup**:
    ```bash
    chmod +x setup_and_run.sh
    ./setup_and_run.sh
    ```

---

## Uso de la API

Una vez en ejecución, accede a la documentación interactiva:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Ejemplo de comando para extraer facturas:
```bash
curl -X 'GET' 'http://localhost:8000/facturas?fecha_desde=01/01/2025&fecha_hasta=31/01/2025'
```

---

## Notas de Desarrollo

- El archivo `.env` es obligatorio y no debe subirse al repositorio público.
- El directorio `temp_endesa_downloads` se autogestiona; no requiere configuración manual.
- Mantén las dependencias actualizadas para evitar problemas de compatibilidad.
- Revisa los logs periódicamente para garantizar el correcto funcionamiento.


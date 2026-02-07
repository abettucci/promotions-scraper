"""
Configuración del scraper de promociones
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Directorios
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Base de datos
DATABASE_PATH = DATA_DIR / "promotions.db"

# Configuración de scraping
MIN_DELAY = 2  # segundos entre requests
MAX_DELAY = 5  # segundos entre requests
PAGE_TIMEOUT = 30000  # milisegundos
SCROLL_DELAY = 1  # segundos después de scroll

# Configuración de browser
HEADLESS = True  # Cambia a False para ver el browser
VIEWPORT = {'width': 1920, 'height': 1080}

# User Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# Proxies (opcional - descomenta y configura si necesitas)
USE_PROXIES = False
PROXIES = [
    # 'http://user:pass@proxy1.example.com:8000',
    # 'http://user:pass@proxy2.example.com:8000',
]

# Geolocalización (Buenos Aires)
GEOLOCATION = {
    'latitude': -34.6037,
    'longitude': -58.3816
}

# Supermercados
# Nota: Los scrapers standalone (dia, coto, masonline, cencosud) usan sus propias URLs internas
SUPERMARKETS = {
    'carrefour': {
        'name': 'Carrefour',
        'url': 'https://www.carrefour.com.ar/descuentos-bancarios',
        'enabled': True
    },
    'dia': {
        'name': 'Supermercados Día',
        'url': 'https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones',
        'enabled': True
    },
    'coto': {
        'name': 'Coto Digital',
        'url': 'https://www.cotodigital.com.ar/sitios/cdigi/terminos-descuentos',
        'enabled': True
    },
    'cencosud': {
        'name': 'Jumbo (Cencosud)',
        'url': 'https://www.jumbo.com.ar/descuentos-del-dia',
        'enabled': True
    },
    'masonline': {
        'name': 'Más Online (ChangoMás)',
        'url': 'https://www.masonline.com.ar/promociones-bancarias',
        'enabled': True
    },
    # Deshabilitados por ahora (sin scraper específico)
    # 'disco': {
    #     'name': 'Disco',
    #     'url': 'https://www.disco.com.ar/promociones-bancarias',
    #     'enabled': False
    # },
    # 'vea': {
    #     'name': 'Vea',
    #     'url': 'https://www.vea.com.ar/promociones-bancarias',
    #     'enabled': False
    # },
}

# Palabras clave para detectar bancos y billeteras
BANKS_KEYWORDS = [
    'galicia', 'santander', 'bbva', 'macro', 'icbc', 'hsbc',
    'ciudad', 'nacion', 'patagonia', 'credicoop', 'supervielle',
    'frances', 'itau', 'comafi', 'piano', 'bind'
]

WALLETS_KEYWORDS = [
    'mercado pago', 'ualá', 'naranja x', 'modo', 'personal pay',
    'cuenta dni', 'claro pay', 'tap', 'bimo', 'prex'
]

# Palabras clave para detectar requisitos/exclusiones en T&C
EXCLUSION_KEYWORDS = [
    'excepto', 'excluye', 'no incluye', 'no aplica', 'no válido',
    'excluyendo', 'sin incluir', 'a excepción'
]

REQUIREMENT_KEYWORDS = [
    'nivel', 'paquete', 'sueldo', 'black', 'platinum', 'signature',
    'requisito', 'mínimo', 'necesario', 'debe', 'solo para'
]

# Configuración de logs
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Intentos de retry
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos

# ============================================
# CONFIGURACIÓN DE IA (Claude Vision)
# ============================================
# API Key de Anthropic (requerida para modo --ai)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Modelo de Claude a usar para extracción
# Opciones: claude-sonnet-4-20250514, claude-3-5-sonnet-20241022, claude-3-haiku-20240307
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-20250514")

# Máximo de tokens en la respuesta
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))

# Número máximo de screenshots por página (para páginas largas)
AI_MAX_SCREENSHOTS = int(os.getenv("AI_MAX_SCREENSHOTS", "5"))


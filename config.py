"""
Configuración del scraper de promociones
"""
import os
from pathlib import Path

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
SUPERMARKETS = {
    'carrefour': {
        'name': 'Carrefour',
        'url': ' https://www.carrefour.com.ar/descuentos-bancarios', # https://www.carrefour.com.ar/promociones
        'enabled': True
    }
    # 'coto': {
    #     'name': 'Coto Digital',
    #     'url': 'https://www.coto.com.ar/descuentos/index.asp',
    #     'enabled': True
    # },
    # 'disco': {
    #     'name': 'Disco',
    #     'url': 'https://www.disco.com.ar/promociones-bancarias',
    #     'enabled': True
    # },
    # 'jumbo': {
    #     'name': 'Jumbo',
    #     'url': 'https://www.jumbo.com.ar/promociones',
    #     'enabled': True
    # },
    # 'dia': {
    #     'name': 'Día',
    #     'url': 'https://diaonline.supermercadosdia.com.ar/promociones',
    #     'enabled': True
    # },
    # 'walmart': {
    #     'name': 'Walmart',
    #     'url': 'https://www.walmart.com.ar/promociones',
    #     'enabled': True
    # },
    # 'changomas': {
    #     'name': 'Changomás',
    #     'url': 'https://www.changomas.com.ar/promociones',
    #     'enabled': True
    # }
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


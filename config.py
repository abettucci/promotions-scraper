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

# Base de datos de promociones (viene de git, se sobreescribe en cada deploy)
DATABASE_PATH = DATA_DIR / "promotions.db"

# Base de datos de usuarios (persistida en Railway Volume en /app/userdata)
_USERS_DB_DIR = Path(os.getenv("USERS_DB_DIR", str(BASE_DIR / "userdata")))
_USERS_DB_DIR.mkdir(exist_ok=True)
USERS_DB_PATH = _USERS_DB_DIR / "users.db"

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
    # ── Estaciones de servicio ──────────────────────────────────────────────
    'shell': {
        'name': 'Shell',
        'url': 'https://www.shell.com.ar/conductores/descuentos-vigentes.html',
        'enabled': True,
        'category': 'fuel',
    },
    'axion': {
        'name': 'Axion',
        'url': 'https://www.axionenergy.com/Paginas/beneficios/beneficiosypromociones.aspx',
        'enabled': True,
        'category': 'fuel',
    },
    'puma': {
        'name': 'Puma Energy',
        'url': 'https://pumaenergyarg.com.ar/promociones',
        'enabled': True,
        'category': 'fuel',
    },
    # Aggregators: scrapean páginas de bancos/billeteras y rutean cada promo
    # a la marca de gasolinera (YPF/Shell/Axion/Puma) extraída por la IA.
    # NO se insertan como supermarket — sus promos van bajo la marca correspondiente.
    'modo': {
        'name': 'MODO',
        'url': 'https://www.modo.com.ar/promos/combustibles',
        'enabled': True,
        'category': 'fuel',
        'aggregator': True,
    },
    'macro': {
        'name': 'Banco Macro',
        'url': 'https://www.macro.com.ar/selecta/combustible',
        'enabled': True,
        'category': 'fuel',
        'aggregator': True,
    },
    'galicia': {
        'name': 'Banco Galicia',
        'url': 'https://www.galicia.ar/personas/promociones/promocion-combustible',
        'enabled': True,
        'category': 'fuel',
        'aggregator': True,
    },
    'bna': {
        'name': 'Banco Nación',
        'url': 'https://www.bna.com.ar/Personas/DescuentosYPromociones/4486/ypf/',
        'enabled': True,
        'category': 'fuel',
        'aggregator': True,
        # BNA es solo YPF — si la IA no extrae la marca, asumir esto
        'default_brand': 'YPF',
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

# ============================================
# CONFIGURACIÓN DE TELEGRAM
# ============================================
# Token del bot (obtenelo hablando con @BotFather en Telegram)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ID del chat/grupo donde enviar las notificaciones
# Para obtenerlo: habla con @userinfobot en Telegram
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Si True, envía notificación automáticamente al finalizar el scraping
TELEGRAM_NOTIFY_ON_SCRAPE = os.getenv("TELEGRAM_NOTIFY_ON_SCRAPE", "false").lower() == "true"

# Si True, el digest diario incluye solo promos válidas para el día de hoy
TELEGRAM_TODAY_ONLY = os.getenv("TELEGRAM_TODAY_ONLY", "true").lower() == "true"

# Secret para validar webhook entrante (header X-Telegram-Bot-Api-Secret-Token).
# Si está vacío, no se valida — pero se recomienda setearlo en producción.
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

# URL pública del webhook (para scripts/setup_webhook.py). Ej: https://promoar.up.railway.app/webhook/telegram
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

# ============================================
# AUTENTICACIÓN JWT
# ============================================
JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esto-en-produccion-usa-openssl-rand-hex-32")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

# ============================================
# CATÁLOGO DE MEDIOS DE PAGO
# ============================================
PAYMENT_METHODS_CATALOG = {
    "bank": [
        "Banco Nación", "Banco Galicia", "Santander", "BBVA", "Macro",
        "ICBC", "HSBC", "Banco Ciudad", "Banco Patagonia", "Credicoop",
        "Supervielle", "Banco Francés", "Itaú", "Comafi", "Carrefour Banco",
    ],
    "wallet": [
        "Mercado Pago", "Ualá", "Naranja X", "MODO", "Personal Pay",
        "Cuenta DNI", "Claro Pay",
    ],
    "club": [
        "Club La Nación", "ANSES / Jubilados",
    ],
}


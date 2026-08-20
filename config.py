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
    # ── Billeteras / Beneficios bancarios ──────────────────────────────────
    'brubank': {
        'name': 'Brubank',
        'url': 'https://www.brubank.com/beneficios',
        'enabled': True,
        'category': 'benefits',
    },
    'personalpay': {
        'name': 'Personal Pay',
        'url': 'https://www.personal.com.ar/pay/beneficios',
        'enabled': True,
        'category': 'benefits',
    },
    'clublanacion': {
        'name': 'Club La Nación',
        'url': 'https://club.lanacion.com.ar/beneficios',
        'enabled': True,
        'category': 'benefits',
    },
    'buepp': {
        'name': 'Buepp',
        'url': 'https://www.buepp.com.ar/beneficios',
        'enabled': True,
        'category': 'benefits',
    },
    'cuentadni': {
        'name': 'Cuenta DNI',
        'url': 'https://www.bancoprovincia.com.ar/cuentadni/contenidos/cdniBeneficios/',
        'enabled': True,
        'category': 'benefits',
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
# CONFIGURACIÓN DE IA (Gemini o Claude Vision)
# Prioridad: GEMINI_API_KEY (gratis) → ANTHROPIC_API_KEY
# ============================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Modelo preferido; ai_extractor verifica disponibilidad y cae al mejor disponible
# si este ya no existe. Lista de prioridad: gemini-2.5-flash > gemini-2.0-flash > gemini-1.5-flash
# Claude fallback: claude-haiku-4-5-20251001
AI_MODEL = os.getenv("AI_MODEL", "gemini-1.5-flash")

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
# CONFIGURACIÓN DE EMAIL (Resend)
# ============================================
# API key desde resend.com → API Keys
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# Remitente verificado (debe matchear con dominio verificado en Resend)
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@promoar.app")

# URL base del frontend para construir links de reset (ej: https://promoar.app)
# El email arma <FRONTEND_BASE_URL>/reset-password?token=<token>
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

# Tiempo de expiración del token de reset (en segundos). Default 1 hora.
PASSWORD_RESET_EXPIRY = int(os.getenv("PASSWORD_RESET_EXPIRY", "3600"))

# Rate limit: máx pedidos de reset por user en 1 hora
PASSWORD_RESET_MAX_PER_HOUR = int(os.getenv("PASSWORD_RESET_MAX_PER_HOUR", "3"))

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
        "Banco Provincia",
    ],
    "wallet": [
        "Mercado Pago", "Ualá", "Naranja X", "MODO", "Personal Pay",
        "Cuenta DNI", "Claro Pay", "Brubank", "Buepp",
    ],
    "club": [
        # Beneficios sociales del Estado
        "ANSES / Jubilados",
        "PAMI",
        # Tarjetas especiales de supermercados / bancos
        "Tarjeta Soy Tigre",
        "Tarjeta Cencosud",
        "Tarjeta Carrefour",
        "Tarjeta Naranja",
        # Clubes de fidelización / medios
        "Club La Nación",
        "Club Personal",
        "Clarín 365",
        "Club Cencosud",
        # Socios de clubes deportivos
        "Socios River Plate",
        "Socios Boca Juniors",
        "Socios Racing",
        "Socios San Lorenzo",
        "Socios Independiente",
        "Socios Vélez",
        "Socios Huracán",
        "Socios Estudiantes LP",
        # Descuentos para estudiantes universitarios
        "Estudiantes Universitarios",
    ],
}

CLUBS_KEYWORDS = [
    'anses', 'jubilados', 'pami', 'soy tigre', 'cencosud', 'naranja',
    'club la nacion', 'club personal', 'clarin 365', 'club cencosud',
    'river plate', 'boca juniors', 'racing', 'san lorenzo', 'independiente',
    'velez', 'huracan', 'estudiantes universitarios',
]


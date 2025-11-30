# 🛒 Scraper de Promociones Bancarias - Supermercados Argentina

Sistema de scraping automático para extraer promociones bancarias de supermercados argentinos.

## 🎯 Características

- ✅ Scraping anti-detección con Playwright-Stealth
- ✅ Extracción de términos y condiciones
- ✅ Base de datos SQLite
- ✅ Dashboard web con Streamlit
- ✅ Ejecución programada automática
- ✅ 100% Gratis

## 🏪 Supermercados Soportados

- Carrefour
- Coto Digital
- Disco
- Jumbo
- Día
- Walmart
- Changomás

## 📦 Instalación

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar Chromium para Playwright
playwright install chromium

# 4. Configurar (opcional)
cp .env.example .env
# Editar .env si necesitas configurar algo
```

## 🚀 Uso

### Scraping Manual

```bash
# Scrapear todos los supermercados
python scraper.py

# Scrapear uno específico
python scraper.py --supermarket carrefour

# Modo verbose (ver más detalles)
python scraper.py --verbose
```

### Dashboard Web

```bash
streamlit run dashboard.py
```

Abre tu navegador en `http://localhost:8501`

### Automatización

#### Con Cron (Linux/Mac)

```bash
# Ejecutar todos los días a las 9 AM
crontab -e

# Agregar esta línea:
0 9 * * * cd /path/to/promo-scraper && /path/to/venv/bin/python scraper.py
```

#### Con Task Scheduler (Windows)

1. Abrir "Programador de tareas"
2. Crear tarea básica
3. Trigger: Diario a las 9:00 AM
4. Acción: Ejecutar `python.exe` con argumento `/path/to/scraper.py`

#### Con GitHub Actions (Gratis, en la nube)

El archivo `.github/workflows/scraper.yml` ya está configurado.

## 📊 Estructura de Base de Datos

```sql
supermarkets: id, name, url, last_scraped
promotions: id, supermarket_id, title, discount, bank, valid_from, valid_until
terms_conditions: id, promotion_id, raw_text, exclusions, requirements, max_discount
```

## 🔧 Configuración Avanzada

### Usar Proxies (Opcional)

Edita `config.py`:

```python
PROXIES = [
    'http://user:pass@proxy1.example.com:8000',
    'http://user:pass@proxy2.example.com:8000',
]
USE_PROXIES = True
```

### Ajustar Delays

En `config.py`:

```python
MIN_DELAY = 2  # segundos
MAX_DELAY = 5  # segundos
```

## 📁 Estructura del Proyecto

```
promo-scraper/
├── scraper.py              # Script principal
├── scrapers/               # Scrapers específicos
│   ├── carrefour.py
│   ├── coto.py
│   └── ...
├── database.py             # Gestión de BD
├── terms_parser.py         # Parser de T&C
├── dashboard.py            # Dashboard Streamlit
├── config.py               # Configuración
├── requirements.txt
└── data/
    └── promotions.db       # SQLite database
```

## 🐛 Troubleshooting

### Error: "Timeout waiting for selector"
- El sitio tardó en cargar. Aumenta el timeout en `config.py`

### Error: "Browser closed unexpectedly"
- Instala Chromium: `playwright install chromium`

### No detecta promociones
- Los selectores CSS pueden haber cambiado
- Edita el scraper específico en `scrapers/`

## 📝 TODO

- [ ] Agregar notificaciones por email/Telegram
- [ ] Integrar LLM para parsear T&C complejos
- [ ] Exportar a CSV/Excel
- [ ] Comparador de promociones

## 📄 Licencia

MIT

## 🤝 Contribuir

Pull requests bienvenidos! 

---

**Creado con ❤️ para Argentina** 🇦🇷


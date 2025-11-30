# 📖 Guía de Uso

## 🚀 Inicio Rápido

### 1. Instalación

```bash
# Clonar o descargar el proyecto
cd promo-scraper

# Ejecutar setup automático
chmod +x setup.sh
./setup.sh
```

### 2. Primer Scraping

```bash
# Activar entorno virtual
source venv/bin/activate

# Scrapear todos los supermercados
python scraper.py

# O usar el helper
./run.sh
```

### 3. Ver Resultados

```bash
# Iniciar dashboard web
streamlit run dashboard.py

# Se abrirá en http://localhost:8501
```

---

## 📚 Comandos Disponibles

### Scraper Principal

```bash
# Scrapear todos los supermercados
python scraper.py

# Scrapear solo uno específico
python scraper.py --supermarket carrefour
python scraper.py -s coto

# Modo verbose (más detalles)
python scraper.py --verbose
python scraper.py -v

# Listar supermercados disponibles
python scraper.py --list
python scraper.py -l
```

### Dashboard

```bash
# Iniciar dashboard en puerto por defecto (8501)
streamlit run dashboard.py

# Iniciar en puerto específico
streamlit run dashboard.py --server.port 8080

# Modo headless (sin abrir browser)
streamlit run dashboard.py --server.headless true
```

---

## 🔧 Configuración

### Archivo `config.py`

Personaliza el comportamiento del scraper:

```python
# Delays entre requests
MIN_DELAY = 2  # segundos
MAX_DELAY = 5  # segundos

# Browser
HEADLESS = True  # False para ver el browser

# Habilitar/deshabilitar supermercados
SUPERMARKETS = {
    'carrefour': {
        'enabled': True,  # Cambiar a False para deshabilitar
        ...
    }
}
```

### Usar Proxies (Opcional)

Edita `config.py`:

```python
USE_PROXIES = True
PROXIES = [
    'http://user:pass@proxy1.example.com:8000',
    'http://user:pass@proxy2.example.com:8000',
]
```

---

## 🤖 Automatización

### Linux/Mac - Cron

```bash
# Editar crontab
crontab -e

# Agregar línea para ejecutar diario a las 9 AM
0 9 * * * cd /ruta/al/promo-scraper && /ruta/al/venv/bin/python scraper.py

# Ejemplo con logs
0 9 * * * cd /home/user/promo-scraper && ./run.sh >> /tmp/scraper.log 2>&1
```

### Windows - Task Scheduler

1. Abrir "Programador de tareas"
2. Crear tarea básica
3. Nombre: "Scraper Promociones"
4. Trigger: Diario a las 9:00 AM
5. Acción: Ejecutar programa
   - Programa: `C:\ruta\a\python.exe`
   - Argumentos: `C:\ruta\a\scraper.py`
   - Directorio: `C:\ruta\a\promo-scraper`

### GitHub Actions (En la nube - GRATIS)

El proyecto incluye `.github/workflows/scraper.yml` configurado para:
- ✅ Ejecutar diario automáticamente
- ✅ Guardar base de datos como artifact
- ✅ 100% gratis (dentro de límites de GitHub)

**Setup:**
1. Subir proyecto a GitHub
2. El workflow se ejecutará automáticamente

---

## 💾 Base de Datos

### Ubicación

```bash
data/promotions.db
```

### Explorar con SQLite

```bash
# Instalar sqlite3
sudo apt install sqlite3  # Linux
brew install sqlite3      # Mac

# Explorar
sqlite3 data/promotions.db

# Queries útiles
SELECT COUNT(*) FROM promotions WHERE is_active = 1;
SELECT supermarket_name, COUNT(*) FROM promotions JOIN supermarkets ON supermarket_id = supermarkets.id GROUP BY supermarket_name;
```

### Backup

```bash
# Backup manual
cp data/promotions.db data/promotions.db.backup

# Backup automático diario
0 23 * * * cp /ruta/a/data/promotions.db /ruta/a/backups/promotions_$(date +\%Y\%m\%d).db
```

---

## 🐛 Troubleshooting

### Error: "playwright not found"

```bash
playwright install chromium
playwright install-deps chromium
```

### Error: "No module named 'playwright_stealth'"

```bash
pip install playwright-stealth
```

### No encuentra promociones

1. Verifica que el sitio carga correctamente
2. Los selectores CSS pueden haber cambiado
3. Ejecuta con `--verbose` para ver errores
4. Ajusta selectores en `scrapers/generic_scraper.py`

### Browser falla en servidor

```bash
# Instalar dependencias de sistema
playwright install-deps chromium

# O usar headless
# En config.py: HEADLESS = True
```

---

## 🔍 Ajustar Selectores

Si un supermercado no extrae bien las promociones, ajusta su scraper:

```python
# scrapers/carrefour_scraper.py

# Cambiar selectores según HTML del sitio
promotions = await page.query_selector_all('.tu-selector-css')

# Ver HTML en browser developer tools (F12)
# Copiar selectores específicos del sitio
```

---

## 📊 Exportar Datos

### A CSV

```python
import pandas as pd
from database import Database

db = Database()
promos = db.get_active_promotions()
df = pd.DataFrame(promos)
df.to_csv('promociones.csv', index=False)
```

### A JSON

```python
import json
from database import Database

db = Database()
promos = db.get_active_promotions()

with open('promociones.json', 'w', encoding='utf-8') as f:
    json.dump(promos, f, indent=2, ensure_ascii=False)
```

---

## 🚀 Siguientes Pasos

### Integrar LLM para T&C

```python
# terms_parser.py
import openai

def parse_with_llm(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "user",
            "content": f"Extrae requisitos y exclusiones de: {text}"
        }]
    )
    return response
```

### Notificaciones

```python
# En scraper.py
import requests

def send_telegram_notification(message):
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message})
```

### API REST

```python
# api.py
from fastapi import FastAPI
from database import Database

app = FastAPI()
db = Database()

@app.get("/promotions")
def get_promotions(supermarket: str = None):
    return db.get_active_promotions(supermarket)

# Ejecutar: uvicorn api:app --reload
```

---

## 💡 Tips

1. **Ejecuta primero manualmente** para verificar que funciona
2. **Revisa logs** si algo falla en automatización
3. **Haz backups** de la base de datos
4. **Ajusta delays** si te bloquean (aumentar MIN_DELAY/MAX_DELAY)
5. **Usa proxies** si scrapeas con mucha frecuencia

---

¿Necesitas ayuda? Revisa el `README.md` o abre un issue en GitHub.


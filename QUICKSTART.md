# ⚡ QUICKSTART - Inicio Rápido

## 🚀 3 Pasos para Empezar

### 1️⃣ Instalación (5 minutos)

```bash
# Ir al directorio
cd /tmp/promo-scraper

# Ejecutar setup automático
chmod +x setup.sh
./setup.sh
```

Esto instalará:
- ✅ Entorno virtual Python
- ✅ Todas las dependencias
- ✅ Playwright + Chromium
- ✅ Base de datos SQLite

---

### 2️⃣ Primer Scraping (2 minutos)

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar scraper
python scraper.py

# O usar el helper script
./run.sh
```

Verás algo como:
```
[10:30:15] INFO: 🚀 Iniciando browser...
[10:30:18] INFO: 📍 Iniciando scrape: Carrefour
[10:30:25] INFO: ✅ Carrefour: 23 promociones guardadas
...
```

---

### 3️⃣ Ver Dashboard (1 minuto)

```bash
streamlit run dashboard.py
```

Se abrirá automáticamente en tu navegador: `http://localhost:8501`

🎉 **¡Listo!** Ya tienes tu sistema de scraping funcionando.

---

## 📋 Comandos Útiles

```bash
# Listar supermercados disponibles
python scraper.py --list

# Scrapear solo uno (más rápido para testing)
python scraper.py --supermarket carrefour

# Ver más detalles (debugging)
python scraper.py --verbose

# Explorar base de datos
sqlite3 data/promotions.db "SELECT COUNT(*) FROM promotions WHERE is_active = 1;"
```

---

## 🤖 Automatización (Opcional)

### Opción A: Cron (Linux/Mac)

```bash
# Editar crontab
crontab -e

# Agregar esta línea (ejecutar todos los días a las 9 AM):
0 9 * * * cd /tmp/promo-scraper && ./run.sh >> /tmp/scraper.log 2>&1
```

### Opción B: GitHub Actions (Gratis, en la nube)

1. Sube el proyecto a GitHub
2. El workflow `.github/workflows/scraper.yml` se ejecutará automáticamente todos los días

---

## ⚙️ Configuración Básica

Edita `config.py` para:

```python
# Ver el browser mientras scrapea (útil para debugging)
HEADLESS = False

# Ajustar delays (si te bloquean, aumentar)
MIN_DELAY = 3  
MAX_DELAY = 8

# Deshabilitar un supermercado
SUPERMARKETS = {
    'carrefour': {
        'enabled': False,  # ← Cambiar aquí
        ...
    }
}
```

---

## 🐛 Problemas Comunes

### Error: "playwright not found"
```bash
playwright install chromium
```

### Browser falla en servidor sin GUI
```python
# En config.py:
HEADLESS = True
```

### No encuentra promociones en un sitio
1. Los selectores CSS pueden haber cambiado
2. Ejecuta con `--verbose` para ver el error
3. Ajusta selectores en `scrapers/generic_scraper.py`

---

## 📖 Documentación Completa

- **README.md** - Información general del proyecto
- **USAGE.md** - Guía detallada de uso y configuración
- **config.py** - Todas las configuraciones disponibles

---

## 💡 Tips Pro

1. **Primero prueba con un solo supermercado:**
   ```bash
   python scraper.py -s carrefour
   ```

2. **Usa modo no-headless para ver qué está pasando:**
   ```python
   # config.py
   HEADLESS = False
   ```

3. **Revisa la base de datos directamente:**
   ```bash
   sqlite3 data/promotions.db
   .tables
   SELECT * FROM promotions LIMIT 5;
   ```

4. **Exporta a CSV para usar en Excel:**
   ```python
   import pandas as pd
   from database import Database
   
   db = Database()
   promos = db.get_active_promotions()
   pd.DataFrame(promos).to_csv('promociones.csv', index=False)
   ```

---

## 🎯 Próximos Pasos

Una vez que funcione básicamente, puedes:

1. ✅ **Automatizar** ejecución diaria (cron o GitHub Actions)
2. ✅ **Agregar notificaciones** (Telegram, email) cuando aparezcan nuevas promos
3. ✅ **Integrar LLM** (OpenAI/Claude) para parsear T&C complejos mejor
4. ✅ **Crear API REST** con FastAPI para consumir desde otras apps
5. ✅ **Agregar proxies** si necesitas escalar (Webshare.io, $3/mes)

---

## 🆘 Ayuda

¿Algo no funciona? 

1. Ejecuta con `--verbose` para ver errores detallados
2. Revisa USAGE.md para troubleshooting
3. Verifica que tengas Python 3.8+

---

**¡Éxito con tu scraper! 🎉🛒**


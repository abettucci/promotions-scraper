#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# test_scrapers.sh  –  Setup + prueba local de scrapers
# Uso:
#   ./test_scrapers.sh             # prueba carrefour + dia (default)
#   ./test_scrapers.sh carrefour
#   ./test_scrapers.sh dia
#   ./test_scrapers.sh cencosud
#   ./test_scrapers.sh all         # todos los supermercados
# ─────────────────────────────────────────────────────────────
set -e

SCRAPER="${1:-carrefour,dia}"
VENV_DIR=".venv_test"
PYTHON=~/.pyenv/versions/3.11.13/bin/python3

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Promotions Scraper — Test Local"
echo " Scrapers: $SCRAPER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Verificar Python ──────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
  echo "❌ Python 3.11.13 no encontrado en ~/.pyenv/versions/3.11.13"
  echo "   Instalá con: pyenv install 3.11.13"
  exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# ── 2. Crear / reutilizar venv ───────────────────────────────
if [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "📦 Creando entorno virtual en $VENV_DIR..."
  $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# ── 3. Instalar dependencias (solo si faltan) ────────────────
if ! python -c "import playwright" 2>/dev/null; then
  echo "📦 Instalando dependencias..."
  pip install --quiet --upgrade pip
  pip install --quiet \
    playwright==1.56.0 \
    playwright-stealth==1.0.6 \
    "crawl4ai>=0.4.0" \
    "beautifulsoup4>=4.12.0" \
    "lxml>=6.0.2" \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    google-generativeai>=0.8.0 \
    anthropic>=0.18.0 \
    "scrapling[fetchers]>=0.4.0" \
    sqlalchemy==2.0.23 \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.6" \
    passlib[bcrypt]==1.7.4 \
    "python-jose[cryptography]==3.3.0"
  echo "🌐 Instalando navegador Chromium..."
  playwright install chromium --with-deps
  echo "🤖 Configurando Crawl4AI..."
  crawl4ai-setup 2>/dev/null || true
else
  echo "✅ Dependencias ya instaladas"
fi

# ── 4. Correr el script de test ──────────────────────────────
echo ""
echo "🚀 Corriendo test..."
DEBUG_SCRAPER=true python test_scrapers.py "$SCRAPER" 2>&1 | tee test_output.log

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Log guardado en: test_output.log"
echo " HTML de debug:   debug_*.html"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

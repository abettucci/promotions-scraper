Write-Output "Setup del Scraper de Promociones Bancarias"
Write-Output "=============================================`n"

# Verificar Python
$python = Get-Command python -ErrorAction SilentlyContinue

if (-not $python) {
    Write-Output "ERROR: Python no esta instalado"
    Write-Output "Instala Python 3.8 o superior"
    exit 1
}

$PYTHON_VERSION = & python --version
Write-Output "Python encontrado: $PYTHON_VERSION`n"

# Crear entorno virtual
Write-Output "Creando entorno virtual..."
python -m venv venv

# Activar entorno virtual
Write-Output "Activando entorno virtual..."
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\venv\Scripts\Activate.ps1

# Actualizar pip
Write-Output "Actualizando pip..."
pip install --upgrade pip

# Instalar dependencias
Write-Output "Instalando dependencias..."
pip install -r requirements.txt

# Instalar Playwright + Chromium
Write-Output "Instalando Playwright y Chromium..."
playwright install chromium

# Crear carpeta data
Write-Output "Creando carpeta 'data'..."
if (-not (Test-Path -Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

# Crear .env si no existe
if (-not (Test-Path ".env")) {
    Write-Output "Creando archivo .env..."
    Copy-Item ".env.example" ".env"
}

# Inicializar base de datos
Write-Output "Inicializando base de datos..."
python -c "from database import Database; Database()"

Write-Output "`n============================================="
Write-Output "Setup completado!"
Write-Output "=============================================`n"

Write-Output "Proximos pasos:"
Write-Output "1. Activar entorno virtual: .\venv\Scripts\Activate.ps1"
Write-Output "2. Ejecutar scraper: python scraper.py"
Write-Output "3. Ver dashboard: streamlit run dashboard.py"

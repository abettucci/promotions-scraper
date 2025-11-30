Write-Output "Scraper de Promociones Bancarias"
Write-Output "===================================`n"

# Verificar que existe el entorno virtual
if (-not (Test-Path "venv")) {
    Write-Output "ERROR: No se encontro el entorno virtual."
    Write-Output "Ejecuta primero:"
    Write-Output "   python -m venv venv"
    Write-Output "   .\venv\Scripts\Activate.ps1"
    Write-Output "   pip install -r requirements.txt"
    exit 1
}

# Activar entorno virtual
Write-Output "Activando entorno virtual..."
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\venv\Scripts\Activate.ps1

# Verificar instalacion de Playwright
try {
    playwright --version | Out-Null
} catch {
    Write-Output "Instalando Playwright..."
    playwright install chromium
}

# Ejecutar scraper
Write-Output "`nIniciando scraper...`n"
python scraper.py @args

Write-Output "`nEjecucion finalizada.`n"
Write-Output "Para ver los resultados:"
Write-Output "   streamlit run dashboard.py"

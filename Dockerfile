# Dockerfile para el backend (FastAPI) en Railway
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements del API (sin Scrapling/Playwright)
# El scraper corre en GitHub Actions, no en Railway
COPY requirements-api.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements-api.txt

# Copiar el resto del código
COPY . .

# Crear directorios de datos
# data/ → promotions.db viene del repo (se actualiza con cada deploy via GitHub Actions)
# userdata/ → users.db persiste en Railway Volume (montar en /app/userdata)
RUN mkdir -p data userdata

# Puerto que usa Railway
EXPOSE 8000

# Comando para iniciar FastAPI
CMD ["sh","-c","uvicorn api:app --host 0.0.0.0 --port $PORT"]
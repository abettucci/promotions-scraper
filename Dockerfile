# Dockerfile para Railway (API + Scraper)
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema (para Playwright/Chromium y compilación)
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libxshmfence1 \
    libx11-xcb1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Instalar browsers para Playwright y Scrapling
RUN playwright install chromium
RUN scrapling install || true

# Copiar el resto del código
COPY . .

# Crear directorios de datos
# data/   → promotions.db (scraper escribe acá directamente)
# userdata/ → users.db persiste en Railway Volume (montar en /app/userdata)
RUN mkdir -p data userdata

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port $PORT"]

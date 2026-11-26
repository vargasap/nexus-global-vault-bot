FROM python:3.11-slim

# Instalar herramientas básicas del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del ecosistema
COPY . .

# Puerto para Render/Koyeb Health Check
EXPOSE 10000

# Iniciar supervisor de los 3 bots 24/7
CMD ["python", "cloud_runner.py"]

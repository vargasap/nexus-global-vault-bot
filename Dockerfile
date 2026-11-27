FROM python:3.11-slim

# Instalar herramientas básicas del sistema (FFmpeg + librerías para OpenCV/MediaPipe en la nube)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del ecosistema
COPY . .

# Puerto para Render/Koyeb Health Check
EXPOSE 10000

# Iniciar supervisor de los bots 24/7 en la nube
CMD ["python", "cloud_runner.py"]

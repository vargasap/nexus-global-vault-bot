#!/bin/bash
# ==============================================================
# SCRIPT DE INSTALACIÓN Y DESPLIEGUE AUTOMÁTICO 24/7 EN VPS LINUX
# Bot Oficial: @nexus_global_vault_bot
# ==============================================================

set -e

echo "🚀 Iniciando configuración del servidor 24/7 para Nexus Global Vault..."

# 1. Actualizar paquetes del sistema
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git curl

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar librerías
pip install --upgrade pip
pip install -r requirements.txt

# 4. Crear Servicio Systemd para que arranque siempre al encender el servidor y se reinicie ante fallos
SERVICE_FILE="/etc/systemd/system/nexus-bot.service"
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "⚙️ Configurando servicio en segundo plano: $SERVICE_FILE"
sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=Nexus Global Vault Telegram Super-Bot 24/7
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/bot.py
Restart=always
RestartSec=5
StandardOutput=append:$CURRENT_DIR/bot_runtime.log
StandardError=append:$CURRENT_DIR/bot_runtime.log

[Install]
WantedBy=multi-user.target
EOL

# 5. Activar e iniciar servicio
sudo systemctl daemon-reload
sudo systemctl enable nexus-bot.service
sudo systemctl restart nexus-bot.service

echo ""
echo "=========================================================="
echo "🎉 ¡EL BOT ESTÁ CORRIENDO 24/7 EN TU SERVIDOR EN LA NUBE!"
echo "Comprobar estado:  sudo systemctl status nexus-bot.service"
echo "Ver logs en vivo:  tail -f bot_runtime.log"
echo "=========================================================="

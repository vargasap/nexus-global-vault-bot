# 🚀 Nexus Global Vault — Super-Bot 8-en-1 Oficial para Telegram

[![Python 3.11](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-2CA5E0.svg?logo=telegram)](https://core.telegram.org/bots/api)
[![Telegram Stars](https://img.shields.io/badge/Monetization-Telegram%20Stars%20(XTR)-F59E0B.svg)](https://telegram.org/blog/telegram-stars)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker)](https://www.docker.com/)
[![License MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Bot Oficial en Vivo:** [@nexus_global_vault_bot](https://t.me/nexus_global_vault_bot)

---

## 📖 Descripción General

**Nexus Global Vault** es una suite integral de 8 herramientas de alta demanda empaquetadas en un único bot de Telegram. Diseñado con una arquitectura modular orientada al crecimiento viral, combina:
1. **1 Prueba Gratuita Individual** por cada una de las 8 herramientas.
2. **Paneles Explicativos Interactivos** con guías paso a paso para cada servicio.
3. **Monetización Nativa con Telegram Stars (`XTR`)** en 3 paquetes oficiales ($0.99, $2.99 y $9.99 USD).
4. **Bucle Viral de Referidos (Share to Unlock):** Cada entrega de archivo adjunta un botón interactivo para compartir el bot en 1 toque.
5. **Deep-Linking Temático:** Enlaces directos que abren la herramienta específica según la campaña de origen.
6. **Telegram Mini App (TMA):** Portal web interactivo listo para integrarse directamente dentro del chat de Telegram.

---

## 🛠️ Las 8 Herramientas Oficiales

| # | Herramienta | Descripción Técnica |
|---|---|---|
| 1️⃣ | **🎬 Descargador de Video HD** | Descarga videos en 1080p sin marca de agua de TikTok, Reels, Shorts, X y Pinterest mediante `yt-dlp`. |
| 2️⃣ | **🎵 Extractor de Audio MP3** | Extrae la pista de audio en 320kbps de cualquier video y la entrega como archivo nativo de música. |
| 3️⃣ | **🪄 Stickers con Sonido** | Convierte fotos a formato oficial `.webp` y adjunta una nota de voz con audio meme sincronizado, además de una galería de stickers virales. |
| 4️⃣ | **📸 Mejorador de Fotos 4K** | Optimiza nitidez, contraste y color en Ultra-HD sin compresión. |
| 5️⃣ | **📄 Foto a PDF Oficial** | Compila imágenes o apuntes en documentos PDF oficiales listos para imprimir o compartir. |
| 6️⃣ | **📱 Códigos QR en HD** | Genera códigos QR de alta resolución para enlaces, redes sociales o textos. |
| 7️⃣ | **🌐 Traductor Multi-Modal** | Traducción inteligente con soporte para **Modo Texto**, **Modo Audio / Voz** (con pronunciación hablada en nota de voz) y **Modo Lectura** para artículos extensos. |
| 8️⃣ | **⚡ Resumidor con IA** | Sintetiza artículos largos, noticias o documentos en los 5 puntos clave indispensables. |

---

## 💳 Modelo de Negocio (Telegram Stars `XTR`)

Integración nativa con la pasarela oficial de Telegram para compras directas con Apple Pay, Google Play o tarjeta:
* 🥉 **Básico:** 3 Usos por **$0.99 USD** (50 Stars)
* 🥈 **Más Vendido:** 10 Usos por **$2.99 USD** (150 Stars)
* 👑 **VIP Ilimitado:** **$9.99 USD** (500 Stars / 50+ usos con prioridad máxima)

---

## 🚀 Despliegue Rápido (Quickstart)

### 1. Clonar el Repositorio
```bash
git clone https://github.com/vargasap/nexus-global-vault-bot.git
cd nexus-global-vault-bot
```

### 2. Configuración
Copia o renombra `config.example.json` a `config.json` e introduce tu token de Telegram:
```json
{
  "bot_token": "TU_TOKEN_DE_TELEGRAM_AQUI",
  "currency": "XTR",
  "fallback_language": "en",
  ...
}
```

### 3. Ejecución Local (Windows / Mac / Linux)
```bash
python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
python bot.py
```

---

## ☁️ Despliegue 24/7 en Servidor Cloud / VPS

### En Servidor Linux (Ubuntu / Debian) — 1 Comando:
```bash
bash deploy_vps.sh
```
El script configura automáticamente:
* Instalación de Python 3, `ffmpeg` y librerías.
* Servicio del sistema `systemd` (`nexus-bot.service`) para arranque automático y reinicio ante caídas.

### Con Docker:
```bash
docker compose up -d --build
```

---

## 📂 Estructura del Proyecto

```text
├── bot.py                        # Motor principal y enrutador de los 8 servicios
├── config.json                   # Configuración de planes y traducciones multilingüe
├── config.example.json           # Plantilla limpia de configuración
├── deploy_vps.sh                 # Script de despliegue automático en 1 comando (Linux)
├── Dockerfile                    # Contenedor de producción con ffmpeg
├── docker-compose.yml            # Orquestador Docker con volúmenes de persistencia
├── requirements.txt              # Dependencias de Python
├── popular_stickers/             # Galería de stickers WebP y efectos de sonido sincronizados
├── promociones_redes/            # Videos promocionales 1080x1920 y kit de difusión
│   ├── videos_tiktok/            # 10 videos verticales optimizados para TikTok/Reels
│   ├── video_avatar_explicativo_oficial.mp4  # Video del Avatar con locución
│   └── KIT_MENSAJES_LISTOS_PARA_COPIAR.txt  # Copys listos para grupos y canales
└── web_hub/                      # Telegram Mini App interactiva (HTML5/CSS3)
    └── index.html
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.

# ☁️ GUÍA MAESTRA: CÓMO MONTAR EL BOT 24/7 EN LA NUBE

Esta guía explica con total claridad técnica cómo funciona la infraestructura de Telegram y las opciones exactas paso a paso para tener tu bot funcionando las 24 horas del día, los 365 días del año, sin necesidad de tener tu ordenador encendido.

---

## 🧠 1. La Realidad Técnica: ¿Cómo funciona Telegram?

Es muy importante entender la división de tareas entre Telegram y tu bot:

```
┌──────────────────────────────────────┐       ┌─────────────────────────────────────────┐
│        SERVIDORES DE TELEGRAM        │       │       TU SERVIDOR CLOUD / HOSTING       │
│                                      │       │                                         │
│  • Cuentas de usuarios y chats       │ <===> │  • Código del Bot (bot.py)              │
│  • Pasarela de pagos Telegram Stars  │       │  • Descargador de Videos (yt-dlp)       │
│  • Bot API Gateway (mensajes/botones)│       │  • Motor de Stickers con Sonido (ffmpeg)│
│  • Interfaz de Telegram Mini App     │       │  • Inteligencia Artificial y Traductor  │
└──────────────────────────────────────┘       └─────────────────────────────────────────┘
```

* **Telegram aloja:** El nombre del bot (`@nexus_global_vault_bot`), los botones del menú, la base de datos de usuarios de Telegram y el cobro de Stars (`XTR`).
* **Tu Servidor aloja:** El "cerebro" y el procesamiento pesado (descargar videos en 1080p, recortar imágenes, mezclar audios con ffmpeg y generar PDFs).

> [!NOTE]
> Telegram **no permite** subir scripts de Python ni ejecutar herramientas pesadas como `ffmpeg` o `yt-dlp` directamente en sus servidores por motivos de seguridad mundial. Por eso, todos los bots profesionales de Telegram (como los descargadores con millones de usuarios) utilizan un **Servidor en la Nube (VPS)** conectado permanentemente a Telegram.

---

## 🚀 2. Las 3 Mejores Opciones para Alojar tu Bot 24/7

### Opción A: Servidor VPS Económico (Recomendado para Máxima Velocidad)
Un VPS (Servidor Privado Virtual) cuesta entre **$3 y $5 USD al mes** y te da un servidor Linux propio con conexión de fibra de 1 Gbps:
* **Proveedores recomendados:**
  * **Hetzner Cloud:** ~$4 USD/mes (Los servidores más rápidos de Europa y América).
  * **DigitalOcean / Vultr / Linode:** $4 - $5 USD/mes.
  * **OVHcloud:** ~$3.50 USD/mes.
  * **Oracle Cloud:** ¡Tiene un plan **100% GRATIS DE POR VIDA** (Always Free Tier) con 4 núcleos y 24 GB de RAM!

**Cómo se instala en tu VPS en 1 solo comando:**
1. Abres la consola de tu VPS (por SSH o desde la web del proveedor).
2. Clonas o subes la carpeta `telegram_stars_engine`.
3. Ejecutas:
   ```bash
   bash deploy_vps.sh
   ```
   *(El script instala todo automáticamente, configura el servicio para que arranque al encender y se reinicie solo ante cualquier fallo).*

---

### Opción B: Despliegue con Docker (En 1 Comando)
Si tienes Docker instalado en cualquier servidor o en tu equipo:
```bash
docker compose up -d --build
```
El contenedor se mantendrá corriendo de forma indefinida en segundo plano.

---

### Opción C: Plataformas Cloud con 1 Clic (PaaS)
Si no quieres tocar comandos de Linux:
* **Railway.app:** Conectas tu cuenta, subes la carpeta del bot y Railway lo arranca solo usando el archivo `Dockerfile` que te dejé listo.
* **Render.com:** Creas un "Background Worker", seleccionas el repositorio y se ejecuta de forma continua.

---

## 📱 3. Montar la Mini App Oficial dentro de Telegram (TMA)

Telegram permite que los bots abran una **Mini App interactiva en pantalla completa** directamente dentro del chat sin salir de Telegram.

Ya dejamos listo el diseño completo en:
`c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\web_hub\index.html`

### Pasos para activarla en @BotFather:
1. Abre Telegram y busca **@BotFather**.
2. Envía el comando: `/mybots`
3. Selecciona tu bot: `@nexus_global_vault_bot`
4. Ve a **Bot Settings** ➡️ **Menu Button** ➡️ **Configure menu button**.
5. Te pedirá la URL de tu Web App (puedes subir la carpeta `web_hub` gratis a **Vercel**, **Netlify** o **GitHub Pages** en 1 minuto).
6. Asigna el texto del botón: `🛠️ Abrir Servicios VIP`

¡A partir de ese momento, los usuarios tendrán un botón permanente al lado del teclado que abrirá tu portal interactivo dentro de Telegram!

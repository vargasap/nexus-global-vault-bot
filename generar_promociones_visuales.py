import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

PROMO_DIR = r"c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\promociones_redes"
os.makedirs(PROMO_DIR, exist_ok=True)

BOT_URL = "https://t.me/nexus_global_vault_bot"

def create_qr(data, size=300):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img.resize((size, size))

# 1. GENERAR HISTORIA VERTICAL (1080 x 1920) PARA TIKTOK / REELS / STORIES
def generate_story_vertical():
    w, h = 1080, 1920
    im = Image.new("RGB", (w, h), color=(10, 12, 18))
    draw = ImageDraw.Draw(im)

    # Gradient background simulation
    for y in range(h):
        r = int(12 + (y / h) * 15)
        g = int(16 + (y / h) * 30)
        b = int(28 + (y / h) * 60)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Top pill
    draw.rounded_rectangle([240, 100, 840, 170], radius=35, fill=(0, 136, 204))
    draw.text((540, 135), "⚡ OFICIAL TELEGRAM 2026", fill="white", anchor="mm")

    # Main Title
    draw.text((540, 260), "SUPER-BOT #1 DE TELEGRAM", fill=(255, 215, 0), anchor="mm")
    draw.text((540, 320), "8 HERRAMIENTAS VIRALES EN 1 SOLO LUGAR", fill=(240, 240, 250), anchor="mm")

    # Offer Badge
    draw.rounded_rectangle([140, 390, 940, 480], radius=25, fill=(34, 197, 94))
    draw.text((540, 435), "🎁 ¡1 PRUEBA GRATIS POR CADA SERVICIO!", fill="white", anchor="mm")

    # Services List Box
    services = [
        "1️⃣ 🎬 Video HD: TikTok, Reels, Shorts sin marca",
        "2️⃣ 🎵 Audio MP3: Extrae música en 320kbps",
        "3️⃣ 🪄 Sticker Maker: Fotos a Stickers oficiales",
        "4️⃣ 📸 Mejorar Fotos: Ultra-HD y nitidez 4K",
        "5️⃣ 📄 Foto a PDF: Documentos oficiales listos",
        "6️⃣ 📱 Código QR: Generador de alta resolución",
        "7️⃣ 🌐 Traductor: +50 idiomas al instante",
        "8️⃣ ⚡ Resumir IA: Artículos y textos en 5 puntos"
    ]

    box_y = 520
    for idx, s in enumerate(services):
        y_pos = box_y + (idx * 95)
        draw.rounded_rectangle([100, y_pos, 980, y_pos + 80], radius=18, fill=(22, 27, 44), outline=(40, 50, 80), width=2)
        draw.text((140, y_pos + 40), s, fill="white", anchor="lm")

    # QR Code Section
    qr_img = create_qr(BOT_URL, size=340)
    qr_x = (w - 340) // 2
    qr_y = 1320
    # White background for QR
    draw.rounded_rectangle([qr_x - 15, qr_y - 15, qr_x + 355, qr_y + 355], radius=20, fill="white")
    im.paste(qr_img, (qr_x, qr_y))

    # Bottom Call to Action
    draw.text((540, 1720), "ESCANEA CON TU CÁMARA O BÚSCALO EN TELEGRAM:", fill=(160, 175, 200), anchor="mm")
    draw.text((540, 1780), "@nexus_global_vault_bot", fill=(56, 189, 248), anchor="mm")
    draw.text((540, 1840), "👉 https://t.me/nexus_global_vault_bot", fill="white", anchor="mm")

    out_path = os.path.join(PROMO_DIR, "historia_viral_tiktok_reels.png")
    im.save(out_path, quality=95)
    print(f"✅ Generada Historia Vertical: {out_path}")

# 2. GENERAR POST CUADRADO (1080 x 1080) PARA FEED, TWITTER/X Y CANALES
def generate_square_post():
    w, h = 1080, 1080
    im = Image.new("RGB", (w, h), color=(12, 16, 26))
    draw = ImageDraw.Draw(im)

    # Top Header
    draw.rounded_rectangle([200, 50, 880, 120], radius=35, fill=(0, 136, 204))
    draw.text((540, 85), "🔥 DESCARGADOR & 8 HERRAMIENTAS HD", fill="white", anchor="mm")

    draw.text((540, 180), "@nexus_global_vault_bot", fill=(56, 189, 248), anchor="mm")
    draw.text((540, 230), "🎁 ¡1 Prueba Gratis en cada una de las 8 herramientas!", fill=(255, 215, 0), anchor="mm")

    # Left Column: Services
    services_left = [
        "🎬 1. Video HD sin marca",
        "🎵 2. Extraer Audio MP3",
        "🪄 3. Creador de Stickers",
        "📸 4. Mejorar Fotos HD",
        "📄 5. Foto a PDF",
        "📱 6. Código QR",
        "🌐 7. Traductor Universal",
        "⚡ 8. Resumen con IA"
    ]

    for idx, s in enumerate(services_left):
        y_pos = 300 + (idx * 80)
        draw.rounded_rectangle([60, y_pos, 600, y_pos + 65], radius=14, fill=(24, 30, 50), outline=(50, 65, 100), width=1)
        draw.text((90, y_pos + 32), s, fill="white", anchor="lm")

    # Right Column: QR Code Box
    qr_img = create_qr(BOT_URL, size=340)
    qr_x = 670
    qr_y = 350
    draw.rounded_rectangle([qr_x - 15, qr_y - 15, qr_x + 355, qr_y + 355], radius=20, fill="white")
    im.paste(qr_img, (qr_x, qr_y))

    draw.text((840, 750), "¡ESCANEA AQUÍ!", fill=(255, 215, 0), anchor="mm")
    draw.text((840, 785), "Abre directo en Telegram", fill=(160, 175, 200), anchor="mm")

    # Bottom bar
    draw.rounded_rectangle([60, 960, 1020, 1030], radius=20, fill=(34, 197, 94))
    draw.text((540, 995), "👉 ENTRA GRATIS AHORA: t.me/nexus_global_vault_bot", fill="white", anchor="mm")

    out_path = os.path.join(PROMO_DIR, "post_cuadrado_feed_redes.png")
    im.save(out_path, quality=95)
    print(f"✅ Generado Post Cuadrado: {out_path}")

if __name__ == "__main__":
    generate_story_vertical()
    generate_square_post()

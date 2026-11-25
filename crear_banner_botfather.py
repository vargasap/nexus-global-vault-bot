import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = r"c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\promociones_redes"
os.makedirs(OUT_DIR, exist_ok=True)
BANNER_PATH = os.path.join(OUT_DIR, "banner_intro_botfather_640x360.png")

# Telegram description picture standard: 640 x 360
w, h = 640, 360
im = Image.new("RGB", (w, h), color=(15, 23, 42))
draw = ImageDraw.Draw(im)

# Gradient background
for y in range(h):
    r = int(15 + (y/h) * 15)
    g = int(23 + (y/h) * 25)
    b = int(42 + (y/h) * 50)
    draw.line([(0, y), (w, y)], fill=(r, g, b))

# Header badge
draw.rounded_rectangle([180, 25, 460, 65], radius=18, fill=(0, 136, 204))
draw.text((w//2, 45), "⚡ SUPER-BOT OFICIAL 2026", fill="white", anchor="mm")

# Main Title
draw.text((w//2, 110), "NEXUS GLOBAL VAULT", fill=(255, 215, 0), anchor="mm")
draw.text((w//2, 145), "8 HERRAMIENTAS EN 1 SOLO LUGAR", fill=(240, 240, 255), anchor="mm")

# Services pill
draw.rounded_rectangle([40, 180, 600, 250], radius=15, fill=(30, 41, 59), outline=(56, 189, 248), width=2)
draw.text((w//2, 202), "🎬 Videos HD • 🎵 MP3 • 🪄 Stickers • 📸 4K", fill="white", anchor="mm")
draw.text((w//2, 228), "📄 PDF • 📱 QR • 🌐 Traductor • ⚡ Resumidor IA", fill=(148, 163, 184), anchor="mm")

# Offer Badge
draw.rounded_rectangle([100, 275, 540, 325], radius=15, fill=(34, 197, 94))
draw.text((w//2, 300), "🎁 ¡1 PRUEBA 100% GRATIS POR HERRAMIENTA!", fill="white", anchor="mm")

im.save(BANNER_PATH, quality=95)
print("✅ Banner guardado exitosamente en:", BANNER_PATH)

import os
import cv2
import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont

PROMO_DIR = r"c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\promociones_redes\videos_tiktok"
os.makedirs(PROMO_DIR, exist_ok=True)

BOT_URL = "https://t.me/nexus_global_vault_bot"
WIDTH, HEIGHT = 1080, 1920
FPS = 30
DURATION_SEC = 5
TOTAL_FRAMES = FPS * DURATION_SEC

# 10 Video concepts
VIDEOS_DATA = [
    {
        "id": "1",
        "title": "EL SUPER-BOT 8 EN 1 DE TELEGRAM",
        "subtitle": "¡Todas las herramientas que necesitas en 1 solo chat!",
        "badge": "🔥 +500,000 USUARIOS DIARIOS",
        "highlight": "🎬 Videos HD • 🎵 MP3 • 🪄 Stickers • 📸 4K",
        "color_accent": (0, 136, 204),
        "cta": "Prueba GRATIS en Telegram: @nexus_global_vault_bot"
    },
    {
        "id": "2",
        "title": "DESCARGA VIDEOS DE TIKTOK SIN MARCA DE AGUA",
        "subtitle": "También Reels, Shorts y X en calidad 1080p HD",
        "badge": "⚡ DESCARGA EN 1 SEGUNDO",
        "highlight": "Solo pega el link en el bot y listo",
        "color_accent": (254, 44, 85),
        "cta": "Usa tu prueba gratis: @nexus_global_vault_bot"
    },
    {
        "id": "3",
        "title": "STICKERS CON SONIDO PARA TELEGRAM",
        "subtitle": "¡Convierte tus fotos en stickers con notas de audio meme!",
        "badge": "🪄 NUEVA FUNCIÓN VIRAL",
        "highlight": "🐱 Cat Pop • 🐶 Doge • 🐸 Pepe • 😂 Risas",
        "color_accent": (168, 85, 247),
        "cta": "Crea tus stickers en: @nexus_global_vault_bot"
    },
    {
        "id": "4",
        "title": "EXTRAE EL AUDIO MP3 DE CUALQUIER VIDEO",
        "subtitle": "Música en alta calidad 320kbps directa a tu celular",
        "badge": "🎵 CALIDAD ESTUDIO",
        "highlight": "TikTok, YouTube, Reels a MP3 en segundos",
        "color_accent": (34, 197, 94),
        "cta": "Pruébalo gratis en: @nexus_global_vault_bot"
    },
    {
        "id": "5",
        "title": "MEJORA TUS FOTOS BORROSAS A ULTRA-HD",
        "subtitle": "IA que restaura nitidez, color y contraste",
        "badge": "📸 RESOLUCIÓN 4K",
        "highlight": "Fotos antiguas o pixeladas como de estudio",
        "color_accent": (245, 158, 11),
        "cta": "Mejora tus fotos con: @nexus_global_vault_bot"
    },
    {
        "id": "6",
        "title": "CONVIERTE TUS FOTOS A PDF EN 1 CLICK",
        "subtitle": "Documentos oficiales listos para imprimir o enviar",
        "badge": "📄 OFICIAL Y RÁPIDO",
        "highlight": "Apuntes, recibos y fotos a PDF instantáneo",
        "color_accent": (239, 68, 68),
        "cta": "Convierte documentos en: @nexus_global_vault_bot"
    },
    {
        "id": "7",
        "title": "GENERADOR DE CÓDIGOS QR EN ALTA RESOLUCIÓN",
        "subtitle": "Para tus redes sociales, menús, WiFi o enlaces",
        "badge": "📱 ESCANEO PERFECTO",
        "highlight": "QR instantáneo listo para compartir",
        "color_accent": (14, 165, 233),
        "cta": "Crea tu QR en Telegram: @nexus_global_vault_bot"
    },
    {
        "id": "8",
        "title": "TRADUCTOR INTELIGENTE CON NOTAS DE VOZ",
        "subtitle": "Traduce texto y escucha la pronunciación nativa",
        "badge": "🌐 MÁS DE 50 IDIOMAS",
        "highlight": "Modo Texto • Modo Audio / Voz • Modo Lectura",
        "color_accent": (59, 130, 246),
        "cta": "Habla en cualquier idioma: @nexus_global_vault_bot"
    },
    {
        "id": "9",
        "title": "RESUME NOTICIAS Y ARTÍCULOS EN 10 SEGUNDOS",
        "subtitle": "La IA extrae los 5 puntos clave de cualquier texto",
        "badge": "⚡ AHORRA HORAS DE LECTURA",
        "highlight": "Pega el enlace o texto y obtén el núcleo vital",
        "color_accent": (236, 72, 153),
        "cta": "Resume con IA en: @nexus_global_vault_bot"
    },
    {
        "id": "10",
        "title": "¡TIENES 1 USO GRATIS EN LAS 8 HERRAMIENTAS!",
        "subtitle": "Descarga, convierte, edita y traduce sin costo inicial",
        "badge": "🎁 REGALO DE BIENVENIDA",
        "highlight": "Planes VIP desde solo $0.99 (50 Stars)",
        "color_accent": (16, 185, 129),
        "cta": "Entra ahora: @nexus_global_vault_bot"
    }
]

def make_qr_img(url, size=280):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((size, size))

QR_IMG = make_qr_img(BOT_URL, size=280)

def render_frame(video_info, frame_idx):
    progress = frame_idx / TOTAL_FRAMES
    pulse = (np.sin(progress * np.pi * 6) + 1) / 2  # 0 to 1 pulse

    im = Image.new("RGB", (WIDTH, HEIGHT), color=(10, 14, 23))
    draw = ImageDraw.Draw(im)

    # Dynamic gradient background
    c_acc = video_info["color_accent"]
    for y in range(0, HEIGHT, 4):
        ratio = y / HEIGHT
        r = int(10 + ratio * (c_acc[0] * 0.15))
        g = int(14 + ratio * (c_acc[1] * 0.15))
        b = int(23 + ratio * (c_acc[2] * 0.25))
        draw.rectangle([0, y, WIDTH, y + 4], fill=(r, g, b))

    # Top Brand Bar
    draw.rectangle([0, 0, WIDTH, 120], fill=(15, 23, 42))
    draw.text((WIDTH // 2, 60), "TELEGRAM OFICIAL 2026 • @nexus_global_vault_bot", fill=(203, 213, 225), anchor="mm")

    # Animated Badge Pill
    badge_pad = int(pulse * 15)
    bx1, by1, bx2, by2 = 180 - badge_pad, 180, 900 + badge_pad, 260
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=35, fill=c_acc)
    draw.text((WIDTH // 2, 220), video_info["badge"], fill="white", anchor="mm")

    # Main Big Title
    title_words = video_info["title"].split()
    mid = len(title_words) // 2
    line1 = " ".join(title_words[:mid])
    line2 = " ".join(title_words[mid:])
    draw.text((WIDTH // 2, 370), line1, fill=(255, 255, 255), anchor="mm")
    draw.text((WIDTH // 2, 430), line2, fill=(255, 215, 0), anchor="mm")

    # Subtitle
    draw.text((WIDTH // 2, 510), video_info["subtitle"], fill=(226, 232, 240), anchor="mm")

    # Central Feature Card
    card_scale = 1.0 + (pulse * 0.03)
    cw, ch = int(920 * card_scale), int(420 * card_scale)
    cx1 = (WIDTH - cw) // 2
    cy1 = 600
    cx2, cy2 = cx1 + cw, cy1 + ch
    draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=30, fill=(30, 41, 59), outline=c_acc, width=4)

    draw.text((WIDTH // 2, cy1 + 70), "🔥 CARACTERÍSTICA DESTACADA 🔥", fill=(148, 163, 184), anchor="mm")
    draw.text((WIDTH // 2, cy1 + 170), video_info["highlight"], fill="white", anchor="mm")
    
    # Free trial banner inside card
    draw.rounded_rectangle([cx1 + 40, cy1 + 270, cx2 - 40, cy1 + 370], radius=20, fill=(34, 197, 94))
    draw.text((WIDTH // 2, cy1 + 320), "🎁 ¡1 PRUEBA 100% GRATIS INCLUIDA!", fill="white", anchor="mm")

    # QR Code Card
    qr_box_y = 1140
    draw.rounded_rectangle([360, qr_box_y, 720, qr_box_y + 360], radius=25, fill="white", outline=(203, 213, 225), width=3)
    im.paste(QR_IMG, (400, qr_box_y + 40))

    # Bottom CTA Box
    cta_y = 1580
    draw.rounded_rectangle([100, cta_y, 980, cta_y + 180], radius=30, fill=(15, 23, 42), outline=(56, 189, 248), width=3)
    draw.text((WIDTH // 2, cta_y + 55), "👉 ESCANEA EL QR O BÚSCALO EN TELEGRAM:", fill=(148, 163, 184), anchor="mm")
    draw.text((WIDTH // 2, cta_y + 115), "@nexus_global_vault_bot", fill=(56, 189, 248), anchor="mm")

    # Very bottom tag
    draw.text((WIDTH // 2, 1840), "✨ 8 Herramientas en 1 solo Bot • Sin Instalar Apps Extras ✨", fill=(100, 116, 139), anchor="mm")

    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

def generate_video(video_info):
    vid_id = video_info["id"]
    filename = f"video_{vid_id}_{video_info['badge'][:10].replace(' ', '_').replace('🔥', '').replace('⚡', '')}.mp4"
    out_path = os.path.join(PROMO_DIR, filename)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, FPS, (WIDTH, HEIGHT))

    print(f"🎬 Generando Video {vid_id}/10: {filename}...")
    for f in range(TOTAL_FRAMES):
        frame = render_frame(video_info, f)
        out.write(frame)

    out.release()
    print(f"✅ Video {vid_id} listo: {out_path} ({os.path.getsize(out_path)} bytes)")
    return out_path

if __name__ == "__main__":
    for v in VIDEOS_DATA:
        generate_video(v)
    print("\n🎉 ¡Los 10 videos promocionales fueron generados exitosamente!")

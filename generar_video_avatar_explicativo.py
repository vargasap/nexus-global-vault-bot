import os
import cv2
import numpy as np
import qrcode
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageOps

PROMO_DIR = r"c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\promociones_redes"
AVATAR_PATH = r"c:\Users\pc1\Desktop\intergravity\telegram_stars_engine\perfil_bot_avatar.jpg"
AUDIO_PATH = os.path.join(PROMO_DIR, "avatar_explicativo_35s.mp3")
TEMP_VIDEO = os.path.join(PROMO_DIR, "temp_avatar_video.mp4")
FINAL_VIDEO = os.path.join(PROMO_DIR, "video_avatar_explicativo_oficial.mp4")

BOT_URL = "https://t.me/nexus_global_vault_bot"
WIDTH, HEIGHT = 1080, 1920
FPS = 30
DURATION_SEC = 56.5
TOTAL_FRAMES = int(FPS * DURATION_SEC)

# Load and prepare Avatar
raw_avatar = Image.open(AVATAR_PATH).convert("RGBA")
AVATAR_SIZE = 380
raw_avatar = raw_avatar.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

# Create circular mask for avatar
mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
draw_mask = ImageDraw.Draw(mask)
draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
avatar_circle = ImageOps.fit(raw_avatar, mask.size, centering=(0.5, 0.5))
avatar_circle.putalpha(mask)

# Prepare QR Code
def create_qr():
    qr = qrcode.QRCode(version=1, box_size=8, border=1)
    qr.add_data(BOT_URL)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((220, 220))

QR_IMG = create_qr()

# Timeline of speech phases (in seconds)
PHASES = [
    (0.0, 7.5, "¡Hola! Te presento el Super-Bot más potente de Telegram:", "🚀 NEXUS GLOBAL VAULT", (0, 136, 204)),
    (7.5, 14.0, "Tienes 8 herramientas oficiales en un solo chat:", "⚡ 8 SERVICIOS EN 1 SOLO BOT", (14, 165, 233)),
    (14.0, 24.0, "Descarga videos sin marca de agua, extrae MP3 y stickers:", "🎬 VIDEOS HD • 🎵 MP3 • 🪄 STICKERS CON SONIDO", (168, 85, 247)),
    (24.0, 36.0, "Mejora fotos a 4K, crea PDFs, códigos QR y traducción:", "📸 FOTOS 4K • 📄 PDF • 📱 QR • 🌐 TRADUCTOR", (34, 197, 94)),
    (36.0, 45.0, "¡Y lo mejor: tienes 1 prueba gratis en cada servicio!", "🎁 ¡1 PRUEBA 100% GRATIS POR HERRAMIENTA!", (245, 158, 11)),
    (45.0, 56.5, "Búscalo ahora en Telegram o escanea el QR en pantalla:", "👉 @nexus_global_vault_bot", (56, 189, 248))
]

def get_current_phase(t_sec):
    for start, end, sub, title, col in PHASES:
        if start <= t_sec <= end:
            return sub, title, col
    return PHASES[-1][2], PHASES[-1][3], PHASES[-1][4]

print(f"🎬 Iniciando renderizado de video con Avatar ({TOTAL_FRAMES} frames)...")
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(TEMP_VIDEO, fourcc, FPS, (WIDTH, HEIGHT))

for frame_idx in range(TOTAL_FRAMES):
    t_sec = frame_idx / FPS
    sub_text, title_text, accent_color = get_current_phase(t_sec)
    
    # Audio pulse oscillation
    speech_pulse = (np.sin(t_sec * 8.0) + 1.0) * 0.5
    ambient_wave = (np.sin(t_sec * 2.0) + 1.0) * 0.5
    
    # Canvas
    im = Image.new("RGB", (WIDTH, HEIGHT), color=(11, 15, 25))
    draw = ImageDraw.Draw(im)

    # Gradient background
    for y in range(0, HEIGHT, 8):
        ratio = y / HEIGHT
        r = int(11 + ratio * (accent_color[0] * 0.12))
        g = int(15 + ratio * (accent_color[1] * 0.12))
        b = int(25 + ratio * (accent_color[2] * 0.20))
        draw.rectangle([0, y, WIDTH, y + 8], fill=(r, g, b))

    # Top Brand Header
    draw.rectangle([0, 0, WIDTH, 110], fill=(15, 23, 42))
    draw.text((WIDTH // 2, 55), "⭐ TELEGRAM OFICIAL 2026 • ASISTENTE VIRTUAL ⭐", fill=(203, 213, 225), anchor="mm")

    # Avatar Position & Animation
    av_center_x = WIDTH // 2
    av_center_y = 390
    
    # Pulsing holographic rings around avatar
    ring_radius_1 = int(205 + speech_pulse * 12)
    ring_radius_2 = int(225 + ambient_wave * 15)
    draw.ellipse([av_center_x - ring_radius_2, av_center_y - ring_radius_2, av_center_x + ring_radius_2, av_center_y + ring_radius_2], outline=(accent_color[0]//2, accent_color[1]//2, accent_color[2]//2), width=2)
    draw.ellipse([av_center_x - ring_radius_1, av_center_y - ring_radius_1, av_center_x + ring_radius_1, av_center_y + ring_radius_1], outline=accent_color, width=4)

    # Paste circular avatar
    im.paste(avatar_circle, (av_center_x - AVATAR_SIZE // 2, av_center_y - AVATAR_SIZE // 2), avatar_circle)

    # Audio Equalizer Visualizer Bars beneath avatar
    num_bars = 28
    bar_w = 14
    eq_start_x = (WIDTH - (num_bars * 24)) // 2
    eq_y = 615
    for i in range(num_bars):
        bx = eq_start_x + (i * 24)
        h_bar = int(15 + 45 * np.sin(t_sec * 10 + i * 0.6)**2 * (0.6 + 0.4 * speech_pulse))
        draw.rounded_rectangle([bx, eq_y - h_bar, bx + bar_w, eq_y + h_bar], radius=6, fill=accent_color)

    # Avatar Name & Badge
    draw.rounded_rectangle([320, 680, 760, 740], radius=25, fill=(30, 41, 59), outline=accent_color, width=2)
    draw.text((WIDTH // 2, 710), "🎙️ AVATAR OFICIAL NEXUS AI", fill=(240, 240, 255), anchor="mm")

    # Speech Bubble / Subtitle Banner
    card_y = 780
    draw.rounded_rectangle([80, card_y, 1000, card_y + 260], radius=25, fill=(18, 24, 38), outline=accent_color, width=3)
    
    # Live Subtitle
    draw.text((WIDTH // 2, card_y + 60), sub_text, fill=(203, 213, 225), anchor="mm")
    
    # Highlight Title with dynamic glow
    draw.rounded_rectangle([120, card_y + 115, 960, card_y + 215], radius=18, fill=(accent_color[0]//3, accent_color[1]//3, accent_color[2]//3))
    draw.text((WIDTH // 2, card_y + 165), title_text, fill=(255, 255, 255), anchor="mm")

    # Showcase Grid of the 8 Tools
    grid_y = 1080
    tools = [
        ("1️⃣ 🎬 Video HD", 140, grid_y),
        ("2️⃣ 🎵 Audio MP3", 560, grid_y),
        ("3️⃣ 🪄 Sticker Sonido", 140, grid_y + 85),
        ("4️⃣ 📸 Fotos 4K", 560, grid_y + 85),
        ("5️⃣ 📄 Foto a PDF", 140, grid_y + 170),
        ("6️⃣ 📱 Código QR", 560, grid_y + 170),
        ("7️⃣ 🌐 Traductor Voz", 140, grid_y + 255),
        ("8️⃣ ⚡ Resumen IA", 560, grid_y + 255)
    ]
    for name, tx, ty in tools:
        draw.rounded_rectangle([tx, ty, tx + 380, ty + 70], radius=15, fill=(22, 29, 47), outline=(45, 55, 80), width=2)
        draw.text((tx + 190, ty + 35), name, fill="white", anchor="mm")

    # Bottom Call to Action Card with QR
    cta_box_y = 1480
    draw.rounded_rectangle([80, cta_box_y, 1000, cta_box_y + 360], radius=30, fill=(15, 23, 42), outline=(34, 197, 94), width=4)
    
    # Paste QR Code
    im.paste(QR_IMG, (120, cta_box_y + 70))

    # Right side text in CTA card
    draw.text((610, cta_box_y + 75), "🎁 ¡1 PRUEBA GRATIS POR CADA SERVICIO!", fill=(34, 197, 94), anchor="mm")
    draw.text((610, cta_box_y + 140), "ESCANEA O BÚSCALO EN TELEGRAM:", fill=(148, 163, 184), anchor="mm")
    draw.text((610, cta_box_y + 205), "@nexus_global_vault_bot", fill=(56, 189, 248), anchor="mm")
    draw.text((610, cta_box_y + 265), "👉 https://t.me/nexus_global_vault_bot", fill=(240, 240, 255), anchor="mm")

    # Bottom watermark
    draw.text((WIDTH // 2, 1880), "✨ Guarda este video o compártelo con tus amigos ✨", fill=(100, 116, 139), anchor="mm")

    frame_bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    out.write(frame_bgr)

    if frame_idx % 150 == 0:
        print(f"Progreso render: {frame_idx}/{TOTAL_FRAMES} frames ({int(frame_idx/TOTAL_FRAMES*100)}%)")

out.release()
print("✅ Video crudo generado en:", TEMP_VIDEO)

# Mux Audio and Video using ffmpeg
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
print("🎙️ Muxing video con locución en español...")
cmd = [
    ffmpeg_exe, "-y",
    "-i", TEMP_VIDEO,
    "-i", AUDIO_PATH,
    "-c:v", "libx264",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    FINAL_VIDEO
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print("🎉 ¡VIDEO FINAL DEL AVATAR CON LOCUCIÓN COMPLETADO!")
    print(f"📁 Ruta: {FINAL_VIDEO} ({os.path.getsize(FINAL_VIDEO)} bytes)")
    if os.path.exists(TEMP_VIDEO):
        os.remove(TEMP_VIDEO)
else:
    print("❌ Error en muxing ffmpeg:", res.stderr.decode("utf-8", errors="ignore"))

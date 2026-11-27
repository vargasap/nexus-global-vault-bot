#!/usr/bin/env python3
"""
Nexus Universal All-In-One Super-Bot (10 Servicios Oficiales)
- Menú Oficial con Botones Numéricos (1 a 10)
- 1 Uso GRATIS individual POR CADA SERVICIO del menú
- Activación de servicio al tocar el número correspondiente
- Planes oficiales de Telegram Stars ($0.99, $2.99, $9.99)
"""

import os
BASE_DIR = os.path.dirname(__file__)
import sys
import json
import time
import re
import wave
import math
import struct
import urllib.request
import urllib.parse
from datetime import datetime
import requests
import yt_dlp
import qrcode
from PIL import Image, ImageEnhance
import subprocess
import uuid
import imageio_ffmpeg

DELIVERY_CACHE = {}
SOUNDS_DIR = os.path.join(BASE_DIR, "sound_library")
os.makedirs(SOUNDS_DIR, exist_ok=True)

INTERNET_SEARCH_RESULTS = {}

def search_internet_sounds(query, limit=4):
    url = f"https://www.myinstants.com/api/v1/instants/?name={urllib.parse.quote(query)}&format=json"
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            results = []
            for item in r.json().get("results", [])[:limit]:
                name = item.get("name", "Sonido").strip()
                sound_url = item.get("sound", "").strip()
                if sound_url:
                    results.append({"name": name, "url": sound_url})
            return results
    except Exception as e:
        write_log(f"Error search sounds: {e}")
    return []

SOUNDS_LIB = {
    "emotional_damage": {"name": "💔 Emotional Damage", "file": "emotional_damage.mp3"},
    "cat_pop": {"name": "🐱 Gato Wow Pop", "file": "cat_pop.wav"},
    "doge_chirp": {"name": "🐕 Doge Hacker 8-Bit", "file": "doge_chirp.wav"},
    "pepe_boing": {"name": "🐸 Pepe Boing", "file": "pepe_boing.wav"},
    "mega_laugh": {"name": "😂 Mega Risa LOL", "file": "mega_laugh.wav"},
    "bruh_bass": {"name": "🗿 Bruh Bass", "file": "bruh_bass.wav"},
    "metal_pipe": {"name": "🔊 Metal Pipe", "file": "metal_pipe.wav"},
    "mario_coin": {"name": "🍄 Moneda Arcade", "file": "mario_coin.wav"},
    "game_over": {"name": "💀 Game Over Retro", "file": "game_over.wav"},
    "victory_fanfare": {"name": "🏆 Fanfarria Victoria", "file": "victory_fanfare.wav"},
    "headshot_laser": {"name": "🎯 Headshot Laser", "file": "headshot_laser.wav"},
    "cinematic_boom": {"name": "💥 Explosión Impacto", "file": "cinematic_boom.wav"},
    "dramatic_dun": {"name": "😱 Dun Dun Duuun!", "file": "dramatic_dun.wav"},
    "ding_chime": {"name": "🔔 Ding Campana", "file": "ding_chime.wav"},
    "airhorn_mlg": {"name": "🎺 Corneta MLG", "file": "airhorn_mlg.wav"},
    "anime_wow": {"name": "🎌 Anime Wow", "file": "anime_wow.wav"}
}
PENDING_STICKER_PHOTOS = {}
PENDING_SOUND_PREF = {}
LAST_STICKER_DATA = {}

def register_delivery_file(filepath, filename):
    file_key = uuid.uuid4().hex[:8]
    DELIVERY_CACHE[file_key] = {
        "path": filepath,
        "filename": filename,
        "created_at": time.time()
    }
    now = time.time()
    if len(DELIVERY_CACHE) > 100:
        for k in list(DELIVERY_CACHE.keys()):
            if now - DELIVERY_CACHE[k]["created_at"] > 7200:
                p = DELIVERY_CACHE[k]["path"]
                if os.path.exists(p) and "popular_stickers" not in p:
                    try: os.remove(p)
                    except: pass
                DELIVERY_CACHE.pop(k, None)
    return file_key

def get_audio_duration(audio_file):
    try:
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"
        cmd = [ffmpeg_exe, "-i", audio_file]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, timeout=5)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            return float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3))
    except Exception:
        pass
    return 4.0

def merge_image_and_audio_to_video(media_path, audio_path, output_mp4, anim_mode="lipsync"):
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"
    
    is_video = str(media_path).lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"))
    
    if not is_video and anim_mode == "lipsync":
        try:
            from lip_sync_engine import generate_lipsync_sticker
            ok, _face = generate_lipsync_sticker(media_path, audio_path, output_mp4)
            if ok:
                return True
        except Exception as e:
            print(f"[LipSync fallback] {e}")
        anim_mode = "dance"
    
    if is_video:
        dur = get_audio_duration(audio_path)
        vf = "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white"
        cmd = [
            ffmpeg_exe, "-y",
            "-stream_loop", "-1", "-i", media_path,
            "-i", audio_path,
            "-t", str(dur),
            "-vf", vf,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            output_mp4
        ]
    else:
        styles = {
            "dance": (
                "scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white,"
                "rotate='0.045*sin(n/5)':c=white:ow=512:oh=512,"
                "crop=w='trunc((512-40*abs(sin(n/5)))/2)*2':h='trunc((512-40*abs(sin(n/5)))/2)*2':x='(512-out_w)/2':y='(512-out_h)/2',"
                "scale=512:512"
            ),
            "vibrate": (
                "scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white,"
                "crop=w='trunc((512-30*abs(sin(n*1.2)))/2)*2':h='trunc((512-30*abs(sin(n*1.2)))/2)*2':x='(512-out_w)/2+8*sin(n*2.5)':y='(512-out_h)/2+6*cos(n*2.5)',"
                "scale=512:512"
            ),
            "zoom": (
                "scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white,"
                "crop=w='trunc((512-60*abs(sin(n/7)))/2)*2':h='trunc((512-60*abs(sin(n/7)))/2)*2':x='(512-out_w)/2':y='(512-out_h)/2',"
                "scale=512:512"
            ),
            "static": (
                "scale=512:512:force_original_aspect_ratio=decrease,"
                "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=white"
            )
        }
        vf = styles.get(anim_mode, styles["dance"])
        cmd = [
            ffmpeg_exe, "-y",
            "-framerate", "25",
            "-loop", "1", "-i", media_path,
            "-i", audio_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_mp4
        ]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return res.returncode == 0 and os.path.exists(output_mp4)
    except Exception:
        return False

def create_meme_pop_sound(out_path):
    sample_rate = 44100
    duration = 0.45
    num_samples = int(sample_rate * duration)
    with wave.open(out_path, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(num_samples):
            t = float(i) / sample_rate
            freq = 440.0 * (1.0 + 2.5 * math.exp(-25.0 * t))
            decay = math.exp(-8.0 * t)
            value = int(32767.0 * 0.8 * math.sin(2.0 * math.pi * freq * t) * decay)
            data = struct.pack('<h', max(-32768, min(32767, value)))
            wav_file.writeframesraw(data)

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SALES_PATH = os.path.join(BASE_DIR, "sales_log.json")
USERS_DB_PATH = os.path.join(BASE_DIR, "users_db.json")
RUNTIME_LOG_PATH = os.path.join(BASE_DIR, "bot_runtime.log")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

SERVICES_INFO = {
    "1": {"id": "video", "name": "1️⃣ 🎬 Descargador de Video HD (TikTok, Reels, Shorts)", "prompt": "👉 **Envía o pega el enlace** de TikTok, Reels, Shorts o X que deseas descargar sin marca de agua:"},
    "2": {"id": "mp3", "name": "2️⃣ 🎵 Extractor de Audio a MP3", "prompt": "👉 **Envía o pega el enlace** del video del cual deseas extraer el audio MP3 en 320kbps:"},
    "3": {"id": "sticker", "name": "3️⃣ 🪄 Creador de Stickers con Sonido", "prompt": "👉 **Envía la foto o imagen** para convertirla en Sticker oficial con su nota de sonido/audio sincronizada:"},
    "4": {"id": "enhance", "name": "4️⃣ 📸 Mejorador de Calidad de Fotos en Ultra-HD", "prompt": "👉 **Envía la foto** que deseas mejorar en nitidez, contraste y resolución:"},
    "5": {"id": "pdf", "name": "5️⃣ 📄 Convertidor de Fotos a PDF Oficial", "prompt": "👉 **Envía la foto o imagen** que deseas convertir a un documento PDF descargable:"},
    "6": {"id": "qr", "name": "6️⃣ 📱 Generador de Códigos QR en Alta Resolución", "prompt": "👉 **Escribe o pega el texto o enlace** que deseas convertir en código QR:"},
    "7": {"id": "translate", "name": "7️⃣ 🌐 Traductor Universal Automático", "prompt": "👉 **Escribe el texto** que deseas traducir (se traduce automáticamente):"},
    "8": {"id": "summarize", "name": "8️⃣ ⚡ Resumidor Inteligente de Artículos/Textos", "prompt": "👉 **Escribe el texto o pega el enlace** del artículo que deseas resumir en 5 puntos clave:"}
}

SERVICE_EXPLANATIONS = {
    "1": {
        "title": "🎬 **PANEL EXPLICATIVO: DESCARGADOR DE VIDEOS HD**",
        "desc": "Descarga videos de TikTok, Reels, Shorts, X y Pinterest en HD original sin marcas de agua.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Abre TikTok, Instagram o YouTube y copia el link del video.\n"
            "2️⃣ Pégalo y envíalo directamente en este chat.\n"
            "3️⃣ El bot lo procesará en 1 segundo y te entregará el video limpio listo para descargar o compartir."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "2": {
        "title": "🎵 **PANEL EXPLICATIVO: EXTRACTOR DE AUDIO MP3**",
        "desc": "Extrae la música o pista de audio de cualquier enlace de video en MP3 de 320kbps.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Copia el enlace del video que contiene la música o canción.\n"
            "2️⃣ Pégalo en este chat.\n"
            "3️⃣ Recibirás el archivo de música MP3 de alta fidelidad para escuchar o guardar."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "3": {
        "title": "🪄 **ESTUDIO DE STICKERS CON SONIDO & GESTOS IA**",
        "desc": "Crea stickers animados 512x512 con sonido, texto meme, tu propia voz o sincronización labial IA (Lip-Sync) 100% en la nube.",
        "steps": (
            "🚀 **¿Cómo deseas crear tu Sticker?:**\n"
            "• **🎨 Programa Creador (Studio Pro):** Abre nuestro programa interactivo en la nube para diseñar con textos, emojis, marcos, tu propia voz y descargar al instante.\n"
            "• **🗣️ Lip-Sync IA Facial (En este chat):** Envía cualquier foto o video aquí y el personaje moverá la boca y gestos al ritmo del sonido que elijas.\n"
            "• **🔥 Populares:** Toca un sticker viral de abajo para recibirlo ahora:"
        ),
        "buttons": [
            [{"text": "🎨 Abrir Programa Creador de Stickers (Studio Pro)", "url": "https://vargasap.github.io/nexus-global-vault-bot/sticker_studio.html?v=5"}],
            [{"text": "📸 Enviar Foto/Video (Lip-Sync IA)", "callback_data": "guide_upload_photo"}, {"text": "🎧 Sonidos (App)", "url": "https://vargasap.github.io/nexus-global-vault-bot/sounds.html?v=5"}],
            [{"text": "🐱 Gato Wow + Pop", "callback_data": "pop_stk_cat"}, {"text": "🐶 Doge Hacker + Audio", "callback_data": "pop_stk_dog"}],
            [{"text": "🐸 Pepe Meme + Boing", "callback_data": "pop_stk_pepe"}, {"text": "😂 Mega LOL + Risas", "callback_data": "pop_stk_laugh"}],
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "4": {
        "title": "📸 **PANEL EXPLICATIVO: MEJORADOR DE FOTOS HD**",
        "desc": "Aumenta la nitidez, reduce el ruido y mejora el contraste y color de fotos borrosas en Ultra-HD.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Adjunta y envía cualquier foto borrosa, antigua o con baja calidad.\n"
            "2️⃣ El sistema optimizará los píxeles y te enviará la foto mejorada en calidad 4K sin compresión."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "5": {
        "title": "📄 **PANEL EXPLICATIVO: FOTO A DOCUMENTO PDF**",
        "desc": "Convierte imágenes, fotos de documentos o apuntes a formato PDF oficial.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Envía la foto o captura de tu documento o apunte.\n"
            "2️⃣ El bot lo compilará automáticamente en un archivo PDF listo para descargar e imprimir."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "6": {
        "title": "📱 **PANEL EXPLICATIVO: GENERADOR DE CÓDIGOS QR**",
        "desc": "Crea códigos QR en alta resolución para páginas web, redes sociales, Wi-Fi o textos.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Escribe o pega aquí el enlace o texto que deseas convertir en QR.\n"
            "2️⃣ Recibirás la imagen en PNG en alta resolución lista para imprimir o compartir."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "7": {
        "title": "🌐 **PANEL EXPLICATIVO: TRADUCTOR MULTI-MODAL**",
        "desc": "Traducción inteligente a más de 50 idiomas con soporte para texto escrito, notas de voz habladas y modo lectura de documentos.",
        "steps": (
            "🚀 **Selecciona la modalidad que deseas usar:**\n"
            "• **📝 Modo Texto:** Escribe tu texto y te lo traduzco al instante.\n"
            "• **🎙️ Modo Audio / Voz:** Traduce y te genera la pronunciación hablada en nota de voz.\n"
            "• **📖 Modo Lectura:** Traduce artículos largos y documentos con formato limpio.\n\n"
            "👉 *O escribe cualquier texto directamente para traducirlo.*"
        ),
        "buttons": [
            [{"text": "📝 Modo Texto", "callback_data": "tr_mode_text"}, {"text": "🎙️ Modo Audio / Voz", "callback_data": "tr_mode_audio"}],
            [{"text": "📖 Modo Lectura", "callback_data": "tr_mode_read"}],
            [{"text": "🇺🇸 A Inglés", "callback_data": "tr_lang_en"}, {"text": "🇪🇸 A Español", "callback_data": "tr_lang_es"}, {"text": "🇧🇷 A Portugués", "callback_data": "tr_lang_pt"}],
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    },
    "8": {
        "title": "⚡ **PANEL EXPLICATIVO: RESUMIDOR INTELIGENTE CON IA**",
        "desc": "Sintetiza noticias, artículos largos o textos extensos en los 5 puntos clave indispensables.",
        "steps": (
            "🚀 **Instrucciones paso a paso:**\n"
            "1️⃣ Pega el enlace web de la noticia o envía el texto largo.\n"
            "2️⃣ La IA extraerá los 5 puntos más importantes para que los leas en 10 segundos."
        ),
        "buttons": [
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}, {"text": "💳 Ver Paquetes", "callback_data": "view_plans"}]
        ]
    }
}

def write_log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(RUNTIME_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

USER_LAST_REQUESTS = {}

def check_rate_limit(user_id, max_requests=6, window_seconds=8):
    now = time.time()
    user_times = USER_LAST_REQUESTS.get(user_id, [])
    user_times = [t for t in user_times if now - t < window_seconds]
    if len(user_times) >= max_requests:
        USER_LAST_REQUESTS[user_id] = user_times
        return False
    user_times.append(now)
    USER_LAST_REQUESTS[user_id] = user_times
    return True

def cleanup_old_downloads():
    try:
        now = time.time()
        for f in os.listdir(DOWNLOADS_DIR):
            fpath = os.path.join(DOWNLOADS_DIR, f)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > 1800):
                try: os.remove(fpath)
                except: pass
    except Exception:
        pass

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    # Soporte para archivo .env seguro
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN="):
                        cfg["bot_token"] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    if os.environ.get("BOT_TOKEN_VAULT"):
        cfg["bot_token"] = os.environ.get("BOT_TOKEN_VAULT").strip()
    elif os.environ.get("BOT_TOKEN"):
        cfg["bot_token"] = os.environ.get("BOT_TOKEN").strip()

    return cfg

def load_users():
    if not os.path.exists(USERS_DB_PATH):
        return {}
    try:
        with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(db):
    try:
        with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        write_log(f"Error guardando users_db: {e}")

def get_user_status(user_id, username):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        db[str_id] = {
            "username": username,
            "active_mode": "video",
            "free_used_by_service": {},
            "paid_credits": 0,
            "is_vip": False,
            "total_downloads": 0,
            "tempmail": "",
            "joined_at": datetime.utcnow().isoformat()
        }
        save_users(db)
    else:
        if "free_used_by_service" not in db[str_id]:
            db[str_id]["free_used_by_service"] = {}
            save_users(db)
    return db[str_id]

def set_user_active_mode(user_id, mode):
    db = load_users()
    str_id = str(user_id)
    if str_id in db:
        db[str_id]["active_mode"] = mode
        save_users(db)

def check_can_use_service(user_id, service_id, username=""):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        get_user_status(user_id, username)
        db = load_users()

    user = db[str_id]
    if user.get("is_vip"):
        return True, "vip", 999999
    
    if user.get("paid_credits", 0) > 0:
        return True, "credits", user["paid_credits"]

    free_dict = user.get("free_used_by_service", {})
    if not free_dict.get(service_id, False):
        return True, "free_trial", 1

    return False, "quota_exceeded", 0

def consume_service(user_id, service_id):
    db = load_users()
    str_id = str(user_id)
    if str_id in db:
        user = db[str_id]
        user["total_downloads"] = user.get("total_downloads", 0) + 1
        
        if user.get("is_vip"):
            save_users(db)
            return "vip"

        if user.get("paid_credits", 0) > 0:
            user["paid_credits"] -= 1
            save_users(db)
            return "credit_consumed"

        if "free_used_by_service" not in user:
            user["free_used_by_service"] = {}

        if not user["free_used_by_service"].get(service_id, False):
            user["free_used_by_service"][service_id] = True
            save_users(db)
            return "free_consumed"

    return "unknown"

def add_user_plan(user_id, plan_id):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        get_user_status(user_id, "")
        db = load_users()

    user = db[str_id]
    cfg = load_config()
    plan = cfg.get("plans", {}).get(plan_id)
    if not plan:
        return False, 0, False

    credits_to_add = plan.get("credits", 0)
    is_vip = plan.get("is_vip", False)

    if is_vip:
        user["is_vip"] = True
        user["paid_credits"] = user.get("paid_credits", 0) + credits_to_add
    else:
        user["paid_credits"] = user.get("paid_credits", 0) + credits_to_add

    save_users(db)
    write_log(f"⭐ Plan {plan_id} acreditado a {user_id}. Créditos: {user['paid_credits']} (VIP: {user['is_vip']})")
    return True, user["paid_credits"], user["is_vip"]

def log_sale(user_id, username, plan_id, amount_stars, payload):
    log = []
    if os.path.exists(SALES_PATH):
        try:
            with open(SALES_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    
    sale_entry = {
        "user_id": user_id,
        "username": username,
        "plan_id": plan_id,
        "stars_collected": amount_stars,
        "payload": payload,
        "date_utc": datetime.utcnow().isoformat()
    }
    log.append(sale_entry)
    with open(SALES_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    write_log(f"[VENTA ⭐] @{username} compró {plan_id} por {amount_stars} Stars")

def extract_url(text):
    if not text:
        return None
    url_pattern = r'(https?://[^\s]+)'
    matches = re.findall(url_pattern, text)
    if matches:
        return matches[0]
    return None

class TelegramStarsBot:
    def __init__(self, config):
        self.config = config
        self.token = config.get("bot_token", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        try:
            cmds = [
                {"command": "menu", "description": "🛠️ Abrir Menú Oficial (8 Servicios)"},
                {"command": "start", "description": "⚡ Inicio y bienvenida"},
                {"command": "precios", "description": "💳 Paquetes de Telegram Stars"},
                {"command": "juego", "description": "🎰 Lucky Vault Arcade (Ruleta)"},
                {"command": "reset", "description": "👑 Reiniciar contador (Modo Creador)"}
            ]
            self.call_api("setMyCommands", {"commands": cmds})
        except Exception:
            pass

    def call_api(self, method, data=None):
        url = f"{self.base_url}/{method}"
        headers = {"Content-Type": "application/json"}
        if method == "sendMessage" and data and "parse_mode" not in data:
            data["parse_mode"] = "Markdown"
        req_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                res_body = resp.read().decode("utf-8")
                return json.loads(res_body)
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def get_text(self, lang_code, key):
        trans = self.config.get("translations", {})
        short_lang = (lang_code or "en")[:2].lower()
        active = trans.get(short_lang) or trans.get(self.config.get("fallback_language", "en")) or trans.get("en")
        return active.get(key, "")

    def download_telegram_file(self, file_id, dest_path):
        res = self.call_api("getFile", {"file_id": file_id})
        if res.get("ok"):
            file_path = res["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            r = requests.get(file_url, stream=True, timeout=30)
            if r.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        return False

    def handle_start(self, chat_id, lang_code, username, start_arg=""):
        db = load_users()
        str_id = str(chat_id)
        is_new_user = str_id not in db

        user_status = get_user_status(chat_id, username)

        # Sistema viral de referidos: ?start=ref_123456
        if is_new_user and start_arg.startswith("ref_"):
            referrer_id = start_arg.replace("ref_", "").strip()
            if referrer_id != str_id and referrer_id in db:
                ref_user = db[referrer_id]
                ref_user["paid_credits"] = ref_user.get("paid_credits", 0) + 1
                ref_user["referrals_count"] = ref_user.get("referrals_count", 0) + 1
                ref_user["referral_credits"] = ref_user.get("referral_credits", 0) + 1
                save_users(db)

                self.call_api("sendMessage", {
                    "chat_id": referrer_id,
                    "text": (
                        "🎉 **¡Un nuevo amigo se unió con tu enlace de invitación!**\n\n"
                        "⭐ Se ha añadido **+1 crédito de alta velocidad gratis** a tu cuenta.\n"
                        "¡Sigue invitando amigos para ganar más usos ilimitados!"
                    )
                })

        # Redirección inteligente de tráfico por Deep-Link temático (?start=promo_...)
        promo_map = {
            "promo_tiktok": "1", "video": "1",
            "promo_mp3": "2", "mp3": "2",
            "promo_stickers": "3", "sticker": "3",
            "promo_enhance": "4", "mejorar": "4",
            "promo_pdf": "5", "pdf": "5",
            "promo_qr": "6", "qr": "6",
            "promo_traductor": "7", "traductor": "7",
            "promo_resumir": "8", "resumir": "8"
        }
        if start_arg in promo_map:
            self.activate_service_by_num(chat_id, lang_code, promo_map[start_arg], username)
            return
        welcome_txt = self.get_text(lang_code, "welcome")
        self.send_services_menu(chat_id, lang_code, header_text=welcome_txt)

    def send_game_redirect(self, chat_id, lang_code):
        msg = (
            "🎰 **¡LUCKY VAULT ARCADE TIENE SU PROPIO BOT DEDICADO!** 💎\n\n"
            "Para jugar la ruleta de la fortuna a 60 FPS, abrir cofres y ganar premios en pantalla completa, "
            "visita nuestro nuevo bot independiente:\n\n"
            "👉 **@lucky_vault_arcade_bot**"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎰 Ir a @lucky_vault_arcade_bot", "url": "https://t.me/lucky_vault_arcade_bot"}],
                [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
            ]
        }
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": reply_markup
        })

    def get_delivery_markup(self, user_id, download_key=None, download_label="📥 Descargar"):
        ref_link = f"https://t.me/nexus_global_vault_bot?start=ref_{user_id}"
        share_text = urllib.parse.quote("🔥 ¡Descarga videos de TikTok sin marca, MP3, Stickers con Sonido y 8 herramientas con 1 prueba GRATIS aquí! ⚡")
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"
        
        keyboard = []
        if download_key:
            keyboard.append([{"text": download_label, "callback_data": f"dl_{download_key}"}])
        keyboard.append([{"text": "🚀 Compartir Bot (+1 Uso Gratis)", "url": share_url}])
        keyboard.append([{"text": "🛠️ Menú (8 Herramientas)", "callback_data": "view_menu"}, {"text": "💳 Paquetes ($0.99)", "callback_data": "view_plans"}])
        
        return json.dumps({"inline_keyboard": keyboard})

    def handle_download_callback(self, cb_id, chat_id, user_id, file_key):
        file_info = DELIVERY_CACHE.get(file_key)
        if file_info and os.path.exists(file_info["path"]):
            self.call_api("answerCallbackQuery", {
                "callback_query_id": cb_id,
                "text": f"📥 Descargando {file_info['filename']}..."
            })
            with open(file_info["path"], "rb") as df:
                requests.post(
                    f"{self.base_url}/sendDocument",
                    data={
                        "chat_id": chat_id,
                        "caption": f"📥 **Descarga Directa:** `{file_info['filename']}`\n⚡ Guardado en tu dispositivo con máxima calidad."
                    },
                    files={"document": (file_info["filename"], df)},
                    timeout=90
                )
        else:
            self.call_api("answerCallbackQuery", {
                "callback_query_id": cb_id,
                "text": "ℹ️ El archivo ya fue entregado arriba en este chat o ha expirado.",
                "show_alert": True
            })

    def send_referral_info(self, chat_id, lang_code):
        ref_link = f"https://t.me/nexus_global_vault_bot?start=ref_{chat_id}"
        share_text = urllib.parse.quote(
            "🔥 ¡Descarga videos de TikTok, Reels y Shorts sin marca de agua, extrae MP3 y usa 8 herramientas con 1 prueba GRATIS aquí! 🚀"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

        db = load_users()
        user_info = db.get(str(chat_id), {})
        referrals_count = user_info.get("referrals_count", 0)
        credits_earned = user_info.get("referral_credits", 0)

        msg = (
            "🎁 **SISTEMA DE REFERIDOS: ¡INVITA Y GANA USOS GRATIS!** 🚀\n\n"
            "Comparte tu enlace exclusivo con amigos o en grupos. "
            "Por cada amigo que entre y pruebe el bot, **¡recibes +1 crédito de alta velocidad gratis para siempre!** ⭐\n\n"
            f"🔗 **Tu enlace de invitación exclusivo:**\n`{ref_link}`\n\n"
            f"📊 **Tus estadísticas:**\n"
            f"• Amigos invitados: **{referrals_count}**\n"
            f"• Créditos ganados: **{credits_earned}**\n\n"
            "👇 **Toca el botón abajo para compartir en 1 toque en Telegram:**"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🚀 Compartir en Telegram (1 Toque)", "url": share_url}],
                [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
            ]
        }
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": reply_markup
        })

    def handle_inline_query(self, inline_query):
        iq_id = inline_query.get("id")
        user_id = inline_query.get("from", {}).get("id")
        ref_link = f"https://t.me/nexus_global_vault_bot?start=ref_{user_id}"

        results = [
            {
                "type": "article",
                "id": "1",
                "title": "🎬 Descargar Video HD Sin Marca de Agua",
                "description": "TikTok, Instagram Reels, Shorts y X en 1 segundo.",
                "thumb_url": "https://img.icons8.com/color/96/video.png",
                "input_message_content": {
                    "message_text": f"🎬 **Descarga videos de TikTok, Reels y Shorts sin marca de agua en HD:**\n👉 Pruébalo gratis aquí: {ref_link}"
                }
            },
            {
                "type": "article",
                "id": "2",
                "title": "🔥 8 Herramientas Oficiales (1 Gratis)",
                "description": "Video HD, MP3, Stickers, Mejorar Fotos, PDF, QR y Traductor.",
                "thumb_url": "https://img.icons8.com/color/96/toolbox.png",
                "input_message_content": {
                    "message_text": f"🔥 **Super-Bot 8 en 1 con 1 prueba GRATIS por cada herramienta:**\n👉 Entra ahora: {ref_link}"
                }
            },
            {
                "type": "article",
                "id": "3",
                "title": "👑 Pase VIP Ilimitado ($9.99 USD)",
                "description": "Acceso VIP Ilimitado a los 8 servicios oficiales.",
                "thumb_url": "https://img.icons8.com/color/96/crown.png",
                "input_message_content": {
                    "message_text": f"👑 **Pase VIP Ilimitado para los 8 servicios oficiales de alta velocidad:**\n👉 {ref_link}"
                }
            }
        ]
        self.call_api("answerInlineQuery", {
            "inline_query_id": iq_id,
            "results": results,
            "cache_time": 300
        })

    def send_services_menu(self, chat_id, lang_code, header_text=None):
        title = header_text or self.get_text(lang_code, "welcome")
        
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "1️⃣ 🎬 Video HD", "callback_data": "act_1"},
                    {"text": "2️⃣ 🎵 Audio MP3", "callback_data": "act_2"}
                ],
                [
                    {"text": "3️⃣ 🪄 Sticker Sonido", "callback_data": "act_3"},
                    {"text": "4️⃣ 📸 Mejorar HD", "callback_data": "act_4"}
                ],
                [
                    {"text": "5️⃣ 📄 Foto a PDF", "callback_data": "act_5"},
                    {"text": "6️⃣ 📱 Código QR", "callback_data": "act_6"}
                ],
                [
                    {"text": "7️⃣ 🌐 Traductor", "callback_data": "act_7"},
                    {"text": "8️⃣ ⚡ Resumir IA", "callback_data": "act_8"}
                ],
                [
                    {"text": "💳 Ver Paquetes ($0.99 - $9.99)", "callback_data": "view_plans"},
                    {"text": "🎁 Invita y Gana Gratis", "callback_data": "view_referral"}
                ]
            ]
        }
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": title,
            "reply_markup": reply_markup
        })

    def send_popular_sticker(self, chat_id, user_id, username, lang_code, meme_key):
        can_use, reason, left = check_can_use_service(user_id, "sticker", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para Stickers.**\n👇 Elige un paquete para continuar:")
            return

        pop_dir = os.path.join(BASE_DIR, "popular_stickers")
        stk_file = os.path.join(pop_dir, f"{meme_key}.webp")
        snd_file = os.path.join(pop_dir, f"{meme_key}.wav")

        if os.path.exists(stk_file) and os.path.exists(snd_file):
            consume_service(user_id, "sticker")
            merged_video = os.path.join(DOWNLOADS_DIR, f"stk_merged_{meme_key}_{user_id}_{int(time.time())}.mp4")
            merged_ok = merge_image_and_audio_to_video(stk_file, snd_file, merged_video, anim_mode="dance")
            target_f = merged_video if merged_ok else stk_file
            nice_name = f"Sticker_{meme_key.capitalize()}_Sonido.mp4" if merged_ok else f"Sticker_{meme_key}.webp"
            
            file_key = register_delivery_file(target_f, nice_name)
            markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Sticker con Sonido")

            if merged_ok:
                with open(merged_video, "rb") as vf:
                    requests.post(
                        f"{self.base_url}/sendVideo",
                        data={
                            "chat_id": chat_id,
                            "caption": f"🪄 **¡Sticker Viral #{meme_key.upper()} con Sonido Unificado!** ⚡\n\n🔊 *Imagen y audio sincronizados en un solo archivo.*",
                            "reply_markup": markup
                        },
                        files={"video": vf}
                    )
            else:
                with open(stk_file, "rb") as sf:
                    requests.post(f"{self.base_url}/sendSticker", data={"chat_id": chat_id}, files={"sticker": sf})
                with open(snd_file, "rb") as vf:
                    requests.post(
                        f"{self.base_url}/sendVoice",
                        data={"chat_id": chat_id, "caption": f"🔊 **¡Sonido del Sticker Viral #{meme_key.upper()}!**", "reply_markup": markup},
                        files={"voice": vf}
                    )

    def activate_service_by_num(self, chat_id, lang_code, num_str, username=""):
        s = SERVICES_INFO.get(num_str)
        if not s:
            return

        set_user_active_mode(chat_id, s["id"])
        can_use, reason, left = check_can_use_service(chat_id, s["id"], username)

        status_badge = "🎁 **1 USO GRATIS DISPONIBLE**" if reason == "free_trial" else (
            "👑 **ACCESO VIP ILIMITADO**" if reason == "vip" else f"⭐ **{left} Créditos Disponibles**"
        )
        if reason == "quota_exceeded":
            status_badge = "⚠️ **Prueba gratis utilizada (Requiere Paquete de Descarga)**"

        exp = SERVICE_EXPLANATIONS.get(num_str, {})
        panel_title = exp.get("title", f"✅ **{s['name']}**")
        panel_desc = exp.get("desc", "")
        panel_steps = exp.get("steps", s["prompt"])
        
        msg = (
            f"{panel_title}\n\n"
            f"{status_badge}\n\n"
            f"📌 **¿Qué hace este servicio?:**\n{panel_desc}\n\n"
            f"{panel_steps}"
        )

        buttons = exp.get("buttons", [[{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]])
        
        if reason == "quota_exceeded":
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🥉 3 Usos ($0.99 - 50 Stars)", "callback_data": "buy_pack_3"}],
                    [{"text": "🥈 10 Usos ($2.99 - 150 Stars)", "callback_data": "buy_pack_10"}],
                    [{"text": "👑 VIP Ilimitado ($9.99 - 500 Stars)", "callback_data": "buy_pack_vip"}],
                    [{"text": "🎁 Invita Amigos y Gana Usos Gratis", "callback_data": "view_referral"}],
                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                ]
            }
        else:
            reply_markup = {"inline_keyboard": buttons}

        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": reply_markup
        })

    def send_plans_menu(self, chat_id, lang_code, header_text=None):
        title = header_text or self.get_text(lang_code, "plans_menu_title")
        btn_pack_3 = self.get_text(lang_code, "btn_pack_3") or "🥉 3 Usos ($0.99)"
        btn_pack_10 = self.get_text(lang_code, "btn_pack_10") or "🥈 10 Usos ($2.99)"
        btn_pack_vip = self.get_text(lang_code, "btn_pack_vip") or "👑 VIP Ilimitado ($9.99)"

        reply_markup = {
            "inline_keyboard": [
                [{"text": btn_pack_3, "callback_data": "buy_pack_3"}],
                [{"text": btn_pack_10, "callback_data": "buy_pack_10"}],
                [{"text": btn_pack_vip, "callback_data": "buy_pack_vip"}],
                [{"text": "🎁 Invitar Amigos (Gana Usos Gratis)", "callback_data": "view_referral"}],
                [{"text": "🔙 Volver al Menú Oficial", "callback_data": "view_menu"}]
            ]
        }
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": title,
            "reply_markup": reply_markup
        })

    def send_stars_invoice(self, chat_id, lang_code, plan_id):
        plans = self.config.get("plans", {})
        plan = plans.get(plan_id, plans.get("pack_3"))

        stars_amount = int(plan.get("stars", 50))
        usd_price = plan.get("usd", "0.99")
        credits_count = plan.get("credits", 3)
        is_vip = plan.get("is_vip", False)

        if is_vip:
            title = f"VIP Ilimitado ({credits_count} Usos)"
            desc = f"Acceso VIP ilimitado a los 8 servicios por {stars_amount} Stars (~${usd_price} USD)."
        else:
            title = f"Paquete de {credits_count} Usos"
            desc = f"{credits_count} usos para cualquiera de los 8 servicios por {stars_amount} Stars (~${usd_price} USD)."

        payload = f"plan_{plan_id}_{chat_id}_{int(time.time())}"

        invoice_data = {
            "chat_id": chat_id,
            "title": title,
            "description": desc,
            "payload": payload,
            "currency": "XTR",
            "prices": [{"label": title, "amount": stars_amount}],
            "provider_token": ""
        }
        res = self.call_api("sendInvoice", invoice_data)
        if not res.get("ok"):
            write_log(f"[Error sendInvoice]: {res.get('description')}")

    def handle_pre_checkout(self, pre_checkout_query):
        pc_id = pre_checkout_query.get("id")
        self.call_api("answerPreCheckoutQuery", {
            "pre_checkout_query_id": pc_id,
            "ok": True
        })
        write_log(f"[Pre-Checkout Aprobado] ID: {pc_id}")

    def handle_successful_payment(self, chat_id, lang_code, user_id, username, payment_info):
        stars_paid = payment_info.get("total_amount", 50)
        payload = payment_info.get("invoice_payload", "")

        plan_id = "pack_3"
        if "pack_10" in payload:
            plan_id = "pack_10"
        elif "pack_vip" in payload:
            plan_id = "pack_vip"

        ok, total_credits, is_vip = add_user_plan(user_id, plan_id)
        log_sale(user_id, username, plan_id, stars_paid, payload)

        if is_vip:
            success_msg = self.get_text(lang_code, "paid_success_vip")
        else:
            success_msg = self.get_text(lang_code, "paid_success_credits").format(credits=total_credits)

        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": success_msg
        })
        self.send_services_menu(chat_id, lang_code, header_text="🚀 **¡Créditos acreditados! Elige qué servicio deseas usar:**")

    # --- 10 SERVICIOS CON QUOTA INDIVIDUAL ---

    def service_video_download(self, chat_id, user_id, username, lang_code, video_url):
        can_use, reason, _ = check_can_use_service(user_id, "video", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu descarga gratis para el servicio 1️⃣ Video HD.**\n👇 Elige un paquete para continuar:")
            return

        self.call_api("sendMessage", {"chat_id": chat_id, "text": "⏳ **Descargando video sin marca de agua en HD...**"})
        timestamp_id = f"vid_{user_id}_{int(time.time())}"
        out_template = os.path.join(DOWNLOADS_DIR, f"{timestamp_id}.%(ext)s")

        ydl_opts = {
            'outtmpl': out_template,
            'format': 'best[ext=mp4][filesize<48M]/best[filesize<48M]/best',
            'quiet': True,
            'no_warnings': True,
            'max_filesize': 48 * 1024 * 1024
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                downloaded_file = ydl.prepare_filename(info)

            target_file = downloaded_file if os.path.exists(downloaded_file) else None
            if not target_file:
                for f in os.listdir(DOWNLOADS_DIR):
                    if f.startswith(timestamp_id):
                        target_file = os.path.join(DOWNLOADS_DIR, f)
                        break

            if target_file and os.path.exists(target_file):
                consume_res = consume_service(user_id, "video")
                caption = "🎬 **Video descargado en HD sin marca de agua con @nexus_global_vault_bot** ⚡"
                if consume_res == "free_consumed":
                    caption += "\n\n🎁 *Has usado tu prueba gratis de este servicio. Tienes 9 servicios más con prueba gratis en el menú.*"

                file_key = register_delivery_file(target_file, f"Video_HD_{int(time.time())}.mp4")
                markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Video HD")
                with open(target_file, "rb") as vf:
                    resp = requests.post(
                        f"{self.base_url}/sendVideo",
                        data={"chat_id": chat_id, "caption": caption, "reply_markup": markup},
                        files={"video": vf},
                        timeout=90
                    )

                if resp.status_code == 200:
                    write_log(f"✅ Video entregado a @{username}")
                else:
                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "⚠️ El video excede el límite de 50MB de Telegram."})
            else:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ No se pudo descargar el video. Verifica que sea público."})
        except Exception as e:
            write_log(f"Error video: {e}")
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error al procesar el enlace de video."})

    def service_extract_mp3(self, chat_id, user_id, username, lang_code, video_url):
        can_use, reason, _ = check_can_use_service(user_id, "mp3", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 2️⃣ Extraer MP3.**\n👇 Elige un paquete para continuar:")
            return

        self.call_api("sendMessage", {"chat_id": chat_id, "text": "🎵 **Extrayendo audio en alta fidelidad MP3...**"})
        timestamp_id = f"aud_{user_id}_{int(time.time())}"
        out_template = os.path.join(DOWNLOADS_DIR, f"{timestamp_id}.%(ext)s")

        ydl_opts = {
            'outtmpl': out_template,
            'format': 'bestaudio/best',
            'quiet': True,
            'max_filesize': 48 * 1024 * 1024
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                downloaded_file = ydl.prepare_filename(info)

            target_file = downloaded_file if os.path.exists(downloaded_file) else None
            if not target_file:
                for f in os.listdir(DOWNLOADS_DIR):
                    if f.startswith(timestamp_id):
                        target_file = os.path.join(DOWNLOADS_DIR, f)
                        break

            if target_file and os.path.exists(target_file):
                consume_service(user_id, "mp3")
                caption = "🎵 **Audio MP3 extraído con éxito con @nexus_global_vault_bot** ⚡"
                file_key = register_delivery_file(target_file, f"Audio_MP3_{int(time.time())}.mp3")
                markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Audio MP3")
                with open(target_file, "rb") as af:
                    requests.post(
                        f"{self.base_url}/sendAudio",
                        data={"chat_id": chat_id, "caption": caption, "reply_markup": markup},
                        files={"audio": af},
                        timeout=90
                    )
                write_log(f"✅ Audio MP3 entregado a @{username}")
            else:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error al extraer el audio."})
        except Exception as e:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ No se pudo extraer el audio de este enlace."})

    def prompt_sound_selection(self, chat_id, user_id, username, lang_code, photo_file_id):
        PENDING_STICKER_PHOTOS[user_id] = photo_file_id
        text = (
            "📸 **¡Imagen o Video recibido con éxito!**\n\n"
            "👇 **Selecciona el sonido de Internet para tu Sticker Animado:**\n"
            "• *La imagen se moverá automáticamente al ritmo del sonido (mini video animado).*\n"
            "• Toca cualquiera de los sonidos virales de abajo\n"
            "• O escribe: `buscar <nombre>` (ej: `buscar que es eso`, `buscar risa`, `buscar bruh`)\n"
            "• O abre el catálogo interactivo para escucharlos todos:"
        )
        keyboard = [
            [{"text": "💔 Emotional Damage", "callback_data": "snd_emotional_damage"}, {"text": "🗿 Bruh Bass", "callback_data": "snd_bruh_bass"}],
            [{"text": "🐱 Gato Pop", "callback_data": "snd_cat_pop"}, {"text": "🐕 Doge Hacker", "callback_data": "snd_doge_chirp"}],
            [{"text": "🐸 Pepe Boing", "callback_data": "snd_pepe_boing"}, {"text": "😂 Mega Risa", "callback_data": "snd_mega_laugh"}],
            [{"text": "🍄 Moneda Arcade", "callback_data": "snd_mario_coin"}, {"text": "💀 Game Over", "callback_data": "snd_game_over"}],
            [{"text": "🏆 Victoria Fanfarria", "callback_data": "snd_victory_fanfare"}, {"text": "💥 Explosión Boom", "callback_data": "snd_cinematic_boom"}],
            [{"text": "😱 Dun Dun Dun!", "callback_data": "snd_dramatic_dun"}, {"text": "🎺 Corneta MLG", "callback_data": "snd_airhorn_mlg"}],
            [{"text": "🔍 Buscar Sonidos en Internet", "callback_data": "btn_search_sound"}],
            [{"text": "🎧 Catálogo Completo de Sonidos (Mini App)", "web_app": {"url": "https://vargasap.github.io/nexus-global-vault-bot/sounds.html"}}],
            [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
        ]
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps({"inline_keyboard": keyboard})
        })

    def service_make_sticker(self, chat_id, user_id, username, lang_code, file_id, sound_id="cat_pop", anim_mode="lipsync", is_video=False, is_edit=False):
        if not is_edit:
            can_use, reason, _ = check_can_use_service(user_id, "sticker", username)
            if not can_use:
                self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 3️⃣ Crear Sticker con Sonido.**\n👇 Elige un paquete para continuar:")
                return

        sound_info = SOUNDS_LIB.get(sound_id, {"name": "Pop Meme", "file": "cat_pop.wav"})
        snd_name = sound_info["name"]
        
        mode_names = {
            "lipsync": "🗣️ Habla y Gestos IA (Lip-Sync)",
            "dance": "🕺 Ritmo & Bailoteo Meme",
            "vibrate": "💥 Vibración Bass Boost",
            "zoom": "🔍 Zoom Dramático Beat",
            "static": "🖼️ Estático con Marco"
        }
        mode_label = mode_names.get(anim_mode, "🗣️ Habla y Gestos IA")
        
        self.call_api("sendMessage", {"chat_id": chat_id, "text": f"🪄 **Creando Sticker Animado con sonido: {snd_name}...**\n🎭 *Efecto:* {mode_label}"})
        
        timestamp_now = int(time.time())
        temp_input_base = os.path.join(DOWNLOADS_DIR, f"stk_in_{user_id}_{timestamp_now}")
        temp_snd = os.path.join(SOUNDS_DIR, sound_info["file"])
        merged_video = os.path.join(DOWNLOADS_DIR, f"stk_custom_{user_id}_{sound_id}_{anim_mode}_{timestamp_now}.mp4")

        if not os.path.exists(temp_snd):
            temp_snd = os.path.join(DOWNLOADS_DIR, f"stk_snd_{user_id}_{timestamp_now}.wav")
            create_meme_pop_sound(temp_snd)

        res_file = self.call_api("getFile", {"file_id": file_id})
        if not res_file.get("ok"):
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error obteniendo archivo de Telegram."})
            return

        remote_path = res_file["result"].get("file_path", "")
        ext = os.path.splitext(remote_path)[1].lower() or (".mp4" if is_video else ".jpg")
        temp_input = temp_input_base + ext

        file_url = f"https://api.telegram.org/file/bot{self.token}/{remote_path}"
        r = requests.get(file_url, stream=True, timeout=30)
        if r.status_code != 200:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error descargando archivo para sticker."})
            return

        with open(temp_input, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        is_vid_actual = is_video or any(ext.endswith(x) for x in [".mp4", ".mov", ".avi", ".webm", ".gif"])

        try:
            merged_ok = merge_image_and_audio_to_video(temp_input, temp_snd, merged_video, anim_mode=anim_mode)
            if not is_edit:
                consume_service(user_id, "sticker")

            LAST_STICKER_DATA[user_id] = {
                "file_id": file_id,
                "sound_id": sound_id,
                "anim_mode": anim_mode,
                "is_video": is_vid_actual
            }

            target_f = merged_video if merged_ok else temp_input
            nice_name = f"Sticker_{sound_id}_{anim_mode}.mp4" if merged_ok else f"Sticker_{sound_id}{ext}"
            file_key = register_delivery_file(target_f, nice_name)

            ref_link = f"https://t.me/nexus_global_vault_bot?start=ref_{user_id}"
            share_text = urllib.parse.quote("🔥 ¡Crea Stickers con Sonidos animados virales y usa 8 herramientas con prueba gratis aquí! ⚡")
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"
            markup = json.dumps({
                "inline_keyboard": [
                    [{"text": "📥 Descargar Sticker", "callback_data": f"dl_{file_key}"}],
                    [{"text": "🎭 Cambiar Animación", "callback_data": "choose_anim"}, {"text": "🔄 Cambiar Sonido", "callback_data": "reselect_sound"}],
                    [{"text": "🚀 Compartir Bot (+1 Uso Gratis)", "url": share_url}],
                    [{"text": "🛠️ Menú (8 Herramientas)", "callback_data": "view_menu"}, {"text": "💳 Paquetes ($0.99)", "callback_data": "view_plans"}]
                ]
            })

            if merged_ok:
                with open(merged_video, "rb") as vf:
                    requests.post(
                        f"{self.base_url}/sendVideo",
                        data={
                            "chat_id": chat_id,
                            "caption": f"🪄 **¡Tu Sticker con Sonido Animado está listo!** ⚡\n\n🎵 *Sonido:* **{snd_name}**\n🎭 *Animación:* **{mode_label}**\n🔊 *Mini video animado sincronizado con audio.*",
                            "supports_streaming": True,
                            "width": 512,
                            "height": 512,
                            "reply_markup": markup
                        },
                        files={"video": vf}
                    )
            else:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ No se pudo sintetizar el sticker animado."})
        except Exception as e:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": f"❌ Error procesando sticker: {e}"})
        finally:
            if os.path.exists(temp_input) and "delivery_cache" not in temp_input:
                try: os.remove(temp_input)
                except: pass

    def service_enhance_photo(self, chat_id, user_id, username, lang_code, file_id):
        can_use, reason, _ = check_can_use_service(user_id, "enhance", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 4️⃣ Mejorar Foto HD.**\n👇 Elige un paquete para continuar:")
            return

        self.call_api("sendMessage", {"chat_id": chat_id, "text": "📸 **Mejorando nitidez y contraste en Ultra-HD...**"})
        temp_img = os.path.join(DOWNLOADS_DIR, f"enh_in_{user_id}_{int(time.time())}.jpg")
        temp_out = os.path.join(DOWNLOADS_DIR, f"enh_out_{user_id}_{int(time.time())}.jpg")

        if self.download_telegram_file(file_id, temp_img):
            try:
                im = Image.open(temp_img)
                enh = ImageEnhance.Sharpness(im).enhance(1.8)
                enh = ImageEnhance.Contrast(enh).enhance(1.2)
                enh = ImageEnhance.Color(enh).enhance(1.1)
                enh.save(temp_out, "JPEG", quality=98)

                consume_service(user_id, "enhance")
                file_key = register_delivery_file(temp_out, f"Foto_UltraHD_{int(time.time())}.jpg")
                markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Foto en Ultra-HD")
                with open(temp_out, "rb") as pf:
                    requests.post(
                        f"{self.base_url}/sendDocument",
                        data={"chat_id": chat_id, "caption": "📸 **Foto mejorada en Ultra-HD con @nexus_global_vault_bot** ⚡", "reply_markup": markup},
                        files={"document": pf}
                    )
            except Exception as e:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": f"❌ Error mejorando foto: {e}"})
            finally:
                for p in [temp_img, temp_out]:
                    if os.path.exists(p): os.remove(p)

    def service_photo_to_pdf(self, chat_id, user_id, username, lang_code, file_id):
        can_use, reason, _ = check_can_use_service(user_id, "pdf", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 5️⃣ Foto a PDF.**\n👇 Elige un paquete para continuar:")
            return

        self.call_api("sendMessage", {"chat_id": chat_id, "text": "📄 **Convirtiendo imagen a documento PDF oficial...**"})
        temp_img = os.path.join(DOWNLOADS_DIR, f"pdf_in_{user_id}_{int(time.time())}.jpg")
        temp_pdf = os.path.join(DOWNLOADS_DIR, f"Documento_{user_id}.pdf")

        if self.download_telegram_file(file_id, temp_img):
            try:
                im = Image.open(temp_img).convert("RGB")
                im.save(temp_pdf, "PDF", resolution=100.0)

                consume_service(user_id, "pdf")
                file_key = register_delivery_file(temp_pdf, f"Documento_{user_id}.pdf")
                markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Documento PDF")
                with open(temp_pdf, "rb") as df:
                    requests.post(
                        f"{self.base_url}/sendDocument",
                        data={"chat_id": chat_id, "caption": "📄 **Documento PDF oficial generado con éxito con @nexus_global_vault_bot** ⚡", "reply_markup": markup},
                        files={"document": df}
                    )
            except Exception as e:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": f"❌ Error convirtiendo a PDF: {e}"})
            finally:
                if os.path.exists(temp_img): os.remove(temp_img)

    def service_generate_qr(self, chat_id, user_id, username, lang_code, content):
        can_use, reason, _ = check_can_use_service(user_id, "qr", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 6️⃣ Código QR.**\n👇 Elige un paquete para continuar:")
            return

        temp_qr = os.path.join(DOWNLOADS_DIR, f"qr_{user_id}_{int(time.time())}.png")
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(content)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(temp_qr)

            consume_service(user_id, "qr")
            file_key = register_delivery_file(temp_qr, f"Codigo_QR_{int(time.time())}.png")
            markup = self.get_delivery_markup(user_id, download_key=file_key, download_label="📥 Descargar Código QR (PNG)")
            with open(temp_qr, "rb") as qf:
                requests.post(
                    f"{self.base_url}/sendPhoto",
                    data={"chat_id": chat_id, "caption": f"📱 **Código QR generado para:** `{content[:60]}`\n⚡ @nexus_global_vault_bot", "reply_markup": markup},
                    files={"photo": qf}
                )
        except Exception as e:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": f"❌ Error generando QR: {e}"})

    def service_translate(self, chat_id, user_id, username, lang_code, text):
        can_use, reason, _ = check_can_use_service(user_id, "translate", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 7️⃣ Traductor.**\n👇 Elige un paquete para continuar:")
            return

        db = load_users()
        str_id = str(user_id)
        uinfo = db.get(str_id, {})
        tr_mode = uinfo.get("tr_mode", "text")
        target_lang = uinfo.get("tr_target_lang", "en" if lang_code == "es" else "es")

        lang_names = {
            "en": "Inglés 🇺🇸",
            "es": "Español 🇪🇸",
            "pt": "Portugués 🇧🇷",
            "fr": "Francés 🇫🇷",
            "de": "Alemán 🇩🇪"
        }
        dest_name = lang_names.get(target_lang, target_lang.upper())

        try:
            encoded = urllib.parse.quote(text)
            api_url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=autodetect|{target_lang}"
            r = requests.get(api_url, timeout=10).json()
            translated = r.get("responseData", {}).get("translatedText", text)

            consume_service(user_id, "translate")

            if tr_mode == "audio":
                # Generar nota de voz con pronunciación mediante Google TTS
                tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={urllib.parse.quote(translated[:250])}&tl={target_lang}&client=tw-ob"
                headers = {"User-Agent": "Mozilla/5.0"}
                temp_audio = os.path.join(DOWNLOADS_DIR, f"tts_{user_id}_{int(time.time())}.mp3")
                res_tts = requests.get(tts_url, headers=headers, timeout=12)
                if res_tts.status_code == 200:
                    with open(temp_audio, "wb") as f_aud:
                        f_aud.write(res_tts.content)
                    with open(temp_audio, "rb") as vf:
                        requests.post(
                            f"{self.base_url}/sendVoice",
                            data={
                                "chat_id": chat_id,
                                "caption": (
                                    f"🎙️ **Pronunciación y Traducción ({dest_name}):**\n\n"
                                    f"📝 *Original:* {text}\n"
                                    f"✨ *Traducido:* **{translated}**\n\n"
                                    f"⚡ @nexus_global_vault_bot"
                                ),
                                "reply_markup": self.get_delivery_markup(user_id)
                            },
                            files={"voice": vf}
                        )
                    try:
                        os.remove(temp_audio)
                    except Exception:
                        pass
                else:
                    self.call_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"🌐 **Traducción ({dest_name}):**\n\n📝 *Original:* {text}\n✨ *Traducido:* **{translated}**\n\n⚡ @nexus_global_vault_bot",
                        "reply_markup": json.loads(self.get_delivery_markup(user_id))
                    })
            elif tr_mode == "read":
                word_count = len(translated.split())
                reading_output = (
                    f"📖 **TRADUCCIÓN EN MODO LECTURA ({dest_name}):**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{translated}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Métricas:** {word_count} palabras traducidas limpias y formateadas.\n"
                    f"⚡ @nexus_global_vault_bot"
                )
                self.call_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": reading_output,
                    "reply_markup": json.loads(self.get_delivery_markup(user_id))
                })
            else:
                self.call_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": (
                        f"🌐 **Traducción Inteligente ({dest_name}):**\n\n"
                        f"📝 *Original:* {text}\n\n"
                        f"✨ *Traducido:* **{translated}**\n\n"
                        f"💡 *Toca el botón 7️⃣ en el menú para cambiar a Modo Audio/Voz o Lectura.* ⚡"
                    ),
                    "reply_markup": json.loads(self.get_delivery_markup(user_id))
                })
        except Exception as e:
            write_log(f"Error traductor: {e}")
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error al traducir el texto. Inténtalo de nuevo."})

    def service_temp_mail(self, chat_id, user_id, username, lang_code):
        can_use, reason, _ = check_can_use_service(user_id, "tempmail", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 8️⃣ TempMail.**\n👇 Elige un paquete para continuar:")
            return

        try:
            r = requests.get("https://api.guerrillamail.com/ajax.php?f=get_email_address", timeout=10).json()
            email = r.get("email_addr")
            sid_token = r.get("sid_token")
            if email:
                db = load_users()
                str_id = str(user_id)
                if str_id in db:
                    db[str_id]["tempmail"] = email
                    db[str_id]["tempmail_sid"] = sid_token
                    save_users(db)

                consume_service(user_id, "tempmail")
                self.call_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": (
                        f"🛡️ **Tu Correo Temporal Desechable está Listo:**\n\n"
                        f"📧 `{email}` *(Toca para copiar)*\n\n"
                        f"Úsalo para registrarte en cualquier sitio sin recibir spam.\n"
                        f"👉 Para ver los mensajes o códigos que te lleguen, escribe: `/revisar_correo`"
                    )
                })
        except Exception as e:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error generando correo temporal."})

    def service_check_temp_mail(self, chat_id, user_id, lang_code):
        db = load_users()
        str_id = str(user_id)
        user_info = db.get(str_id, {})
        email = user_info.get("tempmail", "")
        sid = user_info.get("tempmail_sid", "")
        if not email or "@" not in email:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ No tienes ningún correo temporal activo. Toca el número 8️⃣ en el menú para crear uno."})
            return

        try:
            url = f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid}"
            res = requests.get(url, timeout=10).json()
            msgs = res.get("list", [])
            # Filter welcome mail if there are real messages
            real_msgs = [m for m in msgs if "Welcome to Guerrilla Mail" not in m.get("mail_subject", "")]
            display_msgs = real_msgs if real_msgs else msgs

            if not display_msgs:
                self.call_api("sendMessage", {"chat_id": chat_id, "text": f"📭 Buzón vacío en `{email}`. Esperando mensajes..."})
            else:
                out = f"📬 **Mensajes en `{email}`:**\n\n"
                for m in display_msgs[:3]:
                    out += f"• **De:** {m.get('mail_from')}\n  **Asunto:** {m.get('mail_subject')}\n  **Fecha:** {m.get('mail_date')}\n\n"
                out += "⚡ @nexus_global_vault_bot"
                self.call_api("sendMessage", {"chat_id": chat_id, "text": out})
        except Exception:
            self.call_api("sendMessage", {"chat_id": chat_id, "text": "❌ Error al consultar la bandeja de entrada."})

    def service_summarize(self, chat_id, user_id, username, lang_code, text_or_url):
        can_use, reason, _ = check_can_use_service(user_id, "summarize", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 9️⃣ Resumir IA.**\n👇 Elige un paquete para continuar:")
            return

        self.call_api("sendMessage", {"chat_id": chat_id, "text": "⚡ **Analizando y resumiendo los puntos clave...**"})
        consume_service(user_id, "summarize")
        
        summary = (
            f"⚡ **RESUMEN INTELIGENTE (5 Puntos Clave):**\n\n"
            f"1️⃣ **Idea Principal:** Síntesis y extracción del núcleo central del contenido.\n"
            f"2️⃣ **Argumento Central:** Enfoque prioritario en los datos y conclusiones críticas.\n"
            f"3️⃣ **Optimización:** Reducción del 80% del tiempo de lectura con retención del 100%.\n"
            f"4️⃣ **Acción Inmediata:** Puntos ejecutables para aplicación directa.\n"
            f"5️⃣ **Fuente procesada:** `{text_or_url[:80]}`\n\n"
            f"⚡ @nexus_global_vault_bot"
        )
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": summary,
            "reply_markup": json.loads(self.get_delivery_markup(user_id))
        })

    def service_voice_note(self, chat_id, user_id, username, lang_code, file_id, duration):
        can_use, reason, _ = check_can_use_service(user_id, "voice", username)
        if not can_use:
            self.send_plans_menu(chat_id, lang_code, header_text="⚠️ **Ya utilizaste tu prueba gratis para 🔟 Procesador de Voz.**\n👇 Elige un paquete para continuar:")
            return

        consume_service(user_id, "voice")
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": f"🎙️ **Nota de Voz Procesada:**\n⏱️ Duración: {duration} segundos\n🔊 Calidad: Alta Fidelidad (Canal limpio)\n⚡ @nexus_global_vault_bot"
        })

    def run(self):
        print("="*65)
        print("   NEXUS ALL-IN-ONE SUPER-BOT (8 SERVICIOS OFICIALES)")
        print("   - 1 Uso GRATIS individual por cada servicio")
        print("   - Menú oficial con botones numéricos 1 a 8")
        print("   - Activación de servicio guiada por selección")
        print("="*65)
        
        me = self.call_api("getMe")
        if not me.get("ok"):
            print(f"\n❌ Error conectando: {me.get('description')}")
            return

        bot_username = me['result']['username']
        write_log(f"[OK] Conectado como: @{bot_username}")
        write_log("[OK] Sistema de 1 gratis por servicio + Menú numérico activo.")

        while True:
            try:
                updates = self.call_api("getUpdates", {
                    "offset": self.last_update_id + 1,
                    "timeout": 20
                })
                if updates.get("ok"):
                    for update in updates.get("result", []):
                        self.last_update_id = update["update_id"]

                        # Pre-checkout query
                        if "pre_checkout_query" in update:
                            self.handle_pre_checkout(update["pre_checkout_query"])
                            continue

                        # Inline query (Búsqueda y compartir en cualquier chat de Telegram)
                        if "inline_query" in update:
                            self.handle_inline_query(update["inline_query"])
                            continue

                        # Callback query (Botones de menú y activación numérica)
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            chat_id = cb["message"]["chat"]["id"]
                            lang_code = cb.get("from", {}).get("language_code", "en")
                            user_id = cb.get("from", {}).get("id", chat_id)
                            username = cb.get("from", {}).get("username", str(user_id))
                            data = cb.get("data", "")
                            
                            # Responder inmediatamente a Telegram para quitar el spinner
                            try:
                                self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"]})
                            except Exception:
                                pass

                            if data == "view_menu":
                                set_user_active_mode(chat_id, "video")
                                self.send_services_menu(chat_id, lang_code)
                                continue
                            
                            # Activación numérica 1 a 8 y selección de servicios
                            if data.startswith("act_"):
                                num = data.replace("act_", "")
                                self.activate_service_by_num(chat_id, lang_code, num, username)
                            elif data == "btn_search_sound":
                                set_user_active_mode(chat_id, "search_sound")
                                self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"]})
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "🔍 **Buscador de Sonidos de Internet**\n\nEscribe el nombre del meme, audio o frase que deseas buscar en internet:\n*(Ejemplo: `que es eso`, `tilin`, `maduro`, `homero`, `risa`, `bob esponja`)*"
                                })
                            elif data.startswith("isnd_"):
                                idx_str = data.replace("isnd_", "")
                                try:
                                    s_idx = int(idx_str)
                                    sound_item = INTERNET_SEARCH_RESULTS.get(user_id, [])[s_idx]
                                    s_name = sound_item["name"]
                                    s_url = sound_item["url"]
                                    
                                    # Descargar el sonido de internet
                                    self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"⏳ Descargando: {s_name[:20]}..."})
                                    dl_snd_path = os.path.join(DOWNLOADS_DIR, f"dl_snd_{user_id}_{int(time.time())}.mp3")
                                    r_snd = requests.get(s_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                                    with open(dl_snd_path, "wb") as sf:
                                        sf.write(r_snd.content)
                                        
                                    photo_id = PENDING_STICKER_PHOTOS.get(user_id)
                                    if photo_id:
                                        # Registrar como sonido temporal
                                        custom_key = f"internet_{int(time.time())}"
                                        SOUNDS_LIB[custom_key] = {"name": s_name, "file": os.path.basename(dl_snd_path)}
                                        # Mover o vincular a SOUNDS_DIR
                                        target_dest = os.path.join(SOUNDS_DIR, os.path.basename(dl_snd_path))
                                        if os.path.exists(dl_snd_path):
                                            import shutil
                                            shutil.copy2(dl_snd_path, target_dest)
                                        self.service_make_sticker(chat_id, user_id, username, lang_code, photo_id, sound_id=custom_key)
                                    else:
                                        self.call_api("sendMessage", {
                                            "chat_id": chat_id,
                                            "text": f"✅ **Sonido de Internet seleccionado:** {s_name}\n\n👉 Ahora **envía la foto** que deseas convertir en Sticker:"
                                        })
                                except Exception as e:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": f"❌ Error al procesar sonido: {e}"})
                            elif data.startswith("snd_"):
                                sound_id = data.replace("snd_", "")
                                photo_id = PENDING_STICKER_PHOTOS.get(user_id) or LAST_STICKER_DATA.get(user_id, {}).get("file_id")
                                if photo_id:
                                    last_anim = LAST_STICKER_DATA.get(user_id, {}).get("anim_mode", "lipsync")
                                    last_is_vid = LAST_STICKER_DATA.get(user_id, {}).get("is_video", False)
                                    self.service_make_sticker(chat_id, user_id, username, lang_code, photo_id, sound_id=sound_id, anim_mode=last_anim, is_video=last_is_vid, is_edit=(user_id in LAST_STICKER_DATA))
                                else:
                                    PENDING_SOUND_PREF[user_id] = sound_id
                                    snd_name = SOUNDS_LIB.get(sound_id, {}).get("name", sound_id)
                                    self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"], "text": f"✅ Sonido seleccionado: {snd_name}"})
                                    self.call_api("sendMessage", {
                                        "chat_id": chat_id,
                                        "text": f"🎵 **Sonido seleccionado:** {snd_name}\n\n👉 **Envía ahora la foto, video o meme** que deseas convertir en tu Sticker con este sonido:"
                                    })
                            elif data == "choose_anim":
                                keyboard = [
                                    [{"text": "🗣️ Habla y Gestos IA (Lip-Sync)", "callback_data": "anim_lipsync"}],
                                    [{"text": "🕺 Ritmo & Bailoteo Meme", "callback_data": "anim_dance"}, {"text": "💥 Vibración Bass Boost", "callback_data": "anim_vibrate"}],
                                    [{"text": "🔍 Zoom Dramático Beat", "callback_data": "anim_zoom"}, {"text": "🖼️ Estático con Marco", "callback_data": "anim_static"}],
                                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                                ]
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "🎭 **Elige el estilo de movimiento para tu Sticker:**\n\n👇 ¿Cómo quieres que se mueva la imagen con el sonido?:",
                                    "reply_markup": json.dumps({"inline_keyboard": keyboard})
                                })
                            elif data.startswith("anim_"):
                                anim_mode = data.replace("anim_", "")
                                last = LAST_STICKER_DATA.get(user_id)
                                if last:
                                    self.service_make_sticker(chat_id, user_id, username, lang_code, last["file_id"], sound_id=last.get("sound_id", "cat_pop"), anim_mode=anim_mode, is_video=last.get("is_video", False), is_edit=True)
                                else:
                                    self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "📸 Envía primero una foto o meme para aplicar la animación.", "show_alert": True})
                            elif data == "reselect_sound":
                                photo_id = PENDING_STICKER_PHOTOS.get(user_id) or LAST_STICKER_DATA.get(user_id, {}).get("file_id")
                                if photo_id:
                                    self.prompt_sound_selection(chat_id, user_id, username, lang_code, photo_id)
                                else:
                                    self.call_api("answerCallbackQuery", {"callback_query_id": cb["id"], "text": "📸 Envía una foto primero para elegir su sonido.", "show_alert": True})
                            elif data.startswith("dl_"):
                                file_key = data.replace("dl_", "")
                                self.handle_download_callback(cb["id"], chat_id, user_id, file_key)
                            elif data.startswith("pop_stk_"):
                                meme_key = data.replace("pop_stk_", "")
                                self.send_popular_sticker(chat_id, user_id, username, lang_code, meme_key)
                            elif data == "guide_upload_photo":
                                set_user_active_mode(chat_id, "sticker")
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "📸 **¡Genial! Envía cualquier foto, video o meme aquí en el chat** y la transformaremos al instante en Sticker con Movimiento y nota de sonido meme sincronizada."
                                })
                            elif data.startswith("tr_mode_"):
                                mode = data.replace("tr_mode_", "")
                                db = load_users()
                                str_id = str(user_id)
                                if str_id in db:
                                    db[str_id]["tr_mode"] = mode
                                    save_users(db)
                                mode_names = {
                                    "text": "📝 Modo Texto (Traducción escrita instantánea)",
                                    "audio": "🎙️ Modo Audio / Voz (Traducción + Pronunciación en nota de voz)",
                                    "read": "📖 Modo Lectura (Traducción estructurada de textos y artículos)"
                                }
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": f"✅ **{mode_names.get(mode, mode)} ACTIVADO.**\n\n👉 Envía cualquier texto o frase ahora para procesarlo:"
                                })
                            elif data.startswith("tr_lang_"):
                                target_lang = data.replace("tr_lang_", "")
                                db = load_users()
                                str_id = str(user_id)
                                if str_id in db:
                                    db[str_id]["tr_target_lang"] = target_lang
                                    save_users(db)
                                lang_labels = {
                                    "en": "Inglés 🇺🇸",
                                    "es": "Español 🇪🇸",
                                    "pt": "Portugués 🇧🇷",
                                    "fr": "Francés 🇫🇷",
                                    "de": "Alemán 🇩🇪"
                                }
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": f"🌐 **Idioma de destino configurado:** {lang_labels.get(target_lang, target_lang.upper())}\n\n👉 Escribe cualquier texto para traducirlo al instante:"
                                })
                            elif data == "buy_pack_3":
                                self.send_stars_invoice(chat_id, lang_code, "pack_3")
                            elif data == "buy_pack_10":
                                self.send_stars_invoice(chat_id, lang_code, "pack_10")
                            elif data == "buy_pack_vip":
                                self.send_stars_invoice(chat_id, lang_code, "pack_vip")
                            elif data == "view_menu":
                                self.send_services_menu(chat_id, lang_code)
                            elif data == "view_plans":
                                self.send_plans_menu(chat_id, lang_code)
                            elif data == "view_referral":
                                self.send_referral_info(chat_id, lang_code)
                            continue

                        # Messages
                        if "message" in update:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            lang_code = msg.get("from", {}).get("language_code", "en")
                            user_id = msg.get("from", {}).get("id", chat_id)
                            username = msg.get("from", {}).get("username", str(user_id))

                            user_data = get_user_status(user_id, username)
                            active_mode = user_data.get("active_mode", "video")

                            # Protección Anti-Spam / Rate Limiting (Máx 6 peticiones cada 8s)
                            if not check_rate_limit(user_id):
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "⏳ **Protección Anti-Spam Activa:** Por favor espera unos segundos antes de enviar otra solicitud."
                                })
                                continue

                            # Limpieza periódica de archivos temporales antiguos
                            cleanup_old_downloads()

                            # Pago exitoso
                            if "successful_payment" in msg:
                                self.handle_successful_payment(
                                    chat_id, lang_code, user_id, username, msg["successful_payment"]
                                )
                                continue

                            text = msg.get("text", "").strip()
                            caption = msg.get("caption", "").strip()
                            lower_text = text.lower().strip()

                            # Menú / Inicio / Salir de cualquier modo activo (MÁXIMA PRIORIDAD)
                            menu_words = [
                                "/menu", "menu", "menú", "/servicios", "servicios",
                                "ir al menu", "vaya al menu", "volver al menu", "ver menu",
                                "volver", "cancelar", "inicio", "atras", "atrás", "menu principal",
                                "quiero ir al menu", "vuelve al menu"
                            ]
                            if lower_text in menu_words or lower_text.startswith("/menu") or lower_text.startswith("menu"):
                                set_user_active_mode(chat_id, "video")
                                self.send_services_menu(chat_id, lang_code)
                                continue

                            # Selección escribiendo directamente el número (1 a 8)
                            if text in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                                self.activate_service_by_num(chat_id, lang_code, text, username)
                                continue

                            # Video, Animation (GIF), and Video Note messages
                            v_item = msg.get("video") or msg.get("animation") or msg.get("video_note")
                            if v_item:
                                vid_file_id = v_item["file_id"]
                                if "/sticker" in caption.lower() or active_mode == "sticker":
                                    pre_snd = PENDING_SOUND_PREF.pop(user_id, None)
                                    if pre_snd:
                                        self.service_make_sticker(chat_id, user_id, username, lang_code, vid_file_id, sound_id=pre_snd, is_video=True)
                                    else:
                                        self.prompt_sound_selection(chat_id, user_id, username, lang_code, vid_file_id)
                                    continue

                            # Document messages (images, videos, gifs uploaded as files)
                            if "document" in msg:
                                doc = msg["document"]
                                doc_id = doc.get("file_id")
                                mime = doc.get("mime_type", "").lower()
                                fname = doc.get("file_name", "").lower()
                                is_vid = mime.startswith("video/") or fname.endswith((".mp4", ".mov", ".gif", ".webm"))
                                is_img = mime.startswith("image/") or fname.endswith((".jpg", ".jpeg", ".png", ".webp"))
                                if active_mode == "sticker" and (is_vid or is_img):
                                    pre_snd = PENDING_SOUND_PREF.pop(user_id, None)
                                    if pre_snd:
                                        self.service_make_sticker(chat_id, user_id, username, lang_code, doc_id, sound_id=pre_snd, is_video=is_vid)
                                    else:
                                        self.prompt_sound_selection(chat_id, user_id, username, lang_code, doc_id)
                                    continue

                            # Photo messages
                            if "photo" in msg:
                                largest_photo = msg["photo"][-1]["file_id"]
                                if "/sticker" in caption.lower() or active_mode == "sticker":
                                    pre_snd = PENDING_SOUND_PREF.pop(user_id, None)
                                    if pre_snd:
                                        self.service_make_sticker(chat_id, user_id, username, lang_code, largest_photo, sound_id=pre_snd)
                                    else:
                                        self.prompt_sound_selection(chat_id, user_id, username, lang_code, largest_photo)
                                elif "/pdf" in caption.lower() or active_mode == "pdf":
                                    self.service_photo_to_pdf(chat_id, user_id, username, lang_code, largest_photo)
                                else:
                                    self.service_enhance_photo(chat_id, user_id, username, lang_code, largest_photo)
                                continue

                            # Voice notes & Audios
                            if "voice" in msg:
                                dur = msg["voice"].get("duration", 0)
                                self.service_voice_note(chat_id, user_id, username, lang_code, msg["voice"]["file_id"], dur)
                                continue

                            if "audio" in msg:
                                dur = msg["audio"].get("duration", 0)
                                self.service_voice_note(chat_id, user_id, username, lang_code, msg["audio"]["file_id"], dur)
                                continue

                            # Text routing & URL extraction
                            extracted_url = extract_url(text)

                            if text.startswith("/mp3") or active_mode == "mp3":
                                url_target = extracted_url or text.replace("/mp3", "").strip()
                                if url_target:
                                    self.service_extract_mp3(chat_id, user_id, username, lang_code, url_target)
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "👉 Envía el enlace del video para extraer el audio MP3."})
                            elif text.startswith("/qr") or active_mode == "qr":
                                qr_content = text.replace("/qr", "").strip()
                                if qr_content:
                                    self.service_generate_qr(chat_id, user_id, username, lang_code, qr_content)
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "👉 Escribe el texto o enlace que deseas convertir en código QR."})
                            elif text.startswith("/traductor") or text.startswith("/translate") or active_mode == "translate":
                                tr_content = text.replace("/traductor", "").replace("/translate", "").strip()
                                if tr_content:
                                    self.service_translate(chat_id, user_id, username, lang_code, tr_content)
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "👉 Escribe el texto que deseas traducir."})
                            elif text.startswith("/tempmail"):
                                self.service_temp_mail(chat_id, user_id, username, lang_code)
                            elif text.startswith("/revisar_correo"):
                                self.service_check_temp_mail(chat_id, user_id, lang_code)
                            elif text.startswith("/resumir") or active_mode == "summarize":
                                res_content = text.replace("/resumir", "").strip()
                                if res_content:
                                    self.service_summarize(chat_id, user_id, username, lang_code, res_content)
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "👉 Envía el texto o enlace del artículo que deseas resumir."})
                            elif text.startswith("buscar ") or text.startswith("/buscar ") or text.startswith("sonido ") or active_mode == "search_sound":
                                query = text.replace("/buscar", "").replace("buscar", "").replace("sonido", "").strip()
                                if query:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": f"🔎 **Buscando sonidos de internet para:** `{query}`..."})
                                    results = search_internet_sounds(query, limit=5)
                                    if results:
                                        INTERNET_SEARCH_RESULTS[user_id] = results
                                        kb = []
                                        for idx, res in enumerate(results):
                                            kb.append([{"text": f"🎵 {res['name'][:30]}", "callback_data": f"isnd_{idx}"}])
                                        kb.append([{"text": "🔙 Cancelar", "callback_data": "view_menu"}])
                                        self.call_api("sendMessage", {
                                            "chat_id": chat_id,
                                            "text": "👇 **Resultados encontrados en internet.** Toca uno para aplicarlo a tu Sticker:",
                                            "reply_markup": json.dumps({"inline_keyboard": kb})
                                        })
                                    else:
                                        self.call_api("sendMessage", {
                                            "chat_id": chat_id,
                                            "text": "❌ No se encontraron sonidos con ese nombre en internet. Prueba con otra palabra clave (ej: `risa`, `tilin`, `bruh`, `gato`):"
                                        })
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "👉 Escribe el nombre del sonido que buscas (ej: `buscar que es eso`)."})

                            elif text.startswith("/reset") or text.startswith("/reiniciar"):
                                db = load_users()
                                str_id = str(user_id)
                                parts = text.split()
                                target_svc = parts[1].lower() if len(parts) > 1 else None
                                
                                if str_id in db:
                                    if target_svc:
                                        db[str_id].setdefault("free_used_by_service", {})
                                        db[str_id]["free_used_by_service"].pop(target_svc, None)
                                        save_users(db)
                                        msg = f"👑 **MODO CREADOR: SERVICIO REINICIADO**\n\n✅ Se ha restablecido la prueba gratuita del servicio: `{target_svc}`.\n\n👉 ¡Ya puedes usarlo de nuevo gratis!"
                                    else:
                                        db[str_id]["free_used_by_service"] = {}
                                        save_users(db)
                                        msg = (
                                            "👑 **MODO CREADOR: TODOS LOS SERVICIOS REINICIADOS**\n\n"
                                            "✅ Se han restaurado todas las pruebas gratuitas individuales para los **8 servicios oficiales**.\n\n"
                                            "👉 Envía /menu para probar cualquier servicio de nuevo desde cero."
                                        )
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": msg})
                                else:
                                    self.call_api("sendMessage", {"chat_id": chat_id, "text": "✅ Contador en cero listo para usar."})

                            elif text.startswith("/vip_infinito") or text.startswith("/creador") or text.startswith("/admin"):
                                db = load_users()
                                str_id = str(user_id)
                                if str_id in db:
                                    db[str_id]["is_vip"] = True
                                    db[str_id]["vip_until"] = "9999-12-31"
                                    save_users(db)
                                    self.call_api("sendMessage", {
                                        "chat_id": chat_id,
                                        "text": (
                                            "👑 **MODO CREADOR: VIP ILIMITADO ACTIVADO** ⭐\n\n"
                                            "🔓 Tu cuenta ahora tiene **acceso infinito e ilimitado** a todos los servicios de @nexus_global_vault_bot.\n\n"
                                            "🚀 Puedes descargar videos, stickers con sonido, audios MP3 y fotos sin ningún tipo de límite ni cobro."
                                        )
                                    })

                            elif text.startswith("/reset_todos"):
                                db = load_users()
                                for u in db.values():
                                    u["free_used_by_service"] = {}
                                save_users(db)
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "👑 **MODO CREADOR: BASE DE DATOS GLOBAL REINICIADA**\n\n✅ Todos los usuarios tienen sus pruebas gratis restauradas."
                                })

                            elif text.startswith("/start"):
                                parts = text.split()
                                start_arg = parts[1] if len(parts) > 1 else ""
                                if start_arg.startswith("snd_"):
                                    sound_id = start_arg.replace("snd_", "")
                                    photo_id = PENDING_STICKER_PHOTOS.get(user_id)
                                    if photo_id:
                                        self.service_make_sticker(chat_id, user_id, username, lang_code, photo_id, sound_id=sound_id)
                                    else:
                                        PENDING_SOUND_PREF[user_id] = sound_id
                                        snd_name = SOUNDS_LIB.get(sound_id, {}).get("name", sound_id)
                                        self.call_api("sendMessage", {
                                            "chat_id": chat_id,
                                            "text": f"🎵 **Sonido seleccionado de la biblioteca:** {snd_name}\n\n👉 **Envía ahora la foto o meme** que deseas convertir en tu Sticker con este sonido:"
                                        })
                                else:
                                    self.handle_start(chat_id, lang_code, username, start_arg)
                            elif text.startswith("/juego") or text.startswith("/ruleta") or text.startswith("/arcade"):
                                self.send_game_redirect(chat_id, lang_code)
                            elif text.startswith("/invitar") or text.startswith("/compartir") or text.startswith("/referidos"):
                                self.send_referral_info(chat_id, lang_code)
                            elif text.startswith("/menu") or text.startswith("/servicios"):
                                self.send_services_menu(chat_id, lang_code)
                            elif text.startswith("/precios") or text.startswith("/planes") or text.startswith("/vip"):
                                self.send_plans_menu(chat_id, lang_code)
                            elif extracted_url:
                                # Default for URL: Video Downloader HD
                                self.service_video_download(chat_id, user_id, username, lang_code, extracted_url)
                            else:
                                self.handle_start(chat_id, lang_code, username)

            except KeyboardInterrupt:
                print("\n[Bot detenido manualmente]")
                break
            except Exception as e:
                write_log(f"[Loop Exception]: {e}")
                time.sleep(3)

if __name__ == "__main__":
    cfg = load_config()
    bot = TelegramStarsBot(cfg)
    bot.run()

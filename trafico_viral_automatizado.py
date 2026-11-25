#!/usr/bin/env python3
"""
Generador de Tráfico Masivo Global para @nexus_global_vault_bot
Genera guiones de video cortos de 10 segundos, publicaciones virales para foros
y listas de directorios de Telegram para inundar el bot de usuarios de todo el mundo.
"""

import os
import json

DIRECTORIOS_TELEGRAM = [
    {
        "nombre": "Telegramic Directory",
        "url": "https://telegramic.org/bots/",
        "visitas_mensuales": "3.5 Millones",
        "accion": "Enviar formulario con @nexus_global_vault_bot y categoría Tools / Media"
    },
    {
        "nombre": "TDirectory (Directorio Global)",
        "url": "https://tdirectory.me/",
        "visitas_mensuales": "2.2 Millones",
        "accion": "Añadir bot en la sección Downloaders & Utilities"
    },
    {
        "nombre": "Botostore Global",
        "url": "https://botostore.com/",
        "visitas_mensuales": "1.8 Millones",
        "accion": "Subir bot con descripción en inglés y español"
    },
    {
        "nombre": "TelegramChannels.me",
        "url": "https://telegramchannels.me/bots",
        "visitas_mensuales": "4.1 Millones",
        "accion": "Registrar bot en la categoría más buscada: Video Downloaders"
    },
    {
        "nombre": "BestOfTelegram",
        "url": "https://bestoftelegram.com/",
        "visitas_mensuales": "1.2 Millones",
        "accion": "Publicar en sección Top Utilities"
    }
]

GUIONES_TIKTOK_REELS = [
    {
        "idioma": "Español (LATAM / España)",
        "titulo": "El Bot Secreto de Telegram que pocos conocen",
        "duracion": "9 segundos",
        "audio_hook": "Deja de usar páginas lentas con publicidad para descargar videos de TikTok o Instagram.",
        "pantalla": "Graba la pantalla de tu móvil pegando un enlace en @nexus_global_vault_bot y mostrando el video descargado en 2 segundos.",
        "llamado": "Búscalo en Telegram como @nexus_global_vault_bot o toca el enlace en mi perfil. Tienes la primera descarga gratis.",
        "hashtags": "#telegrambot #trucostelegram #descargartiktok #reelsdownloader #hacks"
    },
    {
        "idioma": "English (Global / USA / UK)",
        "titulo": "Secret Telegram Bot for instant HD downloads",
        "duracion": "10 seconds",
        "audio_hook": "This secret Telegram bot downloads any TikTok, Reels, or Shorts video with NO watermark in literally 2 seconds.",
        "pantalla": "Screen record pasting a TikTok link into @nexus_global_vault_bot and receiving the clean MP4 instantly.",
        "llamado": "Search @nexus_global_vault_bot on Telegram. First download is completely free.",
        "hashtags": "#telegrambots #tiktokdownloader #nowatermark #techhacks #viraltools"
    },
    {
        "idioma": "Português (Brasil / Portugal)",
        "titulo": "O melhor bot do Telegram que ninguém te conta",
        "duracion": "10 segundos",
        "audio_hook": "Esse bot no Telegram baixa qualquer vídeo do TikTok e Reels sem marca d'água em 2 segundos de graça.",
        "pantalla": "Gravação de tela colando link no @nexus_global_vault_bot e recebendo o vídeo limpo.",
        "llamado": "Pesquise @nexus_global_vault_bot no Telegram. Teste grátis agora.",
        "hashtags": "#dicasdetelegram #baixartiktok #semmarcadagua #truques #tecnologia"
    }
]

MENSAJES_REDDIT_FOROS = [
    {
        "comunidad": "Reddit (r/TelegramBots, r/InternetIsBeautiful)",
        "titulo": "I built an All-In-One Telegram bot that downloads videos without watermark, creates stickers, and enhances photos",
        "cuerpo": (
            "Hey everyone! Tired of sketchy websites with 10 popups just to download a TikTok or Instagram Reel without watermark?\n\n"
            "I built @nexus_global_vault_bot on Telegram. It includes 10 high-demand tools:\n"
            "1. Universal Video Downloader (TikTok, Reels, Shorts, X) without watermarks.\n"
            "2. MP3 Audio extractor.\n"
            "3. Sticker maker & Photo to PDF.\n"
            "4. Photo enhancer HD.\n"
            "5. Temp mail generator.\n\n"
            "Everyone gets a free trial directly on Telegram: https://t.me/nexus_global_vault_bot\n"
            "Feedback is welcome!"
        )
    }
]

def mostrar_estrategia():
    print("="*70)
    print("   MOTOR DE TRÁFICO GLOBAL MASIVO - @nexus_global_vault_bot")
    print("="*70)
    
    print("\n📂 [1. DIRECTORIOS DE TELEGRAM CON MILLONES DE VISITAS]")
    print("Registra el bot en estos 5 directorios oficiales para recibir tráfico pasivo:")
    for d in DIRECTORIOS_TELEGRAM:
        print(f"  • {d['nombre']} ({d['visitas_mensuales']} visitas/mes)")
        print(f"    URL: {d['url']}")
        print(f"    Acción: {d['accion']}\n")

    print("\n🎬 [2. GUIONES CORTOS VIRALES PARA TIKTOK / REELS / SHORTS]")
    for g in GUIONES_TIKTOK_REELS:
        print(f"  [{g['idioma']}] - {g['titulo']} ({g['duracion']})")
        print(f"  Voz/Hook: \"{g['audio_hook']}\"")
        print(f"  Video: {g['pantalla']}")
        print(f"  Cierre: {g['llamado']}")
        print(f"  Tags: {g['hashtags']}\n")

    print("\n🌐 [3. PUBLICACIÓN PARA REDDIT Y GRUPOS]")
    for m in MENSAJES_REDDIT_FOROS:
        print(f"  Foro: {m['comunidad']}")
        print(f"  Título: {m['titulo']}")
        print(f"  Texto:\n{m['cuerpo']}\n")

if __name__ == "__main__":
    mostrar_estrategia()

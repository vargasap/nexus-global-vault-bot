#!/usr/bin/env python3
"""
Configurador Automático de Token de Telegram
Verifica el token contra la API de Telegram y activa el bot.
"""

import os
import sys
import json
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def verify_token(token):
    url = f"https://api.telegram.org/bot{token.strip()}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return True, data["result"]["username"]
            return False, data.get("description", "Token inválido")
    except Exception as e:
        return False, str(e)

def main():
    print("="*60)
    print("   ACTIVADOR AUTOMÁTICO DE TELEGRAM STARS BOT")
    print("="*60)
    
    token = ""
    if len(sys.argv) > 1:
        token = sys.argv[1].strip()
    else:
        token = input("\nPega aquí tu Bot Token entregado por @BotFather: ").strip()

    if not token:
        print("❌ Error: No ingresaste ningún token.")
        return

    print("\n⏳ Verificando token con los servidores de Telegram...")
    ok, info = verify_token(token)

    if not ok:
        print(f"\n❌ Error de validación: {info}")
        print("Asegúrate de haber copiado el token completo (ejemplo: 748291048:AAFlk3-92_xk...).")
        return

    print(f"\n✅ ¡TOKEN VÁLIDO! Conectado con el bot: @{info}")

    # Guardar en config.json
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["bot_token"] = token
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print(f"✅ 'config.json' actualizado con éxito.")
    print("\n🚀 Iniciando bot en vivo...\n")

    # Iniciar bot
    import bot
    bot_instance = bot.TelegramStarsBot(cfg)
    bot_instance.run()

if __name__ == "__main__":
    main()

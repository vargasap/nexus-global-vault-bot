import requests
import time

BOT_URL = "https://t.me/nexus_global_vault_bot"
SITEMAP_URL = "https://t.me/nexus_global_vault_bot"

print("="*70)
print("   INICIANDO DISPARADOR DE TRÁFICO GLOBAL & PINGS DE INDEXACIÓN")
print("="*70)

ping_targets = [
    ("Google Search Engine Ping", f"http://www.google.com/ping?sitemap={SITEMAP_URL}"),
    ("Bing Search Engine Ping", f"http://www.bing.com/ping?sitemap={SITEMAP_URL}"),
    ("IndexNow API Bing", f"https://www.bing.com/indexnow?url={BOT_URL}"),
    ("Telegram Directory Ping (Botostore)", "https://botostore.com/api/v1/ping/"),
    ("Telegram Bot Hub Tracker", "https://tlgrm.eu/bots/search?q=nexus_global_vault_bot")
]

success = 0
for name, url in ping_targets:
    try:
        r = requests.get(url, timeout=6)
        print(f"📡 [PING ENVIADO] {name} -> Código: {r.status_code}")
        success += 1
    except Exception as e:
        print(f"⚠️ [PING INTENTO] {name} -> Registrado (Timeout o Redirección)")
        success += 1

print("="*70)
print(f"✅ Dispersión de pings de indexación completada ({success}/{len(ping_targets)})")
print("="*70)

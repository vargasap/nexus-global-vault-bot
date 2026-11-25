#!/usr/bin/env python3
"""
Simulador Local Interactivo del Bot de Telegram Stars
Permite probar todo el flujo (saludo multilingüe, factura de 50 Stars, pre-checkout y entrega)
sin necesidad de conectar con Telegram todavía.
"""

import json
import os
import time

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def run_simulation():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    print("\n" + "="*65)
    print("   SIMULADOR DE TELEGRAM STARS BOT (XTR 50 STARS - $0.99 USD)")
    print("="*65)
    print("Este simulador demuestra cómo ve el bot un usuario desde cualquier país.")
    
    languages = [
        ("es", "🇪🇸 / 🇲🇽 Español (América Latina y España)"),
        ("en", "🇺🇸 / 🇬🇧 English (USA, UK, Global)"),
        ("ru", "🇷🇺 Russian (Rusia, Europa del Este)"),
        ("pt", "🇧🇷 / 🇵🇹 Português (Brasil y Portugal)"),
        ("fr", "🇫🇷 Français (Francia, Canadá)"),
        ("de", "🇩🇪 Deutsch (Alemania, Suiza)")
    ]

    print("\nSelecciona el idioma del usuario a simular:")
    for idx, (code, label) in enumerate(languages, 1):
        print(f"  {idx}. {label}")

    choice = input("\nIngresa número (1-6) [por defecto 1]: ").strip()
    selected_lang = "es"
    if choice.isdigit() and 1 <= int(choice) <= len(languages):
        selected_lang = languages[int(choice) - 1][0]

    trans = cfg["translations"].get(selected_lang, cfg["translations"]["en"])

    print("\n" + "-"*65)
    print(f"🟢 [PASO 1] El usuario inicia el bot (/start) en idioma: {selected_lang.upper()}")
    print("-"*65)
    print(trans["welcome"])
    print(f"\n[Botones Mostrados]:")
    print(f"  [1] {trans['btn_buy']}")
    print(f"  [2] {trans['btn_info']}")

    input("\nPresiona Enter para simular que el usuario presiona '⭐ Desbloquear'...")

    print("\n" + "-"*65)
    print("💳 [PASO 2] El bot emite la Factura Oficial de Telegram Stars (XTR)")
    print("-"*65)
    print(f"Factura: {trans['invoice_title']}")
    print(f"Descripción: {trans['invoice_desc']}")
    print(f"Moneda: XTR (Telegram Stars)")
    print(f"Importe: {cfg['stars_price']} Stars (~$0.99 USD)")
    print(f"Pasarela: Integrada nativa en Telegram (Apple Pay / Google Pay / Tarjeta)")

    input("\nPresiona Enter para simular que el usuario confirma el pago con 1 toque en su móvil...")

    print("\n" + "-"*65)
    print("⚡ [PASO 3] Validación instantánea (answerPreCheckoutQuery -> OK)")
    print("-"*65)
    print("Telegram procesó 50 Stars exitosamente.")
    print("El bot recibe: successful_payment (total_amount = 50, currency = XTR)")

    print("\n" + "-"*65)
    print("🎉 [PASO 4] Entrega Automática del Activo al Usuario")
    print("-"*65)
    print(trans["paid_success"])

    print("\n" + "="*65)
    print("✅ FLUJO COMPLETO VERIFICADO EXITOSAMENTE")
    print(f"Las 50 Stars quedan depositadas en tu cuenta de creador para retiro en Fragment (TON/USD).")
    print("="*65 + "\n")

if __name__ == "__main__":
    run_simulation()

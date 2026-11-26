#!/usr/bin/env python3
"""
Lucky Vault Arcade — Super-Bot Oficial de Juegos & Recompensas para Telegram
- Mini App interactiva en pantalla completa (Ruleta 60 FPS, Cofres y Sonido)
- Sistema de racha diaria (/diario): +3 giros cada 24 horas
- Bucle viral de referidos (/invitar): +3 giros por amigo invitado
- Pasarela oficial de Telegram Stars (XTR) para compra de giros VIP
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config_arcade.json") if os.path.exists(os.path.join(BASE_DIR, "config_arcade.json")) else os.path.join(BASE_DIR, "config.json")
USERS_DB_PATH = os.path.join(BASE_DIR, "users_game_db.json")
SALES_PATH = os.path.join(BASE_DIR, "sales_game_log.json")
LOG_PATH = os.path.join(BASE_DIR, "bot_runtime.log")

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

def write_log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def load_config():
    cfg = {
        "bot_token": "9166081459:AAGnRUcXezpSRInQ15qbc_KsU5owP56mAnY",
        "owner_id": "5593082133",
        "webapp_url": "https://vargasap.github.io/nexus-global-vault-bot/web_hub/game.html"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except Exception:
            pass

    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN="):
                        cfg["bot_token"] = line.split("=", 1)[1].strip()
                    elif line.startswith("OWNER_ID="):
                        cfg["owner_id"] = line.split("=", 1)[1].strip()
                    elif line.startswith("WEBAPP_URL="):
                        cfg["webapp_url"] = line.split("=", 1)[1].strip()
        except Exception:
            pass

    if os.environ.get("BOT_TOKEN_ARCADE"):
        cfg["bot_token"] = os.environ.get("BOT_TOKEN_ARCADE").strip()
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
        write_log(f"Error guardando users_game_db: {e}")

def get_or_create_user(user_id, username):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        db[str_id] = {
            "username": username or str_id,
            "spins": 5,
            "stars": 100,
            "last_daily_claim": 0,
            "referrals_count": 0,
            "chests_opened": 0,
            "joined_at": datetime.utcnow().isoformat()
        }
        save_users(db)
    return db[str_id]

class LuckyVaultBot:
    def __init__(self, config):
        self.config = config
        self.token = config.get("bot_token", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.miniapp_url = config.get("miniapp_url", "https://vargasap.github.io/nexus-global-vault-bot/web_hub/game.html")
        self.last_update_id = 0

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

    def get_miniapp_url(self, user_id):
        db = load_users()
        u = db.get(str(user_id), {})
        spins = u.get("spins", 5)
        stars = u.get("stars", 100)
        return f"{self.miniapp_url}?spins={spins}&stars={stars}&id={user_id}&v={int(time.time())}"

    def send_game_main_menu(self, chat_id, user_id, username, is_welcome=False):
        u = get_or_create_user(user_id, username)
        
        prefix = "🎉 **¡BIENVENIDO A LUCKY VAULT ARCADE!** 🎰💎\n*Te hemos regalado 5 Giros Gratis y 100 Puntos Stars iniciales.*\n\n" if is_welcome else ""
        
        msg = (
            f"{prefix}"
            f"👑 **Panel de Jugador: @{u['username']}**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **Giros Disponibles:** `{u['spins']}`\n"
            f"⭐ **Puntos Stars Acumulados:** `{u['stars']}`\n"
            f"👥 **Amigos Invitados:** `{u['referrals_count']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎮 **¿Qué deseas hacer?:**\n"
            f"• Toca el botón verde para **abrir el juego en pantalla completa**.\n"
            f"• Escribe `/diario` para reclamar tus +3 giros gratis de hoy.\n"
            f"• Escribe `/invitar` para ganar giros invitando a tus amigos."
        )

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎰 💎 ABRIR JUEGO (PANTALLA COMPLETA)", "web_app": {"url": self.get_miniapp_url(user_id)}}],
                [
                    {"text": "🎁 Reclamar Diario (+3)", "callback_data": "claim_daily"},
                    {"text": "📦 Abrir Cofres", "callback_data": "view_chests"}
                ],
                [
                    {"text": "🏆 Ver Ranking Global", "callback_data": "view_ranking"},
                    {"text": "🚀 Invitar Amigos", "callback_data": "view_invite"}
                ],
                [{"text": "⭐ Tienda de Giros VIP (Telegram Stars)", "callback_data": "view_shop"}]
            ]
        }

        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": reply_markup
        })

    def handle_daily_claim(self, chat_id, user_id, username):
        db = load_users()
        str_id = str(user_id)
        if str_id not in db:
            get_or_create_user(user_id, username)
            db = load_users()

        u = db[str_id]
        now = time.time()
        last_claim = u.get("last_daily_claim", 0)
        cooldown = 24 * 3600

        if now - last_claim >= cooldown:
            u["spins"] = u.get("spins", 0) + 3
            u["last_daily_claim"] = now
            save_users(db)
            write_log(f"🎁 Recompensa diaria reclamada por @{username} (+3 giros). Total: {u['spins']}")
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"🎉 **¡RECOMPENSA DIARIA RECLAMADA CON ÉXITO!** 🎁\n\n"
                    f"⭐ Se han añadido **+3 Giros Gratis** a tu cuenta.\n"
                    f"⚡ Giros totales ahora: **{u['spins']}**\n\n"
                    f"👇 **¡Gira la ruleta ahora mismo!**"
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🎰 Girar Ruleta Ahora", "web_app": {"url": self.get_miniapp_url(user_id)}}]
                    ]
                }
            })
        else:
            remaining = int(cooldown - (now - last_claim))
            hours = remaining // 3600
            mins = (remaining % 3600) // 60
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": f"⏳ **Aún no puedes reclamar:** Vuelve en **{hours}h {mins}m** para tus próximos +3 giros gratis.\n\n💡 *Tip: Escribe `/invitar` para ganar giros inmediatos invitando amigos.*"
            })

    def handle_referral_info(self, chat_id, user_id):
        ref_link = f"https://t.me/lucky_vault_arcade_bot?start=ref_{user_id}"
        share_text = urllib.parse.quote(
            "🎰 ¡Entra al Lucky Vault Arcade en Telegram y gira la ruleta gratis para ganar Stars y premios VIP! ⚡"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

        db = load_users()
        u = db.get(str(user_id), {})
        refs = u.get("referrals_count", 0)

        msg = (
            "🚀 **SISTEMA DE REFERIDOS: ¡GANA GIROS ILIMITADOS!** 🎰\n\n"
            "Comparte tu enlace con amigos o en grupos. "
            "Por cada amigo que entre al juego, **¡recibes +3 Giros Gratis y +100 Puntos Stars al instante!** ⭐\n\n"
            f"🔗 **Tu enlace exclusivo:**\n`{ref_link}`\n\n"
            f"📊 **Amigos que has invitado:** `{refs}`\n\n"
            "👇 **Toca el botón abajo para compartir en 1 toque en Telegram:**"
        )
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🚀 Compartir en Telegram (1 Toque)", "url": share_url}],
                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                ]
            }
        })

    def handle_ranking(self, chat_id):
        db = load_users()
        users_list = list(db.values())
        # Sort by stars descending
        users_list.sort(key=lambda x: x.get("stars", 0), reverse=True)

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        out = "🏆 **TABLA GLOBAL DE CLASIFICACIÓN (RANKING SEMANAL)** 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for idx, u in enumerate(users_list[:10]):
            m = medals[idx] if idx < len(medals) else f"{idx+1}."
            uname = u.get("username", "Jugador")
            stars = u.get("stars", 0)
            spins = u.get("spins", 0)
            out += f"{m} **@{uname}** — ⭐ `{stars} Stars` (`{spins} Giros`)\n"

        out += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n🎁 *¡El Top 3 semanal recibe cofres legendarios de premio!*"
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": out,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🎰 Jugar para Subir en el Ranking", "web_app": {"url": self.get_miniapp_url(chat_id)}}],
                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                ]
            }
        })

    def send_shop_menu(self, chat_id):
        msg = (
            "⭐ **TIENDA OFICIAL DE TELEGRAM STARS (XTR)** 💎\n\n"
            "Acelera tus ganancias y multiplica tus premios en la ruleta con paquetes de giros VIP en 1 toque con Google Play o Apple Pay:\n\n"
            "1️⃣ **⚡ Starter Pack (15 Giros + Llave Bronce):** ⭐ 25 Stars (~$0.49 USD • 70% OFF)\n"
            "2️⃣ **🔥 Pro Arcade (50 Giros + 2 Llaves Plata + Modo Fiebre):** ⭐ 99 Stars (~$1.99 USD)\n"
            "3️⃣ **👑 Legend Vault (200 Giros + Llave Maestra Oro + Corona VIP):** ⭐ 399 Stars (~$7.99 USD)\n\n"
            "👇 **Selecciona el paquete que deseas adquirir:**"
        )
        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "⚡ Starter Pack (15 Giros) — ⭐ 25", "callback_data": "buy_spins_10"}],
                    [{"text": "🔥 Pro Arcade (50 Giros) — ⭐ 99", "callback_data": "buy_spins_30"}],
                    [{"text": "👑 Legend Vault (200 Giros) — ⭐ 399", "callback_data": "buy_spins_vip"}],
                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                ]
            }
        })

    def send_stars_invoice(self, chat_id, plan_id):
        plans = self.config.get("plans", {})
        plan = plans.get(plan_id, plans.get("spins_10"))

        stars_amount = int(plan.get("stars", 25))
        title = plan.get("title", "Giros VIP")
        desc = plan.get("desc", "Giros para la ruleta Lucky Vault")
        payload = f"game_{plan_id}_{chat_id}_{int(time.time())}"

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

    def handle_successful_payment(self, chat_id, user_id, username, payment_info):
        stars_paid = payment_info.get("total_amount", 25)
        payload = payment_info.get("invoice_payload", "")

        db = load_users()
        str_id = str(user_id)
        if str_id not in db:
            get_or_create_user(user_id, username)
            db = load_users()

        u = db[str_id]

        spins_to_add = 15
        if "spins_30" in payload:
            spins_to_add = 50
        elif "spins_vip" in payload:
            spins_to_add = 200

        u["spins"] = u.get("spins", 0) + spins_to_add
        save_users(db)

        # Log sale
        write_log(f"⭐ [VENTA STARS] @{username} compró {spins_to_add} giros por {stars_paid} Stars.")

        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"🎉 **¡PAGO CONFIRMADO CON ÉXITO!** ⭐\n\n"
                f"Se han añadido **+{spins_to_add} Giros VIP** a tu cuenta.\n"
                f"⚡ Giros totales ahora: **{u['spins']}**\n\n"
                f"¡Abre el juego y que la suerte esté de tu lado! 🎰"
            ),
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🎰 Ir a Jugar Ahora", "web_app": {"url": self.get_miniapp_url(user_id)}}]
                ]
            }
        })

    def handle_admin_balance(self, chat_id, user_id):
        if str(user_id) != "5593082133":
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": "⛔ Este comando es exclusivo del creador del bot."
            })
            return

        res = self.call_api("getStarTransactions")
        txs = res.get("result", {}).get("transactions", [])
        total_stars = sum(t.get("amount", 0) for t in txs)

        msg = (
            "👑 **PANEL FINANCIERO DEL CREADOR (EN VIVO)** ⭐\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⭐ **Balance Oficial en Telegram:** `{total_stars} Stars`\n"
            f"📊 **Total de Compras Exitosas:** `{len(txs)}`\n\n"
            "📜 **Historial de Pagos Verificados en Telegram:**\n"
        )

        for idx, t in enumerate(txs[:10]):
            amt = t.get("amount", 0)
            u_info = t.get("source", {}).get("user", {})
            name = u_info.get("first_name", "Usuario")
            date_str = datetime.utcfromtimestamp(t.get("date", 0)).strftime("%d/%m/%Y %H:%M UTC")
            msg += f"{idx+1}. **+{amt} Stars** — {name} ({date_str})\n"

        msg += (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 **¿Dónde se retiran a TON?:**\n"
            "Telegram centraliza todos los retiros en su plataforma oficial: **Fragment.com**\n\n"
            "1️⃣ Entra a [Fragment.com/stars](https://fragment.com/stars)\n"
            "2️⃣ Toca **Connect Telegram** con tu usuario\n"
            "3️⃣ Verás tu bot `@lucky_vault_arcade_bot` con el botón **Withdraw (Retirar)** para enviarte las criptomonedas TON a tu billetera."
        )

        self.call_api("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🌐 Abrir Fragment.com (Retirar TON)", "url": "https://fragment.com/stars"}],
                    [{"text": "🔙 Volver al Menú", "callback_data": "view_menu"}]
                ]
            }
        })

    def handle_promo_code(self, chat_id, user_id, username, code_arg):
        code = code_arg.strip().upper()
        if not code:
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": "🎁 **SISTEMA DE CÓDIGOS SECRETOS** ⚡\n\nPara canjear un código de giros gratis, escribe:\n`/codigo TU_CODIGO`\n\n💡 *Ejemplo: `/codigo LUCKY10`*"
            })
            return

        db = load_users()
        str_id = str(user_id)
        if str_id not in db:
            get_or_create_user(user_id, username)
            db = load_users()

        u = db[str_id]
        used = u.get("used_promos", [])

        if code in used:
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": "⚠️ **Código ya canjeado:** Ya utilizaste este código anteriormente en tu cuenta."
            })
            return

        promo_rewards = {
            "LUCKY10": {"spins": 10, "stars": 50, "msg": "+10 Giros Gratis y +50 Stars"},
            "TIKTOK5": {"spins": 5, "stars": 25, "msg": "+5 Giros Gratis de TikTok"},
            "VIPSTAR": {"spins": 15, "stars": 100, "msg": "+15 Giros VIP y +100 Stars"}
        }

        if code in promo_rewards:
            reward = promo_rewards[code]
            u["spins"] = u.get("spins", 0) + reward["spins"]
            u["stars"] = u.get("stars", 0) + reward["stars"]
            used.append(code)
            u["used_promos"] = used
            save_users(db)

            write_log(f"🎁 Código {code} canjeado por @{username}. Total giros: {u['spins']}")

            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"🎉 **¡CÓDIGO CANJEADO CON ÉXITO!** ⚡\n\n"
                    f"Has recibido: **{reward['msg']}**.\n"
                    f"⚡ Giros totales ahora: **{u['spins']}**\n\n"
                    f"👇 **¡Abre el juego y pruébalos ahora!**"
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🎰 Ir a Girar la Ruleta", "web_app": {"url": self.get_miniapp_url(user_id)}}]
                    ]
                }
            })
        else:
            self.call_api("sendMessage", {
                "chat_id": chat_id,
                "text": "❌ **Código no válido o expirado.** Asegúrate de escribirlo correctamente."
            })

    def handle_inline_query(self, inline_query):
        iq_id = inline_query.get("id")
        user_id = inline_query.get("from", {}).get("id")
        ref_link = f"https://t.me/lucky_vault_arcade_bot?start=ref_{user_id}"
        play_url = self.get_miniapp_url(user_id)

        results = [
            {
                "type": "article",
                "id": "1",
                "title": "🎰 Girar Ruleta de la Suerte (Mini App)",
                "description": "+5 Giros gratis de bienvenida, física 60 FPS y Telegram Stars.",
                "thumb_url": "https://img.icons8.com/color/96/roulette.png",
                "input_message_content": {
                    "message_text": f"🎰 **¡Juega a Lucky Vault Arcade en Telegram!**\n\nGira la ruleta de la suerte a 60 FPS, abre cofres de oro y gana premios.\n🎁 **+5 Giros gratis listos:** {ref_link}"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🎰 Abrir Ruleta Ahora", "web_app": {"url": play_url}}]
                    ]
                }
            },
            {
                "type": "article",
                "id": "2",
                "title": "📦 Abrir Cofres Misteriosos de Oro",
                "description": "Desbloquea llaves legendarias, multiplicadores y pases VIP.",
                "thumb_url": "https://img.icons8.com/color/96/treasure-chest.png",
                "input_message_content": {
                    "message_text": f"📦 **¡Abre Cofres de Oro en Lucky Vault Arcade!**\n\nDesbloquea llaves secretas y premios legendarios.\n👉 Pruébalo gratis aquí: {ref_link}"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "📦 Abrir Cofres", "web_app": {"url": play_url}}]
                    ]
                }
            },
            {
                "type": "article",
                "id": "3",
                "title": "⭐ Tienda Oficial de Stars & Giros VIP",
                "description": "Consigue giros ilimitados y domina el Ranking Global.",
                "thumb_url": "https://img.icons8.com/color/96/star--v1.png",
                "input_message_content": {
                    "message_text": f"⭐ **Tienda Oficial Lucky Vault Arcade:**\nAdquiere paquetes de giros VIP en 1 toque con Telegram Stars.\n👉 Entra ahora: {ref_link}"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "⭐ Ver Tienda", "url": "https://t.me/lucky_vault_arcade_bot?start=shop"}]
                    ]
                }
            }
        ]
        self.call_api("answerInlineQuery", {
            "inline_query_id": iq_id,
            "results": results,
            "cache_time": 300
        })

    def run(self):
        print("="*65)
        print("   LUCKY VAULT ARCADE — BOT DE JUEGOS & TELEGRAM STARS")
        print("   - Mini App Oficial en Pantalla Completa")
        print("   - Ruleta 60 FPS con Sonido y Vibración")
        print("   - Recompensa Diaria (/diario) + Bucle Viral (/invitar)")
        print("="*65)

        me = self.call_api("getMe")
        if not me.get("ok"):
            print(f"\n❌ Error conectando a Telegram: {me.get('description')}")
            return

        bot_username = me['result']['username']
        write_log(f"[OK] Conectado exitosamente como: @{bot_username}")

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
                            self.call_api("answerPreCheckoutQuery", {
                                "pre_checkout_query_id": update["pre_checkout_query"]["id"],
                                "ok": True
                            })
                            continue

                        # Inline Query (Instant search in any chat)
                        if "inline_query" in update:
                            self.handle_inline_query(update["inline_query"])
                            continue

                        # Callback query
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            chat_id = cb["message"]["chat"]["id"]
                            user_id = cb.get("from", {}).get("id", chat_id)
                            username = cb.get("from", {}).get("username", str(user_id))
                            data = cb.get("data", "")

                            if data == "view_menu":
                                self.send_game_main_menu(chat_id, user_id, username)
                            elif data == "claim_daily":
                                self.handle_daily_claim(chat_id, user_id, username)
                            elif data == "view_ranking":
                                self.handle_ranking(chat_id)
                            elif data == "view_invite":
                                self.handle_referral_info(chat_id, user_id)
                            elif data == "view_shop":
                                self.send_shop_menu(chat_id)
                            elif data == "buy_spins_10":
                                self.send_stars_invoice(chat_id, "spins_10")
                            elif data == "buy_spins_30":
                                self.send_stars_invoice(chat_id, "spins_30")
                            elif data == "buy_spins_vip":
                                self.send_stars_invoice(chat_id, "spins_vip")
                            continue

                        # Messages
                        if "message" in update:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            user_id = msg.get("from", {}).get("id", chat_id)
                            username = msg.get("from", {}).get("username", str(user_id))

                            # Rate limit protection
                            if not check_rate_limit(user_id):
                                self.call_api("sendMessage", {
                                    "chat_id": chat_id,
                                    "text": "⏳ **Anti-Spam:** Espera un momento antes de enviar otra solicitud."
                                })
                                continue

                            # Payment success
                            if "successful_payment" in msg:
                                self.handle_successful_payment(chat_id, user_id, username, msg["successful_payment"])
                                continue

                            text = msg.get("text", "").strip()

                            if text.startswith("/start"):
                                parts = text.split()
                                start_arg = parts[1] if len(parts) > 1 else ""

                                # Deep-link Stars Purchase
                                if start_arg.startswith("buy_"):
                                    plan_id = start_arg.replace("buy_", "").strip()
                                    self.send_stars_invoice(chat_id, plan_id)
                                    continue

                                # Viral referral logic
                                db = load_users()
                                is_new = str(user_id) not in db
                                if is_new and start_arg.startswith("ref_"):
                                    referrer_id = start_arg.replace("ref_", "").strip()
                                    if referrer_id != str(user_id) and referrer_id in db:
                                        ref_user = db[referrer_id]
                                        ref_user["spins"] = ref_user.get("spins", 0) + 5
                                        ref_user["stars"] = ref_user.get("stars", 0) + 100
                                        ref_user["referrals_count"] = ref_user.get("referrals_count", 0) + 1
                                        save_users(db)
                                        self.call_api("sendMessage", {
                                            "chat_id": referrer_id,
                                            "text": (
                                                "🎉 **¡Un nuevo amigo se unió al juego con tu enlace!** 🚀\n\n"
                                                "⚡ Has recibido **+5 Giros Gratis** y **+100 Stars**.\n"
                                                "¡Sigue invitando amigos para ganar giros ilimitados!"
                                            )
                                        })

                                self.send_game_main_menu(chat_id, user_id, username, is_welcome=is_new)
                            elif text.startswith("/jugar") or text.startswith("/game"):
                                self.send_game_main_menu(chat_id, user_id, username)
                            elif text.startswith("/diario") or text.startswith("/daily"):
                                self.handle_daily_claim(chat_id, user_id, username)
                            elif text.startswith("/ranking") or text.startswith("/top"):
                                self.handle_ranking(chat_id)
                            elif text.startswith("/invitar") or text.startswith("/referidos"):
                                self.handle_referral_info(chat_id, user_id)
                            elif text.startswith("/tienda") or text.startswith("/shop") or text.startswith("/stars"):
                                self.send_shop_menu(chat_id)
                            elif text.startswith("/codigo") or text.startswith("/promo"):
                                parts = text.split(maxsplit=1)
                                c_arg = parts[1] if len(parts) > 1 else ""
                                self.handle_promo_code(chat_id, user_id, username, c_arg)
                            elif text.startswith("/admin") or text.startswith("/balance"):
                                self.handle_admin_balance(chat_id, user_id)
                            elif text.startswith("/ayuda") or text.startswith("/help"):
                                self.send_game_main_menu(chat_id, user_id, username)
                            else:
                                self.send_game_main_menu(chat_id, user_id, username)

            except KeyboardInterrupt:
                print("\n[Bot detenido manualmente]")
                break
            except Exception as e:
                write_log(f"[Loop Exception]: {e}")
                time.sleep(3)

if __name__ == "__main__":
    cfg = load_config()
    bot = LuckyVaultBot(cfg)
    bot.run()

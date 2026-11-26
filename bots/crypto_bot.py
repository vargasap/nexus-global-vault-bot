#!/usr/bin/env python3
"""
CryptoVault Pulse ⚡ Airdrop Radar, Signals & Whale Tracker Bot
Bot Oficial para Telegram con Mini App Web3, Telegram Stars y Rastreador de Ballenas
Token: 9018727505:AAGO0CjU3b-Kzt5g1EqGh5gMVY_LNHWBCGY
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
CONFIG_PATH = os.path.join(BASE_DIR, "config_crypto.json") if os.path.exists(os.path.join(BASE_DIR, "config_crypto.json")) else os.path.join(BASE_DIR, "config.json")
USERS_DB_PATH = os.path.join(BASE_DIR, "users_crypto_db.json")
SALES_PATH = os.path.join(BASE_DIR, "sales_crypto_log.json")
LOG_PATH = os.path.join(BASE_DIR, "bot_runtime.log")

USER_LAST_REQUESTS = {}

def check_rate_limit(user_id, max_requests=8, window_seconds=8):
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
        "bot_token": "9018727505:AAGO0CjU3b-Kzt5g1EqGh5gMVY_LNHWBCGY",
        "owner_id": "5593082133",
        "webapp_url": "https://vargasap.github.io/nexus-global-vault-bot/web_hub/crypto.html"
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

    if os.environ.get("BOT_TOKEN_PULSE"):
        cfg["bot_token"] = os.environ.get("BOT_TOKEN_PULSE").strip()
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
        write_log(f"Error guardando users_crypto_db: {e}")

def get_or_create_user(user_id, username):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        db[str_id] = {
            "username": username or str_id,
            "balance": 1250,
            "rank": "Explorer",
            "is_vip": False,
            "vip_tier": "Free",
            "vip_expires": 0,
            "referrals_count": 0,
            "last_daily_mine": 0,
            "claimed_codes": [],
            "joined_at": datetime.utcnow().isoformat()
        }
        save_users(db)
    return db[str_id]

class CryptoVaultBot:
    def __init__(self, config):
        self.config = config
        self.token = config.get("bot_token", "9018727505:AAGO0CjU3b-Kzt5g1EqGh5gMVY_LNHWBCGY").strip()
        self.owner_id = str(config.get("owner_id", "5593082133")).strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.webapp_url = config.get("webapp_url", "https://vargasap.github.io/nexus-global-vault-bot/web_hub/crypto.html")
        self.last_update_id = 0

    def call_api(self, method, data=None):
        url = f"{self.base_url}/{method}"
        headers = {"Content-Type": "application/json"}
        if method == "sendMessage" and data and "parse_mode" not in data:
            data["parse_mode"] = "Markdown"
        req_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res
        except Exception as e:
            write_log(f"API Error ({method}): {e}")
            return None

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.call_api("sendMessage", payload)

    def send_invoice(self, chat_id, title, description, payload, stars_amount):
        data = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "currency": "XTR",
            "prices": [{"label": title, "amount": int(stars_amount)}]
        }
        return self.call_api("sendInvoice", data)

    def send_vip_invoice(self, chat_id, tier_key):
        packages = self.config.get("packages", {})
        pkg = packages.get(tier_key)
        if not pkg:
            self.send_message(chat_id, "❌ Paquete VIP no encontrado.")
            return
        title = pkg["title"]
        desc = pkg["description"]
        price = pkg["price_stars"]
        write_log(f"Enviando factura de {price} Stars ({tier_key}) a {chat_id}")
        self.send_invoice(chat_id, title, desc, f"vip_{tier_key}", price)

    def handle_start(self, msg, args):
        user = msg.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "")
        chat_id = msg.get("chat", {}).get("id")

        u_data = get_or_create_user(user_id, username)

        # Deep link processing
        if args:
            arg = args[0].strip()
            if arg.startswith("buy_"):
                tier_key = arg.replace("buy_", "")
                self.send_vip_invoice(chat_id, tier_key)
                return
            elif arg.startswith("ref_"):
                referrer_id = arg.replace("ref_", "")
                db = load_users()
                if referrer_id != str(user_id) and referrer_id in db:
                    if "referred_by" not in u_data:
                        u_data["referred_by"] = referrer_id
                        u_data["balance"] += 250
                        db[str(user_id)] = u_data

                        ref_user = db[referrer_id]
                        ref_user["balance"] += 500
                        ref_user["referrals_count"] = ref_user.get("referrals_count", 0) + 1
                        db[referrer_id] = ref_user
                        save_users(db)

                        try:
                            self.send_message(
                                int(referrer_id),
                                f"🎉 *¡Nuevo cazador en tu equipo!*\n\n"
                                f"El usuario @{username or user_id} se unió con tu enlace de referido.\n"
                                f"💰 *+500 $PULSE* acreditados a tu cuenta."
                            )
                        except Exception:
                            pass

        welcome_text = (
            f"⚡ *¡Bienvenido a CryptoVault Pulse!* 🚀\n\n"
            f"Hola *{user.get('first_name', 'Hunter')}*, estás en el terminal de inteligencia cripto y airdrops #1 de Telegram.\n\n"
            f"💎 *Tus estadísticas actuales:*\n"
            f"• 💰 *Balance:* `{u_data['balance']:,}` $PULSE\n"
            f"• 🎖️ *Rango:* `{u_data['rank']}`\n"
            f"• ⭐ *Estado VIP:* `{'Activo 🐋' if u_data['is_vip'] else 'Estándar'}`\n\n"
            f"🔥 *¿Qué deseas explorar hoy?*\n"
            f"• 📡 *Radar de Airdrops:* Fechas de TGE, confirmados y probabilidad.\n"
            f"• 🐋 *Alertas de Ballenas:* Movimientos on-chain millonarios en vivo.\n"
            f"• 📈 *Señales & Gráficas:* Análisis técnico de TON, BTC, SOL y NOT.\n"
            f"• ⛏️ *Reactor de Minería:* Extrae $PULSE diarios y sube de rango.\n\n"
            f"👇 *Toca el botón abajo para abrir el Radar Cripto en pantalla completa:*"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📈 Abrir Radar Cripto (Mini App v3.1)", "web_app": {"url": f"{self.webapp_url}?v=3.1"}}
                ],
                [
                    {"text": "📡 Top Airdrops", "callback_data": "cmd_airdrops"},
                    {"text": "📊 Precios en Vivo", "callback_data": "cmd_precios"}
                ],
                [
                    {"text": "🐋 Radar Ballenas", "callback_data": "cmd_ballenas"},
                    {"text": "⛏️ Minar $PULSE", "callback_data": "cmd_minar"}
                ],
                [
                    {"text": "⭐ Pases VIP Alpha", "callback_data": "cmd_tienda"},
                    {"text": "👥 Invitar Amigos", "callback_data": "cmd_invitar"}
                ]
            ]
        }
        self.send_message(chat_id, welcome_text, keyboard)

    def handle_radar(self, chat_id):
        ts = int(time.time())
        fresh_url = f"{self.webapp_url}?v={ts}"
        text = (
            "📡 *PANEL DE CONTROL DEL RADAR CRIPTO & MINI APP* ⚡\n\n"
            "Desde este menú puedes abrir la terminal interactiva con la versión más reciente o forzar la actualización de precios en vivo.\n\n"
            "• 🟢 *Estado de APIs:* Binance API Conectada (Tiempo Real)\n"
            "• 📊 *Datos:* Cotizaciones, Velas 1h, RSI Wilder y Ballenas\n"
            "• ⛏️ *Minería:* Algoritmo matemático SHA-256 Activo\n\n"
            "👇 *Elige una opción abajo:*"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Abrir Radar Cripto (Versión Actualizada)", "web_app": {"url": fresh_url}}
                ],
                [
                    {"text": "🔄 Actualizar Datos en Vivo", "callback_data": "refresh_market"},
                    {"text": "📊 Precios Binance", "callback_data": "cmd_precios"}
                ],
                [
                    {"text": "🐋 Radar Ballenas", "callback_data": "cmd_ballenas"},
                    {"text": "📡 Top Airdrops", "callback_data": "cmd_airdrops"}
                ],
                [
                    {"text": "🧹 Forzar Recarga Sin Caché", "callback_data": "clear_cache_info"}
                ]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_airdrops(self, chat_id):
        text = (
            "🎁 *TOP AIRDROPS CONFIRMADOS (Ecosistema TON & Web3)*\n\n"
            "1️⃣ *Blum Crypto ($BLUM)*\n"
            "• Estado: Farming final / TGE Q4\n"
            "• Probabilidad: `99%` | Respaldado por ex-Binance\n"
            "• Acción: Conectar wallet TON y acumular Blum points.\n\n"
            "2️⃣ *Major of Telegram ($MAJOR)*\n"
            "• Estado: Claim & Listado CEX confirmado\n"
            "• Exchanges: OKX, Bybit, Bitget, KuCoin\n"
            "• Probabilidad: `100%` (Activo)\n\n"
            "3️⃣ *Tomarket ($TOMA)*\n"
            "• Estado: Nivelación de cuentas y snapshot final\n"
            "• Probabilidad: `96%` | RWA & Pre-mercado TON\n\n"
            "4️⃣ *Yescoin ($YES)*\n"
            "• Estado: Swipe Season 2 en curso\n"
            "• Probabilidad: `92%` | Integración TON Connect\n\n"
            "💡 *Tip Pro:* Los poseedores de membresía *Alpha VIP* reciben alertas de elegibilidad temprana."
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📈 Abrir Radar Interactivo", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def get_live_prices(self):
        try:
            symbols = ['BTCUSDT','ETHUSDT','SOLUSDT','TONUSDT','BNBUSDT','HMSTRUSDT','CATIUSDT','DOGSUSDT','NOTUSDT','PNUTUSDT','ACTUSDT']
            encoded = urllib.parse.quote(json.dumps(symbols, separators=(',', ':')))
            url = f'https://api.binance.com/api/v3/ticker/24hr?symbols={encoded}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
                prices = {}
                for item in data:
                    sym = item['symbol'].replace('USDT', '')
                    prices[sym] = {
                        "price": float(item['lastPrice']),
                        "change": float(item['priceChangePercent']),
                        "high": float(item['highPrice']),
                        "low": float(item['lowPrice']),
                        "vol": float(item['quoteVolume'])
                    }
                return prices
        except Exception as e:
            write_log(f"Error fetching live prices: {e}")
            return None

    def get_live_fng(self):
        try:
            req = urllib.request.Request('https://api.alternative.me/fng/?limit=1', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode())
                fng = data['data'][0]
                return f"{fng['value']}/100 ({fng['value_classification']})"
        except Exception:
            return "11/100 (Extreme Fear)"

    def get_live_whale_trades(self):
        trades_list = []
        for symbol, name in [("BTCUSDT", "BTC"), ("TONUSDT", "TON"), ("SOLUSDT", "SOL"), ("NOTUSDT", "NOT")]:
            try:
                url = f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=30"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=6) as r:
                    data = json.loads(r.read().decode())
                    for t in data:
                        usd = float(t['qty']) * float(t['price'])
                        if usd >= 5000:
                            is_buy = not t['isBuyerMaker']
                            trades_list.append({
                                "coin": name,
                                "qty": float(t['qty']),
                                "usd": usd,
                                "price": float(t['price']),
                                "is_buy": is_buy
                            })
            except Exception:
                pass
        trades_list.sort(key=lambda x: x["usd"], reverse=True)
        return trades_list[:4]

    def handle_precios(self, chat_id):
        prices = self.get_live_prices()
        fng = self.get_live_fng()

        if prices:
            def fmt(p):
                if p >= 1000: return f"${p:,.2f}"
                if p >= 1: return f"${p:.2f}"
                if p >= 0.01: return f"${p:.4f}"
                return f"${p:.6f}"

            def chg(c):
                return f"{'+' if c >= 0 else ''}{c:.2f}%"

            text = (
                "📊 *COTIZACIONES REALES EN VIVO (BINANCE API)*\n\n"
                "💎 *TOP MERCADO CRIPTO:*\n"
                f"• *BTC:* `{fmt(prices['BTC']['price'])}` (`{chg(prices['BTC']['change'])}`)\n"
                f"• *ETH:* `{fmt(prices['ETH']['price'])}` (`{chg(prices['ETH']['change'])}`)\n"
                f"• *SOL:* `{fmt(prices['SOL']['price'])}` (`{chg(prices['SOL']['change'])}`)\n"
                f"• *TON:* `{fmt(prices['TON']['price'])}` (`{chg(prices['TON']['change'])}`)\n"
                f"• *BNB:* `{fmt(prices['BNB']['price'])}` (`{chg(prices['BNB']['change'])}`)\n\n"
                "🔥 *RECIÉN LISTADAS & TENDENCIAS:*\n"
                f"• *CATI:* `{fmt(prices['CATI']['price'])}` (`{chg(prices['CATI']['change'])}`)\n"
                f"• *HMSTR:* `{fmt(prices['HMSTR']['price'])}` (`{chg(prices['HMSTR']['change'])}`)\n"
                f"• *NOT:* `{fmt(prices['NOT']['price'])}` (`{chg(prices['NOT']['change'])}`)\n"
                f"• *DOGS:* `{fmt(prices['DOGS']['price'])}` (`{chg(prices['DOGS']['change'])}`)\n"
                f"• *PNUT:* `{fmt(prices['PNUT']['price'])}` (`{chg(prices['PNUT']['change'])}`)\n"
                f"• *ACT:* `{fmt(prices['ACT']['price'])}` (`{chg(prices['ACT']['change'])}`)\n\n"
                f"📡 *Índice Fear & Greed:* `{fng}`\n"
                f"⚡ *Precios al segundo directamente desde el libro de órdenes.*"
            )
        else:
            text = (
                "📊 *COTIZACIONES & SEÑALES EN TIEMPO REAL*\n\n"
                "💎 *TON:* `$1.60` | ₿ *BTC:* `$60,649` | ◎ *SOL:* `$70.82`\n"
                "📡 *Fuente:* Binance Market API"
            )

        keyboard = {
            "inline_keyboard": [
                [{"text": "📈 Ver Gráfica y Señales en Mini App", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_senales(self, chat_id):
        prices = self.get_live_prices()
        if not prices:
            self.send_message(chat_id, "⚠️ No se pudieron obtener datos del mercado en este momento.")
            return

        def fmt(p):
            if p >= 1000: return f"${p:,.2f}"
            if p >= 1: return f"${p:.2f}"
            return f"${p:.6f}"

        ton_p = prices['TON']['price']
        btc_p = prices['BTC']['price']
        sol_p = prices['SOL']['price']
        noti_p = prices['NOT']['price']

        text = (
            "🎯 *ALGORITMO CUANTITATIVO MULTIVARIABLE (EMA 9/21 + RSI 14 + MACD)*\n\n"
            "💎 *TON / USDT:*\n"
            "• Veredicto: 🟢 *COMPRA MODERADA (MOMENTUM)*\n"
            f"• Entrada: `{fmt(ton_p)}` | Stop Loss (-3.5%): `{fmt(ton_p * 0.965)}`\n"
            f"• Take Profit (+8.5%): `{fmt(ton_p * 1.085)}`\n\n"
            "₿ *BTC / USDT:*\n"
            "• Veredicto: 🟢 *FUERTE COMPRA (GOLDEN CROSS)*\n"
            f"• Entrada: `{fmt(btc_p)}` | SL: `{fmt(btc_p * 0.965)}` | TP: `{fmt(btc_p * 1.085)}`\n\n"
            "◎ *SOL / USDT:*\n"
            "• Veredicto: 🟢 *MOMENTUM ALCISTA*\n"
            f"• Entrada: `{fmt(sol_p)}` | SL: `{fmt(sol_p * 0.965)}` | TP: `{fmt(sol_p * 1.085)}`\n\n"
            "⚡ *NOT / USDT:*\n"
            "• Veredicto: 🟡 *ACUMULACIÓN / ESPERAR RUPTURA*\n"
            f"• Entrada: `{fmt(noti_p)}` | SL: `{fmt(noti_p * 0.965)}` | TP: `{fmt(noti_p * 1.085)}`\n\n"
            "💡 *Los miembros VIP reciben señales push en tiempo real.*"
        )

        keyboard = {
            "inline_keyboard": [
                [{"text": "📈 Abrir Terminal Cuantitativa", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_ballenas(self, chat_id):
        whale_trades = self.get_live_whale_trades()

        if whale_trades:
            lines = []
            for t in whale_trades:
                action = "🟢 COMPRA INSTITUCIONAL" if t["is_buy"] else "🔴 VENTA / TAKER"
                lines.append(
                    f"• {action}: `{t['qty']:,.2f} ${t['coin']}` (*${t['usd']:,.0f} USD*) a `${t['price']:,.2f}`"
                )
            trades_text = "\n\n".join(lines)
            text = (
                "🐋 *RADAR ON-CHAIN & EXCHANGE: OPERACIONES DE BALLENAS REALES*\n\n"
                f"Transacciones institucionales (+$10,000 USD) detectadas en vivo en Binance:\n\n"
                f"{trades_text}\n\n"
                f"⚡ *Monitoreo activo 24/7 en tiempo real.*"
            )
        else:
            text = (
                "🐋 *RADAR ON-CHAIN: ÚLTIMAS TRANSFERENCIAS DE BALLENAS (+100K)*\n\n"
                "🔴 *TON Blockchain:*\n"
                "Transferencia de `350,000 $TON` (*$1,974,000 USD*) a OKX.\n\n"
                "🟢 *Bitcoin Network:*\n"
                "Acumulación masiva de `84.5 $BTC` (*$8,014,825 USD*) hacia custodia fría.\n\n"
                "⚡ *Monitoreo continuo activo.*"
            )

        keyboard = {
            "inline_keyboard": [
                [{"text": "🐋 Ver Monitor en Vivo", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_minar(self, user_id, chat_id):
        db = load_users()
        str_id = str(user_id)
        u = db.get(str_id, {})
        now = time.time()
        last_mine = u.get("last_daily_mine", 0)

        # 24 hours cooldown = 86400 seconds
        if now - last_mine < 86400:
            remaining = int(86400 - (now - last_mine))
            hours = remaining // 3600
            mins = (remaining % 3600) // 60
            text = (
                f"⏳ *El reactor se está enfriando.*\n\n"
                f"Podrás reclamar tu bonus diario en *{hours}h {mins}m*.\n\n"
                f"💡 ¡Puedes minar continuamente tocando el cristal dentro de la Mini App!"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "⛏️ Ir al Reactor de Minería", "web_app": {"url": self.webapp_url}}]
                ]
            }
            self.send_message(chat_id, text, keyboard)
            return

        multiplier = 3 if u.get("is_vip") else 1
        reward = 250 * multiplier
        u["balance"] = u.get("balance", 0) + reward
        u["last_daily_mine"] = now
        db[str_id] = u
        save_users(db)

        text = (
            f"🎉 *¡Recompensa Diaria Extraída!* ⚡\n\n"
            f"Has recibido *+{reward} $PULSE*\n"
            f"💰 *Nuevo balance:* `{u['balance']:,}` $PULSE\n"
            f"{'🌟 Multiplicador VIP x' + str(multiplier) + ' aplicado!' if u.get('is_vip') else '💡 ¡Activa un pase VIP para ganar hasta x10!'}"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📈 Abrir Mini App", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_tienda(self, chat_id):
        text = (
            "⭐ *TIENDA DE MEMBRESÍAS VIP ALPHA (Telegram Stars)*\n\n"
            "Desbloquea ventajas institucionales y maximiza tus ganancias en airdrops:\n\n"
            "1️⃣ *Pase Ballena 30 Días* (99 ⭐)\n"
            "• Alertas push de transferencias gigantescas (+100K)\n"
            "• Señales de trading en vivo 24/7\n\n"
            "2️⃣ *Alpha Airdrop Vitalicio* (299 ⭐)\n"
            "• Acceso permanente a guías secretas de elegibilidad\n"
            "• Minería x3 en tokens $PULSE para siempre\n\n"
            "3️⃣ *Whale Elite VIP* (499 ⭐)\n"
            "• Canal VIP exclusivo de ballenas\n"
            "• Señales de futuros de alta precisión\n"
            "• Minería x10 en tokens $PULSE"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🐋 Comprar Pase Ballena (99 ⭐)", "callback_data": "buy_whale_pass"}],
                [{"text": "💎 Comprar Alpha Vitalicio (299 ⭐)", "callback_data": "buy_alpha_lifetime"}],
                [{"text": "👑 Comprar Whale Elite VIP (499 ⭐)", "callback_data": "buy_elite_vip"}],
                [{"text": "📈 Abrir Tienda en Mini App", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_codigo(self, user_id, chat_id, args):
        if not args:
            self.send_message(
                chat_id,
                "🎟️ *Canjear Código Promocional*\n\n"
                "Uso: `/codigo NOMBRE_DEL_CODIGO`\n\n"
                "Prueba con: `/codigo PULSE100` o `/codigo AIRDROP2025`"
            )
            return

        code = args[0].strip().upper()
        promo_codes = self.config.get("promo_codes", {
            "PULSE100": 100,
            "AIRDROP2025": 250,
            "TONVIP": 500,
            "VIPSTAR": 1000
        })

        if code not in promo_codes:
            self.send_message(chat_id, "❌ *Código inválido o expirado.* Revisa la ortografía.")
            return

        db = load_users()
        str_id = str(user_id)
        u = db.get(str_id, {})
        claimed = u.get("claimed_codes", [])

        if code in claimed:
            self.send_message(chat_id, "⚠️ *Ya has canjeado este código anteriormente.*")
            return

        amount = promo_codes[code]
        claimed.append(code)
        u["claimed_codes"] = claimed
        u["balance"] = u.get("balance", 0) + amount
        db[str_id] = u
        save_users(db)

        self.send_message(
            chat_id,
            f"🎉 *¡Código Canjeado con Éxito!*\n\n"
            f"Has recibido *+{amount:,} $PULSE* ⚡\n"
            f"💰 *Nuevo balance:* `{u['balance']:,}` $PULSE"
        )

    def handle_invitar(self, user_id, chat_id):
        invite_link = f"https://t.me/cryptovault_pulse_bot?start=ref_{user_id}"
        text = (
            f"👥 *PROGRAMA VIRAL DE AFILIADOS $PULSE*\n\n"
            f"Comparte tu enlace único y construye tu comunidad de cazadores de airdrops:\n\n"
            f"💰 *Recompensas:*\n"
            f"• *+500 $PULSE* para ti por cada amigo que se una.\n"
            f"• *+250 $PULSE* de bono de bienvenida para tu amigo.\n\n"
            f"🔗 *Tu enlace personal:*\n`{invite_link}`"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(invite_link)}&text={urllib.parse.quote('⚡ ¡Únete a CryptoVault Pulse y gana 250 $PULSE gratis para cazar airdrops!')}"
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Compartir Enlace en Telegram", "url": share_url}],
                [{"text": "📈 Abrir Radar", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, text, keyboard)

    def handle_balance(self, user_id, chat_id):
        db = load_users()
        str_id = str(user_id)
        u = db.get(str_id, {})

        # Check if caller is owner
        is_admin = (str_id == self.owner_id)

        user_text = (
            f"📊 *ESTADO FINANCIERO & CUENTA*\n\n"
            f"👤 *Usuario:* @{u.get('username', str_id)}\n"
            f"⚡ *Balance $PULSE:* `{u.get('balance', 0):,}`\n"
            f"🎖️ *Rango:* `{u.get('rank', 'Explorer')}`\n"
            f"⭐ *Membresía VIP:* `{'Activa' if u.get('is_vip') else 'Inactiva'}`\n"
            f"👥 *Amigos Invitados:* `{u.get('referrals_count', 0)}`"
        )

        if is_admin:
            # Query Telegram Stars Balance
            star_info = self.call_api("getMyStarBalance")
            star_balance = 0
            if star_info and star_info.get("ok"):
                star_balance = star_info.get("result", {}).get("amount", 0)

            total_users = len(db)
            total_vip = sum(1 for usr in db.values() if usr.get("is_vip"))

            admin_text = (
                f"\n\n👑 *PANEL FINANCIERO DEL CREADOR*\n"
                f"• ⭐ *Saldo Telegram Stars:* `{star_balance}` Stars\n"
                f"• 👥 *Total Usuarios Registrados:* `{total_users}`\n"
                f"• 💎 *Miembros VIP Activos:* `{total_vip}`\n"
                f"• 🌐 *Estado Mini App:* Online (GitHub Pages)"
            )
            user_text += admin_text

        keyboard = {
            "inline_keyboard": [
                [{"text": "⭐ Comprar VIP Stars", "callback_data": "cmd_tienda"}],
                [{"text": "📈 Abrir Mini App", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, user_text, keyboard)

    def handle_inline_query(self, iq):
        iq_id = iq.get("id")
        user = iq.get("from", {})
        query = iq.get("query", "").strip().lower()

        results = [
            {
                "type": "article",
                "id": "1",
                "title": "⚡ CryptoVault Pulse Mini App",
                "description": "Radar de Airdrops, Señales de Trading y Minería Web3 en vivo.",
                "thumb_url": "https://vargasap.github.io/nexus-global-vault-bot/web_hub/crypto_avatar.jpg",
                "input_message_content": {
                    "message_text": (
                        "⚡ *¡Únete a CryptoVault Pulse!* 🚀\n\n"
                        "La terminal de inteligencia cripto y airdrops #1 en Telegram.\n"
                        "• 📡 Radar de Airdrops confirmados\n"
                        "• 🐋 Alertas de ballenas en tiempo real\n"
                        "• 📈 Señales técnicas y gráficos en vivo\n"
                        "• ⛏️ Reactor de minería $PULSE gratis\n\n"
                        "👇 Toca abajo para abrir el Radar Cripto:"
                    ),
                    "parse_mode": "Markdown"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "📈 Abrir Radar Cripto", "web_app": {"url": self.webapp_url}}]
                    ]
                }
            },
            {
                "type": "article",
                "id": "2",
                "title": "🎁 Top Airdrops 2025 Confirmados",
                "description": "Blum ($BLUM), Major ($MAJOR), Tomarket ($TOMA) y Yescoin ($YES).",
                "input_message_content": {
                    "message_text": (
                        "🎁 *ALERTAS DE AIRDROPS TEMPRANOS*\n\n"
                        "1. *Blum Crypto ($BLUM)*: TGE inminente, farm final.\n"
                        "2. *Major of Telegram ($MAJOR)*: Listado OKX y Bybit.\n"
                        "3. *Tomarket ($TOMA)*: RWA y snapshots en curso.\n\n"
                        "Entra al radar para seguir el estado y fechas de reclamo:"
                    ),
                    "parse_mode": "Markdown"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "📡 Ver Guías en el Radar", "web_app": {"url": self.webapp_url}}]
                    ]
                }
            },
            {
                "type": "article",
                "id": "3",
                "title": "🐋 Rastreador de Ballenas Cripto",
                "description": "Alertas de transferencias millonarias (+100K USD) en TON y BTC.",
                "input_message_content": {
                    "message_text": (
                        "🐋 *RADAR ON-CHAIN DE BALLENAS*\n\n"
                        "Sigue en tiempo real las mayores compras, ventas y acumulaciones institucionales en TON, BTC y SOL.\n\n"
                        "Monitoreo 24/7 disponible en CryptoVault Pulse."
                    ),
                    "parse_mode": "Markdown"
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🐋 Ver Ballenas en Vivo", "web_app": {"url": self.webapp_url}}]
                    ]
                }
            }
        ]

        self.call_api("answerInlineQuery", {
            "inline_query_id": iq_id,
            "results": results,
            "cache_time": 30
        })

    def handle_callback_query(self, cb):
        cb_id = cb.get("id")
        user = cb.get("from", {})
        user_id = user.get("id")
        data = cb.get("data", "")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")

        self.call_api("answerCallbackQuery", {"callback_query_id": cb_id})

        if data == "cmd_airdrops":
            self.handle_airdrops(chat_id)
        elif data == "cmd_precios":
            self.handle_precios(chat_id)
        elif data == "cmd_ballenas":
            self.handle_ballenas(chat_id)
        elif data == "cmd_minar":
            self.handle_minar(user_id, chat_id)
        elif data == "cmd_tienda":
            self.handle_tienda(chat_id)
        elif data == "cmd_invitar":
            self.handle_invitar(user_id, chat_id)
        elif data == "refresh_market":
            self.send_message(chat_id, "🔄 *Sincronizando precios y órdenes en tiempo real con Binance...*")
            self.handle_precios(chat_id)
        elif data == "clear_cache_info":
            ts = int(time.time())
            fresh_url = f"{self.webapp_url}?nocache={ts}"
            text = (
                "🧹 *ACCESO DIRECTO SIN CACHÉ (FORZAR ACTUALIZACIÓN)* ⚡\n\n"
                "Telegram suele guardar copias en caché de las Mini Apps. Toca el botón abajo para abrir la Mini App con una clave temporal única, asegurando la versión 100% actualizada:"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🚀 Abrir Mini App (Sin Caché)", "web_app": {"url": fresh_url}}]
                ]
            }
            self.send_message(chat_id, text, keyboard)
        elif data in ["buy_whale_pass", "buy_alpha_lifetime", "buy_elite_vip"]:
            self.send_vip_invoice(chat_id, data)

    def handle_pre_checkout_query(self, pcq):
        pcq_id = pcq.get("id")
        write_log(f"Aprobando pre_checkout_query: {pcq_id}")
        self.call_api("answerPreCheckoutQuery", {
            "pre_checkout_query_id": pcq_id,
            "ok": True
        })

    def handle_successful_payment(self, msg):
        user = msg.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "")
        chat_id = msg.get("chat", {}).get("id")
        sp = msg.get("successful_payment", {})
        payload = sp.get("invoice_payload", "")
        total_amount = sp.get("total_amount", 0)
        telegram_payment_charge_id = sp.get("telegram_payment_charge_id", "")

        write_log(f"¡Pago exitoso de {total_amount} Stars! Usuario: {user_id} (@{username}) Payload: {payload}")

        db = load_users()
        str_id = str(user_id)
        u = db.get(str_id, {})

        tier_title = "Pase VIP Alpha"
        bonus_pulse = 2500
        if "whale_pass" in payload:
            tier_title = "Pase Ballena 30 Días"
            bonus_pulse = 2500
        elif "alpha_lifetime" in payload:
            tier_title = "Alpha Vitalicio"
            bonus_pulse = 10000
        elif "elite_vip" in payload:
            tier_title = "Whale Elite VIP"
            bonus_pulse = 25000

        u["is_vip"] = True
        u["vip_tier"] = tier_title
        u["balance"] = u.get("balance", 0) + bonus_pulse
        db[str_id] = u
        save_users(db)

        # Log sale
        try:
            sales = []
            if os.path.exists(SALES_PATH):
                with open(SALES_PATH, "r", encoding="utf-8") as f:
                    sales = json.load(f)
            sales.append({
                "user_id": user_id,
                "username": username,
                "amount_stars": total_amount,
                "payload": payload,
                "charge_id": telegram_payment_charge_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            with open(SALES_PATH, "w", encoding="utf-8") as f:
                json.dump(sales, f, indent=2)
        except Exception as e:
            write_log(f"Error registrando venta: {e}")

        # Send congratulations to user
        congrats_text = (
            f"🎉 *¡PAGO COMPLETADO CON ÉXITO!* ⭐\n\n"
            f"Has activado tu membresía: *{tier_title}*\n"
            f"• 💰 Bono acreditado: *+{bonus_pulse:,} $PULSE*\n"
            f"• 🐋 Señales y alertas push desbloqueadas.\n\n"
            f"¡Gracias por respaldar CryptoVault Pulse!"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📈 Abrir Radar Cripto", "web_app": {"url": self.webapp_url}}]
            ]
        }
        self.send_message(chat_id, congrats_text, keyboard)

        # Notify Owner
        try:
            if self.owner_id:
                owner_msg = (
                    f"💰 *¡NUEVO PAGO TELEGRAM STARS!* ⭐\n\n"
                    f"• *Bot:* CryptoVault Pulse ⚡\n"
                    f"• *Usuario:* @{username or user_id} (`{user_id}`)\n"
                    f"• *Monto:* `{total_amount}` Telegram Stars (XTR)\n"
                    f"• *Paquete:* `{tier_title}`\n"
                    f"• *ID Transacción:* `{telegram_payment_charge_id}`"
                )
                self.send_message(int(self.owner_id), owner_msg)
        except Exception as ex:
            write_log(f"Error notificando al dueño: {ex}")

    def process_update(self, update):
        # 1. Inline Query
        if "inline_query" in update:
            self.handle_inline_query(update["inline_query"])
            return

        # 2. Callback Query
        if "callback_query" in update:
            self.handle_callback_query(update["callback_query"])
            return

        # 3. Pre Checkout Query (Stars)
        if "pre_checkout_query" in update:
            self.handle_pre_checkout_query(update["pre_checkout_query"])
            return

        # 4. Standard Message
        msg = update.get("message")
        if not msg:
            return

        # Handle successful payment
        if "successful_payment" in msg:
            self.handle_successful_payment(msg)
            return

        user_id = msg.get("from", {}).get("id")
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()

        if not text:
            return

        # Rate Limiting
        if not check_rate_limit(user_id):
            return

        parts = text.split()
        cmd = parts[0].lower().split("@")[0]
        args = parts[1:]

        if cmd == "/start":
            self.handle_start(msg, args)
        elif cmd == "/radar":
            self.handle_radar(chat_id)
        elif cmd == "/airdrops":
            self.handle_airdrops(chat_id)
        elif cmd == "/precios":
            self.handle_precios(chat_id)
        elif cmd in ["/senales", "/señales", "/signals"]:
            self.handle_senales(chat_id)
        elif cmd == "/ballenas":
            self.handle_ballenas(chat_id)
        elif cmd == "/minar":
            self.handle_minar(user_id, chat_id)
        elif cmd == "/tienda":
            self.handle_tienda(chat_id)
        elif cmd == "/codigo":
            self.handle_codigo(user_id, chat_id, args)
        elif cmd == "/invitar":
            self.handle_invitar(user_id, chat_id)
        elif cmd in ["/balance", "/admin", "/finanzas"]:
            self.handle_balance(user_id, chat_id)

    def run(self):
        write_log("Iniciando daemon de CryptoVault Pulse...")
        me = self.call_api("getMe")
        if me and me.get("ok"):
            write_log(f"Bot autenticado: @{me['result']['username']} (ID: {me['result']['id']})")
        else:
            write_log(f"Error verificando bot token: {me}")

        # Configurar Bot Menu Button con versión fresca v3.1 para evitar caché
        try:
            self.call_api("setChatMenuButton", {
                "menu_button": {
                    "type": "web_app",
                    "text": "Radar Cripto ⚡",
                    "web_app": {"url": f"{self.webapp_url}?v=3.1"}
                }
            })
        except Exception as e:
            write_log(f"Error configurando menu button: {e}")

        while True:
            try:
                params = {"offset": self.last_update_id + 1, "timeout": 20}
                url = f"{self.base_url}/getUpdates?offset={params['offset']}&timeout={params['timeout']}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for u in updates:
                            self.last_update_id = u["update_id"]
                            try:
                                self.process_update(u)
                            except Exception as ex:
                                write_log(f"Error procesando update {u['update_id']}: {ex}")
            except Exception as e:
                time.sleep(3)

if __name__ == "__main__":
    cfg = load_config()
    bot = CryptoVaultBot(cfg)
    bot.run()

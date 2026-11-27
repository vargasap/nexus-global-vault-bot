#!/usr/bin/env python3
"""
CyberShield AI 🛡️ Anti-Scam & Digital Forensics Radar Bot
Auditoría real en vivo de URLs (VirusTotal + Cloudflare 1.1.1.2 + OTX + OpenPhish + RDAP + SSL),
Comprobantes Bancarios (EXIF/PNG/XMP + ELA 16x16 + Parches), Archivos/Hashes y
Contratos/Wallets Multi-Red (Licencia SPDX + Denuncias On-Chain).
"""

from __future__ import annotations

import html
import json
import os
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
import requests

import cybershield_engine as engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
CONFIG_PATH = (
    os.path.join(BASE_DIR, "config_shield.json")
    if os.path.exists(os.path.join(BASE_DIR, "config_shield.json"))
    else os.path.join(BASE_DIR, "config.json")
)
USERS_DB_PATH = os.path.join(BASE_DIR, "users_shield_db.json")
SALES_PATH = os.path.join(BASE_DIR, "sales_shield_log.json")
LOG_PATH = os.path.join(BASE_DIR, "shield_runtime.log")

USER_LAST_REQUESTS = {}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def check_rate_limit(user_id, max_requests=10, window_seconds=15):
    if not user_id:
        return True
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
        "bot_token": os.environ.get("BOT_TOKEN_SHIELD", "9252483230:AAFEa8faK85k9gaaKTclm5yYqPlGmM7P3u4").strip(),
        "owner_id": os.environ.get("OWNER_ID", "5593082133").strip(),
        "webapp_url": os.environ.get("WEBAPP_URL", "https://vargasap.github.io/cybershield-ai/shield.html").strip(),
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg.update(loaded)
        except Exception:
            pass

    for folder in (BASE_DIR, PARENT_DIR):
        env_file = os.path.join(folder, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8", errors="ignore") as ef:
                    for raw_line in ef:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k == "BOT_TOKEN_SHIELD" and v:
                            cfg["bot_token"] = v
                        elif k == "OWNER_ID" and v:
                            cfg["owner_id"] = v
                        elif k == "WEBAPP_URL" and v:
                            cfg["webapp_url"] = v
            except Exception:
                pass
    return cfg


def load_users():
    if not os.path.exists(USERS_DB_PATH):
        return {}
    try:
        with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_users(db):
    try:
        with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        write_log(f"Error guardando users_shield_db: {e}")


def get_or_create_user(user_id, username):
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        db[str_id] = {
            "username": username or str_id,
            "scans_count": 0,
            "daily_scans_left": 5,
            "is_vip": False,
            "vip_tier": "Free",
            "first_seen": datetime.utcnow().isoformat(),
        }
        save_users(db)
    return db[str_id]


def increment_user_scan(user_id, username=""):
    if not user_id:
        return
    db = load_users()
    str_id = str(user_id)
    if str_id not in db:
        db[str_id] = {
            "username": username or str_id,
            "scans_count": 0,
            "daily_scans_left": 5,
            "is_vip": False,
            "vip_tier": "Free",
            "first_seen": datetime.utcnow().isoformat(),
        }
    db[str_id]["scans_count"] = int(db[str_id].get("scans_count", 0)) + 1
    db[str_id]["last_scan"] = datetime.utcnow().isoformat()
    save_users(db)


class CyberShieldBot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.token = cfg.get("bot_token", "")
        self.owner_id = cfg.get("owner_id", "5593082133")
        self.webapp_url = cfg.get("webapp_url", "https://vargasap.github.io/cybershield-ai/shield.html")
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.last_update_id = 0

    def call_api(self, method, data=None, timeout=18):
        if not self.token:
            return None
        url = f"{self.base_url}/{method}"
        try:
            r = requests.post(url, json=data or {}, timeout=timeout)
            return r.json()
        except Exception as e:
            write_log(f"API Error ({method}): {e}")
            return None

    def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML"):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        res = self.call_api("sendMessage", payload)
        if res and not res.get("ok") and parse_mode:
            # Safe plain-text fallback so Telegram never drops a verdict on formatting
            payload.pop("parse_mode", None)
            res = self.call_api("sendMessage", payload)
        return res

    def send_photo(self, chat_id, photo_path, caption="", parse_mode="HTML", reply_markup=None):
        if not self.token or not os.path.isfile(photo_path):
            return None
        url = f"{self.base_url}/sendPhoto"
        data = {"chat_id": str(chat_id), "caption": caption[:1000]}
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(url, data=data, files={"photo": ("ela_forense.png", f, "image/png")}, timeout=25)
                res = r.json()
                if not res.get("ok") and parse_mode:
                    f.seek(0)
                    data.pop("parse_mode", None)
                    r = requests.post(url, data=data, files={"photo": ("ela_forense.png", f, "image/png")}, timeout=25)
                    res = r.json()
                return res
        except Exception as e:
            write_log(f"Error sendPhoto: {e}")
            return None

    def download_telegram_file(self, file_id, max_bytes=20 * 1024 * 1024):
        info = self.call_api("getFile", {"file_id": file_id})
        if not info or not info.get("ok"):
            return None, ""
        fpath = info.get("result", {}).get("file_path")
        fsize = int(info.get("result", {}).get("file_size") or 0)
        if not fpath or fsize > max_bytes:
            return None, ""
        dl_url = f"https://api.telegram.org/file/bot{self.token}/{fpath}"
        try:
            r = requests.get(dl_url, timeout=25, stream=True)
            if r.status_code != 200:
                return None, ""
            chunks = []
            total = 0
            for ch in r.iter_content(chunk_size=65536):
                if ch:
                    total += len(ch)
                    if total > max_bytes:
                        r.close()
                        return None, ""
                    chunks.append(ch)
            return b"".join(chunks), os.path.basename(fpath)
        except Exception as e:
            write_log(f"Error descargando archivo Telegram: {e}")
            return None, ""

    def send_vip_menu(self, chat_id, intro_text=None):
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚡ Auditoría Express (25 ⭐)", "callback_data": "buy_express"}],
                [{"text": "🛡️ Pase Centinela 30 Días (99 ⭐)", "callback_data": "buy_sentinel"}],
                [{"text": "👑 Investigador Vitalicio (299 ⭐)", "callback_data": "buy_lifetime"}],
                [{"text": "📱 Abrir Tienda en Mini App", "web_app": {"url": f"{self.webapp_url}?v=6.0"}}],
            ]
        }
        body = intro_text or (
            "⭐ <b>CYBERSHIELD SENTINEL VIP</b>\n\n"
            "Elige tu nivel de protección para desbloquear auditorías forenses ilimitadas con Telegram Stars:\n\n"
            "⚡ <b>Auditoría Express (25 ⭐):</b> 1 Certificado forense criptográfico.\n"
            "🛡️ <b>Pase Centinela (99 ⭐):</b> 30 días de auditorías ilimitadas.\n"
            "👑 <b>Investigador Vitalicio (299 ⭐):</b> Acceso permanente sin límites.\n\n"
            "<i>Pulsa un botón para recibir la factura oficial de Telegram Stars al instante.</i>"
        )
        self.send_message(chat_id, body, keyboard)

    def send_api_status(self, chat_id):
        st = engine.get_api_status()
        opt = st.get("optional_api_keys", {})
        free_list = "\n".join(f"• ✅ {html.escape(name)}" for name in st.get("free_live_engines", []))
        vt_line = "✅ <b>Activa</b> (70+ motores en vivo)" if opt.get("VT_API_KEY") else "⚪ <b>No configurada</b> (añade <code>VT_API_KEY</code> en <code>.env</code> o Render)"
        eth_line = "✅ <b>Activa</b>" if opt.get("ETHERSCAN_API_KEY") else "⚪ Opcional (Sourcify + Blockscout activos gratis)"
        ab_line = "✅ <b>Activa</b> (URLhaus / MalwareBazaar API)" if opt.get("ABUSECH_AUTH_KEY") else "⚪ Opcional (OpenPhish / Phishing Army / ScamSniffer activos)"
        tron_line = "✅ <b>Activa</b>" if opt.get("TRON_API_KEY") else "⚪ Opcional (TronGrid + GoPlus TRON activos)"

        msg = (
            "🛰️ <b>ESTADO DE MOTORES FORENSES EN VIVO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Fuentes Gratuitas Activas 24/7:</b>\n"
            f"{free_list}\n\n"
            "<b>Claves Opcionales de Ampliación:</b>\n"
            f"• 🦠 <b>VirusTotal API v3:</b> {vt_line}\n"
            f"• ⛓️ <b>Etherscan v2 API:</b> {eth_line}\n"
            f"• ☣️ <b>Abuse.ch Auth-Key:</b> {ab_line}\n"
            f"• 🔺 <b>TronGrid/Scan API:</b> {tron_line}"
        )
        self.send_message(chat_id, msg)

    def handle_start(self, user_id, chat_id, username):
        get_or_create_user(user_id, username)
        try:
            self.call_api("setChatMenuButton", {
                "chat_id": chat_id,
                "menu_button": {
                    "type": "web_app",
                    "text": "CyberShield 🛡️",
                    "web_app": {"url": f"{self.webapp_url}?v=6.0"},
                },
            })
        except Exception:
            pass

        welcome_text = (
            "🛡️ <b>BIENVENIDO A CYBERSHIELD AI (v2.5 REAL)</b> ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Radar Forense en Tiempo Real &amp; Escudo Anti-Estafas</b>\n\n"
            "Envía cualquier elemento directamente aquí en el chat para auditarlo con APIs y análisis forense real:\n\n"
            "• 🌐 <b>Enlaces / Tiendas / Dominios:</b> DNS Cloudflare 1.1.1.2, VirusTotal, GoPlus Phishing, AlienVault OTX, urlscan.io, OpenPhish, Phishing Army, RDAP y SSL.\n"
            "• 🧾 <b>Comprobantes Bancarios:</b> Envía la <b>foto o documento de imagen</b> y revisamos metadatos EXIF/PNG/XMP, anomalías ELA 16×16 (con mapa visual) y parches.\n"
            "• 🪙 <b>Contratos y Wallets Cripto:</b> Auto-detecta 7 redes EVM, TRON, Solana, BTC y TON; muestra red, <b>tipo de licencia SPDX</b> y <b>denuncias reales</b> (GoPlus + ScamSniffer).\n"
            "• 📁 <b>Archivos / Hashes SHA-256:</b> Envía un PDF/APK/ZIP o hash para verificar cabecera real y reputación.\n"
            "• 💬 <b>Mensajes Sospechosos:</b> Extrae y audita automáticamente los enlaces y wallets ocultos dentro del texto."
        )

        fresh_url = f"{self.webapp_url}?v={int(time.time())}"
        keyboard = {
            "inline_keyboard": [
                [{"text": "🛡️ Abrir Escudo Forense (Mini App)", "web_app": {"url": fresh_url}}],
                [
                    {"text": "🌐 Auditar Link / Hash", "callback_data": "cmd_scan_link"},
                    {"text": "🧾 Auditar Comprobante", "callback_data": "cmd_receipts"},
                ],
                [
                    {"text": "🪙 Auditar Contrato / Wallet", "callback_data": "cmd_crypto"},
                    {"text": "🛰️ APIs en Vivo", "callback_data": "cmd_status"},
                ],
                [{"text": "⭐ Membresía Sentinel VIP", "callback_data": "cmd_vip"}],
            ]
        }
        self.send_message(chat_id, welcome_text, keyboard)

    def _result_keyboard(self):
        return {
            "inline_keyboard": [
                [{"text": "🛡️ Abrir Mini App Interactiva", "web_app": {"url": f"{self.webapp_url}?v=6.0"}}],
                [{"text": "🛰️ Estado APIs", "callback_data": "cmd_status"}, {"text": "⭐ VIP Stars", "callback_data": "cmd_vip"}],
            ]
        }

    def handle_scan_text(self, user_id, chat_id, username, text):
        self.call_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        wait_msg = self.send_message(chat_id, "🛰️ <i>Consultando APIs de inteligencia y blockchain en vivo...</i>")
        wait_id = (wait_msg or {}).get("result", {}).get("message_id")

        res = engine.classify_and_audit_text(text)
        increment_user_scan(user_id, username)
        report_html = engine.format_telegram_html(res)

        if wait_id:
            self.call_api("deleteMessage", {"chat_id": chat_id, "message_id": wait_id})
        self.send_message(chat_id, report_html, self._result_keyboard())

    def handle_receipt_image(self, user_id, chat_id, username, file_id, filename, is_compressed_photo=False):
        self.call_api("sendChatAction", {"chat_id": chat_id, "action": "upload_photo"})
        wait_msg = self.send_message(chat_id, "🔬 <i>Descargando comprobante y ejecutando análisis forense real (EXIF, ELA 16×16, parches y compresión JPEG)...</i>")
        wait_id = (wait_msg or {}).get("result", {}).get("message_id")

        raw_bytes, dl_name = self.download_telegram_file(file_id, max_bytes=15 * 1024 * 1024)
        if not raw_bytes:
            if wait_id:
                self.call_api("deleteMessage", {"chat_id": chat_id, "message_id": wait_id})
            self.send_message(chat_id, "❌ No se pudo descargar la imagen (o supera 15 MB). Intenta reenviarla.")
            return

        tmp_fd, tmp_ela_path = tempfile.mkstemp(prefix="cs_ela_", suffix=".png")
        os.close(tmp_fd)
        try:
            res = engine.audit_bank_receipt(
                image_bytes=raw_bytes,
                filename=filename or dl_name or "comprobante.jpg",
                save_heatmap_path=tmp_ela_path,
            )
            increment_user_scan(user_id, username)
            if is_compressed_photo and not res.get("error"):
                res.setdefault("checks", []).append({
                    "label": "Canal de Envío Telegram",
                    "status": "Enviada como Foto comprimida (para preservar EXIF original, reenvíala como Archivo/Documento)",
                    "ok": True,
                    "severity": "info",
                })

            if wait_id:
                self.call_api("deleteMessage", {"chat_id": chat_id, "message_id": wait_id})

            if os.path.isfile(tmp_ela_path) and not res.get("error"):
                score = res.get("risk_score", 0)
                badge = "🚨" if res.get("verdict_level") == "danger" else "⚠️" if res.get("verdict_level") == "warn" else "✅"
                cap = (
                    f"{badge} <b>Mapa Forense ELA (Original | Nivel de Error)</b>\n"
                    f"📊 Riesgo técnico detectado: <code>{score}%</code>\n"
                    f"<i>Las zonas anormalmente brillantes o con distinta densidad frente al resto del texto indican posible edición.</i>"
                )
                self.send_photo(chat_id, tmp_ela_path, caption=cap)

            report_html = engine.format_telegram_html(res)
            self.send_message(chat_id, report_html, self._result_keyboard())
        finally:
            try:
                if os.path.exists(tmp_ela_path):
                    os.remove(tmp_ela_path)
            except Exception:
                pass

    def handle_document_file(self, user_id, chat_id, username, doc):
        file_id = doc.get("file_id")
        file_name = doc.get("file_name") or "archivo_sin_nombre"
        mime = (doc.get("mime_type") or "").lower()
        ext = os.path.splitext(file_name.lower())[1]

        if mime.startswith("image/") or ext in IMAGE_EXTENSIONS:
            self.handle_receipt_image(user_id, chat_id, username, file_id, file_name, is_compressed_photo=False)
            return

        self.call_api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        wait_msg = self.send_message(chat_id, f"🔬 <i>Calculando SHA-256 e inspeccionando <code>{html.escape(file_name[:50])}</code> en bases de malware...</i>")
        wait_id = (wait_msg or {}).get("result", {}).get("message_id")

        raw_bytes, dl_name = self.download_telegram_file(file_id, max_bytes=20 * 1024 * 1024)
        if wait_id:
            self.call_api("deleteMessage", {"chat_id": chat_id, "message_id": wait_id})

        if not raw_bytes:
            self.send_message(chat_id, "❌ No se pudo descargar el archivo o excede el límite seguro de 20 MB.")
            return

        res = engine.audit_file_or_hash(raw_bytes=raw_bytes, filename=file_name or dl_name)
        increment_user_scan(user_id, username)
        self.send_message(chat_id, engine.format_telegram_html(res), self._result_keyboard())

    def send_stars_invoice(self, chat_id, tier_id):
        invoices = {
            "audit_single": {
                "title": "⚡ CyberShield Auditoría Express",
                "desc": "1 Análisis forense profundo con certificado SHA-256.",
                "stars": 25,
                "payload": "vip_audit_single",
            },
            "sentinel_30": {
                "title": "🛡️ CyberShield Sentinel VIP (30 Días)",
                "desc": "Protección forense total y auditorías ilimitadas por 30 días.",
                "stars": 99,
                "payload": "vip_sentinel_30",
            },
            "forensic_lifetime": {
                "title": "👑 CyberShield Lifetime Investigator",
                "desc": "Acceso VIP permanente de por vida a todas las herramientas forenses.",
                "stars": 299,
                "payload": "vip_lifetime",
            },
        }
        item = invoices.get(tier_id, invoices["sentinel_30"])
        invoice_data = {
            "chat_id": chat_id,
            "title": item["title"],
            "description": item["desc"],
            "payload": f"{item['payload']}_{chat_id}_{int(time.time())}",
            "currency": "XTR",
            "prices": [{"label": item["title"], "amount": item["stars"]}],
            "provider_token": "",
        }
        res = self.call_api("sendInvoice", invoice_data)
        if not res or not res.get("ok"):
            write_log(f"[Error sendInvoice]: {(res or {}).get('description')}")
        else:
            write_log(f"[Factura Stars enviada] Chat: {chat_id}, Plan: {tier_id}")

    def handle_pre_checkout(self, pre_checkout_query):
        pc_id = pre_checkout_query.get("id")
        self.call_api("answerPreCheckoutQuery", {
            "pre_checkout_query_id": pc_id,
            "ok": True,
        })
        write_log(f"[Pre-Checkout CyberShield Aprobado] ID: {pc_id}")

    def handle_inline_query(self, inline_query):
        iq_id = inline_query.get("id")
        query = (inline_query.get("query") or "").strip()

        if not query:
            results = [{
                "type": "article",
                "id": "help_query",
                "title": "🛡️ CyberShield AI: Escáner Forense Real",
                "description": "Escribe un link, wallet/contrato, hash SHA-256 o mensaje sospechoso.",
                "thumb_url": "https://vargasap.github.io/cybershield-ai/avatar.jpg",
                "input_message_content": {
                    "message_text": (
                        "🛡️ <b>CYBERSHIELD AI — RADAR FORENSE EN VIVO</b>\n\n"
                        "Escribe en cualquier chat:\n"
                        "<code>@cybershield_defense_bot enlace-wallet-o-mensaje</code>\n\n"
                        "O abre la Mini App abajo 👇"
                    ),
                    "parse_mode": "HTML",
                },
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🛡️ Abrir CyberShield Mini App", "web_app": {"url": self.webapp_url}}]]
                },
            }]
        else:
            res = engine.classify_and_audit_text(query)
            risk = res.get("risk_score", 0)
            level = res.get("verdict_level", "safe")
            verdict = "🚨 PELIGRO CRÍTICO" if level == "danger" else "⚠️ PRECAUCIÓN" if level == "warn" else "✅ LIMPIO"
            report = engine.format_telegram_html(res)
            results = [{
                "type": "article",
                "id": f"res_{int(time.time())}",
                "title": f"[{verdict}] {query[:32]}",
                "description": f"Riesgo: {risk}% | {res.get('verdict_title', '')[:55]}",
                "thumb_url": "https://vargasap.github.io/cybershield-ai/avatar.jpg",
                "input_message_content": {
                    "message_text": report,
                    "parse_mode": "HTML",
                },
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🛡️ Ver en Mini App", "web_app": {"url": self.webapp_url}}]]
                },
            }]

        self.call_api("answerInlineQuery", {
            "inline_query_id": iq_id,
            "results": results,
            "cache_time": 10,
        })

    def process_update(self, update):
        if "message" in update:
            msg = update["message"]
            user = msg.get("from", {})
            user_id = user.get("id")
            chat_id = msg.get("chat", {}).get("id")
            username = user.get("username", "")

            if not chat_id:
                return

            # Pago exitoso de Telegram Stars
            if "successful_payment" in msg:
                sp = msg["successful_payment"]
                stars = sp.get("total_amount", 0)
                payload = sp.get("invoice_payload", "")
                write_log(f"[Pago Exitoso Stars] Chat: {chat_id}, Stars: {stars}, Payload: {payload}")

                db = load_users()
                uid = str(user_id)
                if uid not in db:
                    db[uid] = {
                        "username": username or uid,
                        "scans_count": 0,
                        "daily_scans_left": 9999,
                        "first_seen": datetime.utcnow().isoformat(),
                    }
                db[uid]["is_vip"] = True
                db[uid]["vip_tier"] = "Sentinel Lifetime" if "lifetime" in payload else ("Express 25★" if "single" in payload else "Sentinel 30D")
                db[uid]["vip_activated_at"] = datetime.utcnow().isoformat()
                save_users(db)

                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🛡️ Abrir Escudo Forense VIP", "web_app": {"url": self.webapp_url}}]
                    ]
                }
                self.send_message(
                    chat_id,
                    f"🎉 <b>¡PAGO CONFIRMADO CON ÉXITO!</b>\n\n"
                    f"⭐ Has activado tu membresía con <b>{stars} Telegram Stars</b>.\n\n"
                    f"🛡️ <b>Beneficios VIP habilitados:</b>\n"
                    f"• Auditorías forenses ilimitadas sin restricciones\n"
                    f"• Prioridad máxima en verificación de contratos y dApps\n"
                    f"• Certificados forenses firmados con Hash SHA-256\n\n"
                    f"<i>¡Gracias por utilizar CyberShield AI Sentinel!</i>",
                    keyboard,
                )
                return

            # Capturas de comprobante enviadas como Foto
            if msg.get("photo"):
                if not check_rate_limit(user_id):
                    self.send_message(chat_id, "⏳ Espera unos segundos antes de enviar otro análisis.")
                    return
                best_photo = msg["photo"][-1]
                self.handle_receipt_image(
                    user_id, chat_id, username,
                    best_photo.get("file_id"),
                    f"comprobante_{msg.get('message_id', int(time.time()))}.jpg",
                    is_compressed_photo=True,
                )
                return

            # Archivos o comprobantes enviados como Documento
            if msg.get("document"):
                if not check_rate_limit(user_id):
                    self.send_message(chat_id, "⏳ Espera unos segundos antes de enviar otro archivo.")
                    return
                self.handle_document_file(user_id, chat_id, username, msg["document"])
                return

            text = (msg.get("text") or "").strip()
            if not text:
                return

            if text.startswith("/start"):
                parts = text.split()
                if len(parts) > 1 and "vip" in parts[1]:
                    self.send_vip_menu(chat_id)
                elif len(parts) > 1 and "web_limit" in parts[1]:
                    fresh_url = f"{self.webapp_url}?v={int(time.time())}"
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🛡️ Abrir Escudo Forense Ilimitado", "web_app": {"url": fresh_url}}],
                            [{"text": "⭐ Ver Planes Sentinel VIP", "callback_data": "cmd_vip"}],
                        ]
                    }
                    self.send_message(
                        chat_id,
                        "🛡️ <b>¡BIENVENIDO A CYBERSHIELD AI EN TELEGRAM!</b> ⚡\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "Aquí tienes acceso completo y en vivo a todas las auditorías reales:\n\n"
                        "• 🌐 Pega cualquier enlace o hash para auditarlo.\n"
                        "• 🧾 Envía la foto o archivo de cualquier comprobante bancario.\n"
                        "• 🪙 Pega cualquier contrato o wallet (EVM, TRON, Solana, BTC, TON).\n"
                        "• 💬 Reenvía mensajes sospechosos para extraer sus trampas.",
                        keyboard,
                    )
                else:
                    self.handle_start(user_id, chat_id, username)
            elif text.startswith("/ayuda") or text.startswith("/help"):
                self.send_message(
                    chat_id,
                    "🛡️ <b>Comandos y Uso de CyberShield AI:</b>\n\n"
                    "• 🌐 Envía un link o dominio → Auditoría VirusTotal + Cloudflare 1.1.1.2 + OTX + OpenPhish + RDAP + SSL.\n"
                    "• 🧾 Envía una <b>foto o archivo de imagen</b> → Forense real de comprobantes (EXIF/XMP + ELA 16×16 + parches).\n"
                    "• 🪙 Envía una wallet o contrato (<code>0x...</code>, <code>T...</code>, <code>EQ...</code>, Solana, BTC) → Red, Licencia SPDX y Denuncias.\n"
                    "• 📁 Envía un archivo o hash SHA-256 → Inspección binaria + reputación.\n"
                    "• /estado — Muestra motores API activos en tiempo real.\n"
                    "• /vip — Membresías Sentinel con Telegram Stars.\n"
                    "• /start — Menú principal y Mini App.",
                )
            elif text.startswith("/estado") or text.startswith("/apis") or text.startswith("/status"):
                self.send_api_status(chat_id)
            elif text.startswith("/vip") or text.startswith("/tienda"):
                self.send_vip_menu(chat_id)
            else:
                if not check_rate_limit(user_id):
                    self.send_message(chat_id, "⏳ Límite temporal alcanzado. Espera unos segundos entre escaneos.")
                    return
                self.handle_scan_text(user_id, chat_id, username, text)

        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            if cb_id:
                self.call_api("answerCallbackQuery", {"callback_query_id": cb_id})
            chat_id = cb.get("message", {}).get("chat", {}).get("id")
            data = cb.get("data", "")
            if not chat_id:
                return

            if data == "cmd_scan_link":
                self.send_message(
                    chat_id,
                    "🌐 <b>Auditoría de Enlaces y Hashes:</b>\n"
                    "Pega aquí el enlace sospechoso, dominio o hash SHA-256 para escanearlo en VirusTotal, Cloudflare 1.1.1.2, OpenPhish, OTX, urlscan.io y RDAP.",
                )
            elif data == "cmd_scan_msg":
                self.send_message(
                    chat_id,
                    "💬 <b>Detector de Mensajes Fraudulentos:</b>\n"
                    "Reenvía o pega el texto completo aquí para detectar patrones Ponzi y auditar los enlaces/wallets incrustados.",
                )
            elif data == "cmd_receipts":
                self.send_message(
                    chat_id,
                    "🧾 <b>Auditoría Forense de Comprobantes Bancarios:</b>\n\n"
                    "📸 <b>Envía la imagen aquí mismo en este chat</b> (preferiblemente como <i>Archivo/Documento</i> para conservar sus metadatos EXIF/PNG intactos).\n\n"
                    "Ejecutaremos análisis EXIF/XMP/Photoshop, mapa visual de <b>Error Level Analysis (ELA 16×16)</b> y detector de parches sobre montos/fechas.",
                )
            elif data == "cmd_crypto":
                self.send_message(
                    chat_id,
                    "🪙 <b>Auditoría Multi-Red de Contratos y Wallets:</b>\n\n"
                    "Pega cualquier dirección <b>EVM (ETH, BSC, Polygon, Arbitrum, Base, Optimism, Avalanche)</b>, <b>TRON</b>, <b>Solana</b>, <b>Bitcoin</b> o <b>TON</b>.\n"
                    "Verificamos si es Wallet o Smart Contract, su <b>Tipo de Licencia SPDX</b>, impuestos Honeypot y <b>denuncias reales</b> (GoPlus + ScamSniffer).",
                )
            elif data == "cmd_status":
                self.send_api_status(chat_id)
            elif data == "cmd_vip":
                self.send_vip_menu(chat_id)
            elif data == "buy_express":
                self.send_stars_invoice(chat_id, "audit_single")
            elif data == "buy_sentinel":
                self.send_stars_invoice(chat_id, "sentinel_30")
            elif data == "buy_lifetime":
                self.send_stars_invoice(chat_id, "forensic_lifetime")

    def run(self):
        write_log("Iniciando daemon de CyberShield AI v2.5 (Motores Reales)...")
        if not self.token:
            write_log("AVISO: CyberShield AI no tiene BOT_TOKEN_SHIELD asignado aún. Esperando configuración de token.")
            while True:
                time.sleep(30)
                cfg = load_config()
                if cfg.get("bot_token"):
                    self.token = cfg["bot_token"]
                    self.base_url = f"https://api.telegram.org/bot{self.token}"
                    break

        me = self.call_api("getMe")
        if me and me.get("ok"):
            write_log(f"Bot autenticado: @{me['result']['username']} (ID: {me['result']['id']})")
            try:
                self.call_api("setChatMenuButton", {
                    "menu_button": {
                        "type": "web_app",
                        "text": "CyberShield 🛡️",
                        "web_app": {"url": f"{self.webapp_url}?v=6.0"},
                    }
                })
            except Exception as e:
                write_log(f"Error configurando menu button: {e}")

        while True:
            try:
                url = f"{self.base_url}/getUpdates?offset={self.last_update_id + 1}&timeout=20"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        for u in data.get("result", []):
                            self.last_update_id = u["update_id"]
                            try:
                                if "pre_checkout_query" in u:
                                    self.handle_pre_checkout(u["pre_checkout_query"])
                                    continue
                                if "inline_query" in u:
                                    self.handle_inline_query(u["inline_query"])
                                    continue
                                self.process_update(u)
                            except Exception as ex:
                                write_log(f"Error procesando update: {ex}")
            except Exception:
                time.sleep(3)


if __name__ == "__main__":
    cfg = load_config()
    bot = CyberShieldBot(cfg)
    bot.run()

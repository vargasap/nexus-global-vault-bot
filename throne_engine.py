#!/usr/bin/env python3
"""
The $1.99 Throne Engine — Persistent Real-Time SQLite WAL Store + SSE EventBus + Telegram Stars Invoice Creator.

Powers the live global battle for #1:
- Visitors react, click promo links, and chat in real time for free.
- Paying 100 Stars (~$1.99) dethrones the current King #1 immediately, displays the
  buyer's name/message/link across Web, Telegram Mini App & Live Stream overlays,
  notifies SSE subscribers, and triggers an instant revenge alert for the previous King.
"""

from __future__ import annotations

import json
import os
import queue
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "throne_db.sqlite")

THRONE_TIERS: Dict[str, Dict[str, Any]] = {
    "king_100": {
        "id": "king_100",
        "title": "👑 Tomar el Trono #1 ($1.99)",
        "description": "Destrona al Rey actual al instante, fija tu nombre, mensaje y enlace en pantalla global en vivo.",
        "stars": 100,
        "usd_hint": "$1.99",
        "shield_seconds": 0,
        "pin_seconds": 0,
    },
    "shield_250": {
        "id": "shield_250",
        "title": "🛡️ Trono Blindado 15 Min ($4.99)",
        "description": "Toma el Trono #1 con escudo anti-derrocamiento durante 15 minutos seguidos.",
        "stars": 250,
        "usd_hint": "$4.99",
        "shield_seconds": 900,
        "pin_seconds": 0,
    },
    "pin_50": {
        "id": "pin_50",
        "title": "💎 Pin VIP en el Muro 24h ($0.99)",
        "description": "Destaca tu perfil o negocio en la franja VIP del muro en vivo durante 24 horas.",
        "stars": 50,
        "usd_hint": "$0.99",
        "shield_seconds": 0,
        "pin_seconds": 86400,
    },
}

VALID_THEMES = {"gold", "cyber", "inferno", "diamond"}
VALID_REACTIONS = {"fire", "crown", "bomb", "rocket"}
AVATAR_CHOICES = ["👑", "🔥", "⚡", "💎", "🦁", "🐉", "🚀", "🛸", "🦊", "🦅", "💰", "🎯"]


# ---------------------------------------------------------------------------
# EventBus for Real-Time Server-Sent Events (SSE)
# ---------------------------------------------------------------------------

class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: List[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def online_count(self) -> int:
        with self._lock:
            return max(1, len(self._subs))

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        msg = json.dumps({"event": event_type, "data": data, "ts": int(time.time())}, ensure_ascii=False)
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait((event_type, msg))
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait((event_type, msg))
                except Exception:
                    pass


BUS = EventBus()


# ---------------------------------------------------------------------------
# In-Memory Rate Limiter
# ---------------------------------------------------------------------------

_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, List[float]] = {}


def check_rate_limit(bucket_key: str, max_hits: int, window_sec: float) -> bool:
    now = time.time()
    with _RATE_LOCK:
        arr = [t for t in _RATE_BUCKETS.get(bucket_key, []) if now - t < window_sec]
        if len(arr) >= max_hits:
            _RATE_BUCKETS[bucket_key] = arr
            return False
        arr.append(now)
        _RATE_BUCKETS[bucket_key] = arr
        return True


# ---------------------------------------------------------------------------
# Strict Input & URL Sanitization
# ---------------------------------------------------------------------------

def sanitize_text(val: Any, max_len: int, default: str = "") -> str:
    txt = str(val or "").replace("\r", " ").replace("\n", " ").strip()
    txt = re.sub(r"\s+", " ", txt)
    if not txt:
        return default
    return txt[:max_len]


def sanitize_promo_url(raw: Any) -> Tuple[str, Optional[str]]:
    """
    Normalizes and strictly validates a promotional link.
    Allows: https://..., http://..., @telegram_handle, or clean domain name.
    Rejects javascript:, data:, vbscript:, file:, etc.
    Returns (normalized_url, error_message).
    """
    val = str(raw or "").strip()
    if not val:
        return "", None

    lower = val.lower()
    if re.match(r"^(javascript|data|vbscript|file|blob|about):", lower):
        return "", "Esquema de URL no permitido por seguridad."
    if any(ch in val for ch in (" ", "<", ">", '"', "'", "\n", "\r", "\t")):
        return "", "El enlace contiene espacios o caracteres inválidos."

    # Telegram handle @user
    if val.startswith("@"):
        handle = val[1:].strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", handle):
            return "", "Usuario de Telegram inválido (usa 4-32 letras, números o _)."
        return f"https://t.me/{handle}", None

    if not re.match(r"^https?://", lower):
        if "." not in val:
            return "", "Ingresa un enlace válido (ej. https://tiktok.com/@tuusuario o @tu_telegram)."
        val = "https://" + val

    if not re.match(r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?(?:/[^\s<>\"']*)?$", val):
        return "", "Formato de enlace web inválido."
    if len(val) > 220:
        return "", "El enlace excede los 220 caracteres."
    return val, None


# ---------------------------------------------------------------------------
# SQLite Schema & Connection Helper
# ---------------------------------------------------------------------------

_INIT_DONE: Dict[str, bool] = {}
_INIT_LOCK = threading.Lock()


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    init_db(path)
    conn = sqlite3.connect(path, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    path = db_path or DEFAULT_DB_PATH
    with _INIT_LOCK:
        if _INIT_DONE.get(path):
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = sqlite3.connect(path, timeout=15.0)
        try:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    telegram_user_id INTEGER DEFAULT 0,
                    message TEXT NOT NULL,
                    promo_url TEXT DEFAULT '',
                    promo_label TEXT DEFAULT '',
                    theme TEXT DEFAULT 'gold',
                    avatar_emoji TEXT DEFAULT '👑',
                    status TEXT NOT NULL DEFAULT 'pending',
                    invoice_url TEXT DEFAULT '',
                    external_checkout_url TEXT DEFAULT '',
                    created_at INTEGER NOT NULL,
                    paid_at INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS throne_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE NOT NULL,
                    tier TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    telegram_user_id INTEGER DEFAULT 0,
                    message TEXT NOT NULL,
                    promo_url TEXT DEFAULT '',
                    promo_label TEXT DEFAULT '',
                    theme TEXT DEFAULT 'gold',
                    avatar_emoji TEXT DEFAULT '👑',
                    stars_paid INTEGER NOT NULL,
                    started_at INTEGER NOT NULL,
                    ended_at INTEGER DEFAULT 0,
                    shield_until INTEGER DEFAULT 0,
                    is_current_king INTEGER DEFAULT 0,
                    is_pinned_until INTEGER DEFAULT 0,
                    clicks_count INTEGER DEFAULT 0,
                    reactions_fire INTEGER DEFAULT 0,
                    reactions_crown INTEGER DEFAULT 0,
                    reactions_bomb INTEGER DEFAULT 0,
                    reactions_rocket INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS shoutbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT NOT NULL,
                    text TEXT NOT NULL,
                    is_system INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO meta (key, value) VALUES
                    ('total_stars', 0),
                    ('total_takeovers', 0),
                    ('total_clicks', 0),
                    ('total_reactions', 0);
                """
            )
            conn.commit()
            _INIT_DONE[path] = True
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def _gen_order_id() -> str:
    return "TRN" + secrets.token_hex(3).upper()


def _create_telegram_invoice_link(
    bot_token: str,
    order_id: str,
    tier_cfg: Dict[str, Any],
    display_name: str,
) -> Optional[str]:
    if not bot_token:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/createInvoiceLink",
            json={
                "title": tier_cfg["title"][:32],
                "description": f"{tier_cfg['description']} | Para: {display_name[:28]}"[:255],
                "payload": f"throne_{order_id}",
                "provider_token": "",
                "currency": "XTR",
                "prices": [{"label": tier_cfg["title"][:32], "amount": int(tier_cfg["stars"])}],
            },
            timeout=10,
        )
        data = r.json()
        if data.get("ok") and data.get("result"):
            return str(data["result"])
    except Exception:
        pass
    return None


def create_pending_order(
    payload_data: Dict[str, Any],
    bot_token: str = "",
    bot_username: str = "nexus_global_vault_bot",
    external_checkout_base: str = "",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    tier = str(payload_data.get("tier") or "king_100").strip()
    if tier not in THRONE_TIERS:
        return {"ok": False, "error": "Plan seleccionado inválido."}

    tier_cfg = THRONE_TIERS[tier]
    display_name = sanitize_text(payload_data.get("display_name"), 36)
    if len(display_name) < 2:
        return {"ok": False, "error": "Escribe tu nombre o apodo (mínimo 2 caracteres)."}

    message = sanitize_text(payload_data.get("message"), 130, default="¡Nuevo Rey en el Trono!")
    promo_url, url_err = sanitize_promo_url(payload_data.get("promo_url", ""))
    if url_err:
        return {"ok": False, "error": url_err}

    promo_label = sanitize_text(payload_data.get("promo_label"), 28, default=("Visitar enlace" if promo_url else ""))
    theme = str(payload_data.get("theme") or "gold").strip().lower()
    if theme not in VALID_THEMES:
        theme = "gold"

    avatar = sanitize_text(payload_data.get("avatar_emoji"), 8, default="👑")
    if avatar not in AVATAR_CHOICES:
        avatar = "👑"

    username = sanitize_text(payload_data.get("username"), 36, default="")
    tg_uid = int(payload_data.get("telegram_user_id") or 0)
    now = int(time.time())

    conn = _connect(db_path)
    try:
        if tier in ("king_100", "shield_250"):
            king = conn.execute(
                "SELECT display_name, shield_until FROM throne_entries WHERE is_current_king=1 LIMIT 1"
            ).fetchone()
            if king and int(king["shield_until"] or 0) > now:
                rem = int(king["shield_until"]) - now
                return {
                    "ok": False,
                    "shielded": True,
                    "shield_remaining": rem,
                    "error": f"🛡️ El Rey actual ({king['display_name']}) tiene Escudo Blindado activo por {rem}s más.",
                }

        order_id = _gen_order_id()
        invoice_url = _create_telegram_invoice_link(bot_token, order_id, tier_cfg, display_name) or ""
        ext_url = ""
        if external_checkout_base:
            sep = "&" if "?" in external_checkout_base else "?"
            ext_url = f"{external_checkout_base}{sep}order_id={order_id}&tier={tier}"

        conn.execute(
            """
            INSERT INTO orders (
                order_id, tier, stars_amount, display_name, username, telegram_user_id,
                message, promo_url, promo_label, theme, avatar_emoji, status,
                invoice_url, external_checkout_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                order_id, tier, int(tier_cfg["stars"]), display_name, username, tg_uid,
                message, promo_url, promo_label, theme, avatar,
                invoice_url, ext_url, now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "order_id": order_id,
        "tier": tier,
        "stars": int(tier_cfg["stars"]),
        "usd_hint": tier_cfg["usd_hint"],
        "invoice_url": invoice_url,
        "tg_deeplink": f"https://t.me/{bot_username}?start=throne_{order_id}",
        "external_checkout_url": ext_url,
    }


def get_order(order_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    clean_id = sanitize_text(order_id, 24).upper()
    if not clean_id:
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM orders WHERE order_id=?", (clean_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row, now: int) -> Dict[str, Any]:
    d = dict(row)
    started = int(d.get("started_at") or now)
    ended = int(d.get("ended_at") or 0)
    is_king = bool(d.get("is_current_king"))
    if is_king:
        d["reign_seconds"] = max(0, now - started)
    elif ended > started:
        d["reign_seconds"] = ended - started
    else:
        d["reign_seconds"] = 0
    shield_until = int(d.get("shield_until") or 0)
    d["shield_remaining"] = max(0, shield_until - now) if is_king and shield_until > now else 0
    d["is_current_king"] = is_king
    return d


def activate_paid_order(
    order_id: str,
    payer_user_id: int = 0,
    payer_username: str = "",
    stars_paid: Optional[int] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically & idempotently activates a paid order:
    - For king_100 / shield_250: dethrones previous king cleanly & crowns the new King #1.
    - For pin_50: adds a 24h VIP spotlight pin without dethroning the current King.
    Publishes real-time SSE event and returns previous_king metadata for revenge notifications.
    """
    clean_id = sanitize_text(order_id, 24).upper()
    now = int(time.time())
    conn = _connect(db_path)
    previous_king_info: Optional[Dict[str, Any]] = None
    new_entry_dict: Optional[Dict[str, Any]] = None

    try:
        conn.execute("BEGIN IMMEDIATE;")
        order = conn.execute("SELECT * FROM orders WHERE order_id=?", (clean_id,)).fetchone()
        if not order:
            conn.rollback()
            return {"ok": False, "error": "Orden no encontrada"}

        if order["status"] == "paid":
            existing = conn.execute("SELECT * FROM throne_entries WHERE order_id=?", (clean_id,)).fetchone()
            conn.rollback()
            return {
                "ok": True,
                "already_paid": True,
                "entry": _row_to_entry(existing, now) if existing else None,
                "previous_king": None,
            }

        tier = order["tier"]
        tier_cfg = THRONE_TIERS.get(tier, THRONE_TIERS["king_100"])
        actual_stars = int(stars_paid if stars_paid is not None else order["stars_amount"])
        final_uid = int(payer_user_id or order["telegram_user_id"] or 0)
        final_uname = sanitize_text(payer_username or order["username"], 36)

        conn.execute(
            "UPDATE orders SET status='paid', paid_at=?, telegram_user_id=?, username=? WHERE order_id=?",
            (now, final_uid, final_uname, clean_id),
        )

        is_takeover = tier in ("king_100", "shield_250")
        shield_until = (now + int(tier_cfg["shield_seconds"])) if tier_cfg["shield_seconds"] > 0 else 0
        pinned_until = (now + int(tier_cfg["pin_seconds"])) if tier_cfg["pin_seconds"] > 0 else 0

        if is_takeover:
            prev = conn.execute(
                "SELECT * FROM throne_entries WHERE is_current_king=1 LIMIT 1"
            ).fetchone()
            if prev:
                previous_king_info = {
                    "id": prev["id"],
                    "display_name": prev["display_name"],
                    "username": prev["username"],
                    "telegram_user_id": int(prev["telegram_user_id"] or 0),
                    "reign_seconds": max(0, now - int(prev["started_at"] or now)),
                }
                conn.execute(
                    "UPDATE throne_entries SET is_current_king=0, ended_at=? WHERE id=?",
                    (now, prev["id"]),
                )

            conn.execute(
                """
                INSERT INTO throne_entries (
                    order_id, tier, display_name, username, telegram_user_id, message,
                    promo_url, promo_label, theme, avatar_emoji, stars_paid,
                    started_at, ended_at, shield_until, is_current_king, is_pinned_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1, 0)
                """,
                (
                    clean_id, tier, order["display_name"], final_uname, final_uid, order["message"],
                    order["promo_url"], order["promo_label"], order["theme"], order["avatar_emoji"],
                    actual_stars, now, shield_until,
                ),
            )
            sys_msg = (
                f"👑 {order['display_name']} destronó a {previous_king_info['display_name']}!"
                if previous_king_info
                else f"👑 ¡{order['display_name']} tomó el Trono #1!"
            )
            conn.execute(
                "INSERT INTO shoutbox (author, text, is_system, created_at) VALUES (?, ?, 1, ?)",
                ("SISTEMA", sys_msg[:120], now),
            )
            conn.execute("UPDATE meta SET value = value + 1 WHERE key='total_takeovers'")
        else:
            # VIP 24h pin without dethroning current King
            conn.execute(
                """
                INSERT INTO throne_entries (
                    order_id, tier, display_name, username, telegram_user_id, message,
                    promo_url, promo_label, theme, avatar_emoji, stars_paid,
                    started_at, ended_at, shield_until, is_current_king, is_pinned_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (
                    clean_id, tier, order["display_name"], final_uname, final_uid, order["message"],
                    order["promo_url"], order["promo_label"], order["theme"], order["avatar_emoji"],
                    actual_stars, now, now, pinned_until,
                ),
            )
            conn.execute(
                "INSERT INTO shoutbox (author, text, is_system, created_at) VALUES (?, ?, 1, ?)",
                ("SISTEMA", f"💎 {order['display_name']} fijó un Pin VIP por 24h en el muro.", now),
            )

        conn.execute("UPDATE meta SET value = value + ? WHERE key='total_stars'", (actual_stars,))
        conn.execute("DELETE FROM shoutbox WHERE id NOT IN (SELECT id FROM shoutbox ORDER BY id DESC LIMIT 60)")

        inserted = conn.execute("SELECT * FROM throne_entries WHERE order_id=?", (clean_id,)).fetchone()
        new_entry_dict = _row_to_entry(inserted, now) if inserted else None
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if new_entry_dict:
        BUS.publish(
            "takeover" if new_entry_dict["is_current_king"] else "pin",
            {"entry": new_entry_dict, "previous_king": previous_king_info},
        )

    return {
        "ok": True,
        "already_paid": False,
        "entry": new_entry_dict,
        "previous_king": previous_king_info,
    }


def record_reaction(entry_id: int, kind: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    if kind not in VALID_REACTIONS:
        return {"ok": False, "error": "Reacción inválida"}
    col = f"reactions_{kind}"
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT id FROM throne_entries WHERE id=?", (int(entry_id),)).fetchone()
        if not row:
            return {"ok": False, "error": "Entrada no encontrada"}
        conn.execute(f"UPDATE throne_entries SET {col} = {col} + 1 WHERE id=?", (int(entry_id),))
        conn.execute("UPDATE meta SET value = value + 1 WHERE key='total_reactions'")
        updated = conn.execute(
            "SELECT id, reactions_fire, reactions_crown, reactions_bomb, reactions_rocket FROM throne_entries WHERE id=?",
            (int(entry_id),),
        ).fetchone()
        conn.commit()
        res = dict(updated)
    finally:
        conn.close()

    BUS.publish("reaction", {"entry_id": int(entry_id), "kind": kind, "counts": res})
    return {"ok": True, "counts": res}


def record_click(entry_id: int, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT id, promo_url FROM throne_entries WHERE id=?", (int(entry_id),)).fetchone()
        if not row:
            return {"ok": False, "error": "Entrada no encontrada"}
        conn.execute("UPDATE throne_entries SET clicks_count = clicks_count + 1 WHERE id=?", (int(entry_id),))
        conn.execute("UPDATE meta SET value = value + 1 WHERE key='total_clicks'")
        updated = conn.execute("SELECT id, clicks_count FROM throne_entries WHERE id=?", (int(entry_id),)).fetchone()
        conn.commit()
        res = dict(updated)
    finally:
        conn.close()

    BUS.publish("click", res)
    return {"ok": True, **res}


def post_shout(author: Any, text: Any, db_path: Optional[str] = None) -> Dict[str, Any]:
    clean_author = sanitize_text(author, 24, default="Visitante")
    clean_text = sanitize_text(text, 100)
    if len(clean_text) < 2:
        return {"ok": False, "error": "Escribe un mensaje corto (mín. 2 caracteres)."}
    now = int(time.time())
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO shoutbox (author, text, is_system, created_at) VALUES (?, ?, 0, ?)",
            (clean_author, clean_text, now),
        )
        sid = cur.lastrowid
        conn.execute("DELETE FROM shoutbox WHERE id NOT IN (SELECT id FROM shoutbox ORDER BY id DESC LIMIT 60)")
        conn.commit()
    finally:
        conn.close()

    item = {"id": sid, "author": clean_author, "text": clean_text, "is_system": False, "created_at": now}
    BUS.publish("shout", item)
    return {"ok": True, "shout": item}


def get_live_state(db_path: Optional[str] = None) -> Dict[str, Any]:
    now = int(time.time())
    conn = _connect(db_path)
    try:
        king_row = conn.execute(
            "SELECT * FROM throne_entries WHERE is_current_king=1 LIMIT 1"
        ).fetchone()
        current_king = _row_to_entry(king_row, now) if king_row else None

        pin_rows = conn.execute(
            "SELECT * FROM throne_entries WHERE is_pinned_until > ? ORDER BY id DESC LIMIT 12",
            (now,),
        ).fetchall()
        vip_pins = [_row_to_entry(r, now) for r in pin_rows]

        hist_rows = conn.execute(
            "SELECT * FROM throne_entries WHERE tier IN ('king_100', 'shield_250') ORDER BY id DESC LIMIT 20"
        ).fetchall()
        recent_kings = [_row_to_entry(r, now) for r in hist_rows]

        all_kings = conn.execute(
            "SELECT * FROM throne_entries WHERE tier IN ('king_100', 'shield_250')"
        ).fetchall()
        hall = sorted(
            [_row_to_entry(r, now) for r in all_kings],
            key=lambda x: (
                x["reign_seconds"] + x["clicks_count"] * 25 + x["reactions_crown"] * 10,
                x["stars_paid"],
            ),
            reverse=True,
        )[:10]

        shout_rows = conn.execute(
            "SELECT id, author, text, is_system, created_at FROM shoutbox ORDER BY id DESC LIMIT 25"
        ).fetchall()
        shouts = [
            {
                "id": r["id"],
                "author": r["author"],
                "text": r["text"],
                "is_system": bool(r["is_system"]),
                "created_at": r["created_at"],
            }
            for r in reversed(shout_rows)
        ]

        meta_rows = conn.execute("SELECT key, value FROM meta").fetchall()
        stats = {r["key"]: int(r["value"]) for r in meta_rows}
        stats["online_viewers"] = BUS.online_count()
    finally:
        conn.close()

    return {
        "ok": True,
        "server_time": now,
        "current_king": current_king,
        "vip_pins": vip_pins,
        "recent_kings": recent_kings,
        "hall_of_fame": hall,
        "shouts": shouts,
        "stats": stats,
        "tiers": list(THRONE_TIERS.values()),
    }

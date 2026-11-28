#!/usr/bin/env python3
"""
The $1.99 Throne — Standalone Threading HTTP + SSE Server & Reusable Route Handler.

Serves:
  GET  / , /throne , /throne.html     -> web_hub/throne.html
  GET  /api/throne/state               -> Live JSON state (King #1, pins, Hall of Fame, stats)
  GET  /api/throne/events              -> Real-time Server-Sent Events stream (SSE)
  POST /api/throne/order               -> Creates order + real Telegram Stars createInvoiceLink
  POST /api/throne/react               -> Increments live emoji reaction & broadcasts SSE
  POST /api/throne/click               -> Tracks promo link click & broadcasts SSE
  POST /api/throne/shout               -> Posts live shoutbox message & broadcasts SSE
  GET  /healthz                        -> Service health check
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import queue
import re
import threading
import time
from typing import Optional, Tuple
import requests

import throne_engine as te

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_HTML_PATH = os.path.join(BASE_DIR, "web_hub", "throne.html")
MAX_POST_BYTES = 128 * 1024

_BOT_CACHE_LOCK = threading.Lock()
_BOT_IDENTITY: Optional[Tuple[str, str]] = None


def _load_env_key(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if val:
        return val
    for folder in (BASE_DIR, os.path.join(BASE_DIR, "bots")):
        env_p = os.path.join(folder, ".env")
        if os.path.isfile(env_p):
            try:
                with open(env_p, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            cleaned = v.strip().strip('"').strip("'")
                            if cleaned:
                                return cleaned
            except Exception:
                pass
    return ""


def resolve_throne_bot() -> Tuple[str, str]:
    global _BOT_IDENTITY
    with _BOT_CACHE_LOCK:
        if _BOT_IDENTITY and _BOT_IDENTITY[0]:
            return _BOT_IDENTITY

        token = (
            _load_env_key("BOT_TOKEN_THRONE")
            or _load_env_key("BOT_TOKEN")
            or _load_env_key("BOT_TOKEN_VAULT")
        )
        if not token:
            cfg_p = os.path.join(BASE_DIR, "config.json")
            if os.path.isfile(cfg_p):
                try:
                    cfg = json.load(open(cfg_p, "r", encoding="utf-8"))
                    token = str(cfg.get("bot_token") or "").strip()
                except Exception:
                    pass

        username = "nexus_global_vault_bot"
        if token:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=6).json()
                if r.get("ok") and r.get("result", {}).get("username"):
                    username = str(r["result"]["username"])
            except Exception:
                pass

        _BOT_IDENTITY = (token, username)
        return _BOT_IDENTITY


def send_cors_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def send_json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    send_cors_headers(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _client_ip(handler: BaseHTTPRequestHandler) -> str:
    xff = handler.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return xff or (handler.client_address[0] if handler.client_address else "unknown")


def handle_throne_get(handler: BaseHTTPRequestHandler, path: str, db_path: Optional[str] = None) -> bool:
    """
    Handles Throne GET routes. Returns True if path belonged to Throne, False otherwise.
    """
    if path in ("/throne", "/throne/", "/throne.html"):
        if not os.path.isfile(WEB_HTML_PATH):
            send_json(handler, 404, {"ok": False, "error": "web_hub/throne.html no encontrado"})
            return True
        with open(WEB_HTML_PATH, "rb") as f:
            raw = f.read()
        handler.send_response(200)
        send_cors_headers(handler)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)
        return True

    if path == "/api/throne/state":
        state = te.get_live_state(db_path=db_path)
        _, uname = resolve_throne_bot()
        state["bot_username"] = uname
        send_json(handler, 200, state)
        return True

    if path == "/api/throne/events":
        handler.send_response(200)
        send_cors_headers(handler)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("X-Accel-Buffering", "no")
        handler.end_headers()

        sub_q = te.BUS.subscribe()
        try:
            init_payload = json.dumps({"event": "state", "data": te.get_live_state(db_path=db_path)}, ensure_ascii=False)
            handler.wfile.write(f"event: state\ndata: {init_payload}\n\n".encode("utf-8"))
            handler.wfile.flush()
            while True:
                try:
                    ev_type, ev_json = sub_q.get(timeout=15.0)
                    chunk = f"event: {ev_type}\ndata: {ev_json}\n\n".encode("utf-8")
                except queue.Empty:
                    chunk = b": ping\n\n"
                handler.wfile.write(chunk)
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            te.BUS.unsubscribe(sub_q)
        return True

    return False


def handle_throne_post(handler: BaseHTTPRequestHandler, path: str, db_path: Optional[str] = None) -> bool:
    if not path.startswith("/api/throne/"):
        return False

    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    if length <= 0 or length > MAX_POST_BYTES:
        send_json(handler, 400, {"ok": False, "error": "Cuerpo vacío o excede tamaño máximo"})
        return True

    try:
        body = json.loads(handler.rfile.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Objeto JSON esperado")
    except Exception:
        send_json(handler, 400, {"ok": False, "error": "JSON inválido"})
        return True

    ip = _client_ip(handler)

    if path == "/api/throne/order":
        if not te.check_rate_limit(f"ord:{ip}", 8, 60):
            send_json(handler, 429, {"ok": False, "error": "Demasiadas órdenes en 1 minuto. Espera unos segundos."})
            return True
        tok, uname = resolve_throne_bot()
        ext_base = _load_env_key("THRONE_EXTERNAL_CHECKOUT_URL")
        res = te.create_pending_order(
            body,
            bot_token=tok,
            bot_username=uname,
            external_checkout_base=ext_base,
            db_path=db_path,
        )
        code = 200 if res.get("ok") else (409 if res.get("shielded") else 400)
        send_json(handler, code, res)
        return True

    if path == "/api/throne/react":
        if not te.check_rate_limit(f"rx:{ip}", 25, 10):
            send_json(handler, 429, {"ok": False, "error": "Límite de reacciones alcanzado por unos segundos"})
            return True
        try:
            entry_id = int(body.get("entry_id") or 0)
        except Exception:
            entry_id = 0
        kind = str(body.get("kind") or "").strip().lower()
        res = te.record_reaction(entry_id, kind, db_path=db_path)
        send_json(handler, 200 if res.get("ok") else 400, res)
        return True

    if path == "/api/throne/click":
        if not te.check_rate_limit(f"ck:{ip}", 12, 30):
            send_json(handler, 200, {"ok": True, "throttled": True})
            return True
        try:
            entry_id = int(body.get("entry_id") or 0)
        except Exception:
            entry_id = 0
        res = te.record_click(entry_id, db_path=db_path)
        send_json(handler, 200 if res.get("ok") else 400, res)
        return True

    if path == "/api/throne/shout":
        if not te.check_rate_limit(f"sh:{ip}", 4, 20):
            send_json(handler, 429, {"ok": False, "error": "Espera unos segundos antes de enviar otro mensaje."})
            return True
        res = te.post_shout(body.get("author"), body.get("text"), db_path=db_path)
        send_json(handler, 200 if res.get("ok") else 400, res)
        return True

    send_json(handler, 404, {"ok": False, "error": "Ruta Throne no encontrada"})
    return True


class ThroneHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ThroneHTTPHandler(BaseHTTPRequestHandler):
    db_path_override: Optional[str] = None

    def do_OPTIONS(self):
        self.send_response(204)
        send_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/throne"
        if handle_throne_get(self, path, db_path=self.db_path_override):
            return
        if path in ("/healthz", "/status"):
            _, uname = resolve_throne_bot()
            send_json(self, 200, {"status": "online", "service": "El Trono de $1.99", "bot": f"@{uname}"})
            return
        send_json(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if handle_throne_post(self, path, db_path=self.db_path_override):
            return
        send_json(self, 404, {"ok": False, "error": "Not found"})

    def log_message(self, format, *args):
        pass


def start_throne_server(port: Optional[int] = None) -> ThroneHTTPServer:
    target_port = port or int(os.environ.get("THRONE_PORT", os.environ.get("PORT", 8099)))
    te.init_db()
    _, uname = resolve_throne_bot()
    srv = ThroneHTTPServer(("0.0.0.0", target_port), ThroneHTTPHandler)
    print(f"[ThroneServer] Escuchando en http://0.0.0.0:{target_port}/throne | Bot: @{uname}", flush=True)
    return srv


if __name__ == "__main__":
    srv = start_throne_server()
    srv.serve_forever()

#!/usr/bin/env python3
"""
Nexus Global Cloud Supervisor ⚡
Runs and supervises all 3 Telegram Bots concurrently on a single Free Cloud Instance:
  1. @nexus_global_vault_bot (Productivity & Utility Vault)
  2. @lucky_vault_arcade_bot (Arcade Gaming & Fortune Wheel)
  3. @cryptovault_pulse_bot (Crypto Signals, Whale Tracker & Airdrops)
Includes HTTP Health Check server for Render.com / Koyeb / Railway / Docker deployments.
"""

import os
import sys
import time
import signal
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_SCRIPTS = [
    {
        "name": "Nexus Global Vault Bot (@nexus_global_vault_bot)",
        "script": os.path.join(BASE_DIR, "bot.py"),
        "cwd": BASE_DIR,
        "token_env": "BOT_TOKEN_VAULT"
    },
    {
        "name": "Lucky Vault Arcade Bot (@lucky_vault_arcade_bot)",
        "script": os.path.join(BASE_DIR, "bots", "arcade_bot.py"),
        "cwd": os.path.join(BASE_DIR, "bots"),
        "token_env": "BOT_TOKEN_ARCADE"
    },
    {
        "name": "CryptoVault Pulse Bot (@cryptovault_pulse_bot)",
        "script": os.path.join(BASE_DIR, "bots", "crypto_bot.py"),
        "cwd": os.path.join(BASE_DIR, "bots"),
        "token_env": "BOT_TOKEN_PULSE"
    }
]

BOT_PROCESSES = {}
RUNNING = True

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] [CloudSupervisor] {msg}", flush=True)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        status_info = {
            "status": "online",
            "uptime_utc": datetime.utcnow().isoformat(),
            "active_bots": {b["name"]: (BOT_PROCESSES.get(b["name"]) and BOT_PROCESSES[b["name"]].poll() is None) for b in BOT_SCRIPTS}
        }
        import json
        self.wfile.write(json.dumps(status_info, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence routine health check request logs to keep terminal clean
        pass

def run_health_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    log(f"Servidor de Health Check activo en puerto {port} para Render/Koyeb")
    server.serve_forever()

def supervise_bot(bot_info):
    name = bot_info["name"]
    script = bot_info["script"]
    cwd = bot_info["cwd"]
    
    if not os.path.exists(script):
        log(f"ERROR: Script no encontrado para {name}: {script}")
        return

    while RUNNING:
        log(f"Iniciando subproceso: {name}...")
        env = os.environ.copy()
        
        # Inyectar token específico si existe variable de entorno
        if bot_info["token_env"] in env:
            env["BOT_TOKEN"] = env[bot_info["token_env"]]
        
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=cwd,
            env=env
        )
        BOT_PROCESSES[name] = proc
        
        # Esperar a que el proceso termine
        return_code = proc.wait()
        log(f"ALERTA: {name} se detuvo con codigo {return_code}. Reiniciando en 5 segundos...")
        time.sleep(5)

def main():
    log("Iniciando Nexus Global Cloud Supervisor (3 Bots en 1 Contenedor)...")
    
    # Iniciar cada bot en su propio hilo de supervision
    for bot_info in BOT_SCRIPTS:
        t = threading.Thread(target=supervise_bot, args=(bot_info,), daemon=True)
        t.start()
        time.sleep(1) # Breve pausa entre arranques

    # Iniciar servidor HTTP en el puerto indicado por la nube (Render asigna PORT)
    port = int(os.environ.get("PORT", 10000))
    health_thread = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    health_thread.start()

    log(f"Todos los bots han sido desplegados y estan bajo supervision 24/7.")

    try:
        while RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Deteniendo supervisor...")
        for name, proc in BOT_PROCESSES.items():
            if proc.poll() is None:
                proc.terminate()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CyberShield AI — Real Threat Intelligence, Multi-Chain Blockchain & Image Forensics Engine.

Integrates real live security APIs (no simulated verdicts):
- URL / Domain / Hash Threat Intel:
  Cloudflare Security DNS (1.1.1.2), VirusTotal v3 (when VT_API_KEY is set),
  GoPlus Phishing & dApp Security, AlienVault OTX, urlscan.io, OpenPhish,
  Phishing Army, ScamSniffer, RDAP Domain Age/Registrar, Live X.509 SSL/TLS,
  Shodan InternetDB, HTTP Redirect Tracer, and Abuse.ch URLhaus/MalwareBazaar
  (when ABUSECH_AUTH_KEY is set).
- Multi-Chain Crypto Contract & Wallet Audit:
  EVM (7 chains via PublicNode RPCs: ETH, BSC, Polygon, Arbitrum, Base,
  Optimism, Avalanche), TRON (TronGrid + GoPlus), Solana (RPC + GoPlus +
  RugCheck), Bitcoin (Mempool.space), TON (TonAPI v2). Extracts verified
  status, SPDX license type (Sourcify / Blockscout / Etherscan v2), and live
  scam/sanctions/phishing reputation (GoPlus Address Security + ScamSniffer).
- Bank Receipt / Image Forensics:
  Real SHA-256 hashing, EXIF/PNG/XMP/8BIM editor metadata scan, localized 16x16
  Error Level Analysis (ELA) with heatmap image generation, cover-up patch
  noise/color mismatch detection, and JPEG double-compression zone check.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import io
import json
import math
import os
import re
import socket
import ssl
import tempfile
import threading
import time
import urllib.parse
import zlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
import requests

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except Exception:
    HAS_CRYPTOGRAPHY = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
CACHE_DIR = os.path.join(tempfile.gettempdir(), "cybershield_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

USER_AGENT = "CyberShieldAI-Forensics/2.5 (+https://github.com/vargasap/cybershield-ai)"

# Thread-safe in-memory feed caches
_FEED_LOCKS: Dict[str, threading.Lock] = {
    "openphish": threading.Lock(),
    "phishing_army": threading.Lock(),
    "scamsniffer_domains": threading.Lock(),
    "scamsniffer_addrs": threading.Lock(),
}
_FEED_CACHE: Dict[str, Tuple[float, Any]] = {}

# Two-part ccTLDs so registrable domain extraction avoids stopping at ".com.co"
SECOND_LEVEL_CCTLDS = {
    "com.ve", "net.ve", "org.ve", "gob.ve", "gov.ve", "edu.ve",
    "com.co", "net.co", "org.co", "gov.co", "edu.co",
    "com.mx", "net.mx", "org.mx", "gob.mx", "edu.mx",
    "com.ar", "net.ar", "org.ar", "gob.ar", "edu.ar",
    "com.br", "net.br", "org.br", "gov.br", "edu.br",
    "com.pe", "net.pe", "org.pe", "gob.pe", "edu.pe",
    "com.ec", "com.uy", "com.py", "com.bo", "com.do",
    "com.gt", "com.sv", "com.hn", "com.ni", "com.pa", "com.cr", "com.pr",
    "co.uk", "org.uk", "gov.uk", "ac.uk",
    "com.au", "net.au", "org.au", "gov.au",
    "co.jp", "ne.jp", "or.jp", "co.in", "com.tr", "co.kr",
}

EVM_CHAINS = [
    ("1", "Ethereum", "ETH", "https://ethereum-rpc.publicnode.com", "https://etherscan.io/address/"),
    ("56", "BNB Smart Chain", "BNB", "https://bsc-rpc.publicnode.com", "https://bscscan.com/address/"),
    ("137", "Polygon", "POL", "https://polygon-bor-rpc.publicnode.com", "https://polygonscan.com/address/"),
    ("42161", "Arbitrum One", "ETH", "https://arbitrum-one-rpc.publicnode.com", "https://arbiscan.io/address/"),
    ("8453", "Base", "ETH", "https://base-rpc.publicnode.com", "https://basescan.org/address/"),
    ("10", "Optimism", "ETH", "https://optimism-rpc.publicnode.com", "https://optimistic.etherscan.io/address/"),
    ("43114", "Avalanche C-Chain", "AVAX", "https://avalanche-c-chain-rpc.publicnode.com", "https://snowtrace.io/address/"),
]

BLOCKSCOUT_V2_HOSTS = {
    "1": "https://eth.blockscout.com",
    "10": "https://optimism.blockscout.com",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "rb.gy", "is.gd", "v.gd",
    "ow.ly", "shorturl.at", "rebrand.ly", "tiny.cc", "goo.gl", "buff.ly",
    "shorte.st", "adf.ly", "clck.ru", "s.id",
}

SUSPICIOUS_TLDS = {
    ".top", ".xyz", ".club", ".work", ".click", ".site", ".monster", ".rest",
    ".buzz", ".cfd", ".sbs", ".icu", ".gq", ".tk", ".ml", ".ga", ".cf",
    ".loan", ".win", ".vip", ".shop",
}

KNOWN_BRANDS: Dict[str, List[str]] = {
    "amazon": ["amazon.com", "amazon.es", "amazon.com.mx", "amazon.co.uk", "amazon.de", "amzn.to"],
    "paypal": ["paypal.com", "paypal.me"],
    "binance": ["binance.com", "binance.us", "binance.org", "bnbchain.org"],
    "mercadolibre": ["mercadolibre.com", "mercadolibre.com.ve", "mercadolibre.com.co", "mercadolibre.com.mx", "mercadolibre.com.ar", "mercadopago.com"],
    "google": ["google.com", "google.es", "gmail.com", "youtube.com", "youtu.be", "googleapis.com", "accounts.google.com"],
    "apple": ["apple.com", "icloud.com"],
    "microsoft": ["microsoft.com", "live.com", "outlook.com", "office.com", "xbox.com"],
    "netflix": ["netflix.com"],
    "shein": ["shein.com", "shein.com.mx"],
    "temu": ["temu.com"],
    "walmart": ["walmart.com", "walmart.com.mx"],
    "metamask": ["metamask.io"],
    "coinbase": ["coinbase.com"],
    "trustwallet": ["trustwallet.com"],
    "telegram": ["telegram.org", "t.me", "web.telegram.org"],
    "whatsapp": ["whatsapp.com", "wa.me", "web.whatsapp.com"],
    "bbva": ["bbva.com", "bbva.es", "bbva.mx", "bbva.com.co", "bbva.com.ar"],
    "santander": ["santander.com", "bancosantander.es", "santander.com.mx"],
    "bancolombia": ["bancolombia.com", "grupobancolombia.com"],
    "nequi": ["nequi.com.co", "nequi.com"],
    "zelle": ["zellepay.com"],
    "banesco": ["banesco.com", "banesco.com.pa"],
    "mercantil": ["mercantilbanco.com"],
    "provincial": ["provincial.com"],
    "bnc": ["bncenlinea.com"],
    "dhl": ["dhl.com"],
    "fedex": ["fedex.com"],
    "ups": ["ups.com"],
}

EDITOR_SIGNATURES = [
    ("Adobe Photoshop", "Adobe Photoshop"),
    ("Photoshop", "Photoshop"),
    ("8BIM", "Adobe Photoshop IRB (8BIM)"),
    ("Canva", "Canva"),
    ("PicsArt", "PicsArt"),
    ("Picsart", "PicsArt"),
    ("GIMP", "GIMP"),
    ("Photopea", "Photopea"),
    ("Snapseed", "Snapseed"),
    ("Figma", "Figma"),
    ("Lightroom", "Adobe Lightroom"),
    ("Paint.NET", "Paint.NET"),
    ("paint.net", "Paint.NET"),
    ("Corel", "CorelDRAW / Photo-Paint"),
    ("Pixlr", "Pixlr"),
    ("InShot", "InShot"),
    ("CapCut", "CapCut"),
    ("Fotor", "Fotor"),
    ("ibisPaint", "ibisPaint"),
    ("Procreate", "Procreate"),
    ("Affinity", "Affinity Photo/Designer"),
    ("Illustrator", "Adobe Illustrator"),
    ("Sketch", "Sketch App"),
    ("fake", "Cadena 'fake' en metadatos"),
    ("comprobante falso", "Generador de comprobantes"),
]

EXECUTABLE_EXTENSIONS = {
    ".exe", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse",
    ".msi", ".apk", ".dll", ".sys", ".com", ".pif", ".hta", ".jar", ".sh",
}

SOLANA_B58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


# ---------------------------------------------------------------------------
# Helpers: Configuration, Hashing, Normalization
# ---------------------------------------------------------------------------

def _read_env_value(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if val:
        return val
    for folder in (BASE_DIR, PARENT_DIR):
        env_path = os.path.join(folder, ".env")
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
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


def get_api_keys() -> Dict[str, str]:
    return {
        "vt": _read_env_value("VT_API_KEY") or _read_env_value("VIRUSTOTAL_API_KEY"),
        "abusech": _read_env_value("ABUSECH_AUTH_KEY") or _read_env_value("URLHAUS_AUTH_KEY"),
        "etherscan": _read_env_value("ETHERSCAN_API_KEY"),
        "tron": _read_env_value("TRON_API_KEY") or _read_env_value("TRONGRID_API_KEY"),
    }


def get_api_status() -> Dict[str, Any]:
    keys = get_api_keys()
    return {
        "free_live_engines": [
            "Cloudflare Security DNS (1.1.1.2 Malware/Phishing Block)",
            "GoPlus Security (Phishing URLs, dApps, Wallet Reports, Token Honeypot)",
            "AlienVault OTX (Domain & File Hash Threat Pulses)",
            "urlscan.io (Live Domain Scan History)",
            "OpenPhish + Phishing Army + ScamSniffer Feeds",
            "RDAP / WHOIS (Real Domain Creation Date & Registrar)",
            "Live X.509 SSL/TLS Certificate & Redirect Chain Tracer",
            "Shodan InternetDB (Open Ports & CVEs)",
            "7x EVM RPCs + Sourcify v2 + Blockscout v2 (SPDX Contract License)",
            "TRON (TronGrid + GoPlus) / Solana (RPC + RugCheck + GoPlus) / BTC (Mempool) / TON (TonAPI)",
            "Local Receipt Forensics (EXIF/XMP/PNG Metadata + 16x16 ELA Heatmap + Patch Detector)",
        ],
        "optional_api_keys": {
            "VT_API_KEY": bool(keys["vt"]),
            "ETHERSCAN_API_KEY": bool(keys["etherscan"]),
            "ABUSECH_AUTH_KEY": bool(keys["abusech"]),
            "TRON_API_KEY": bool(keys["tron"]),
        },
    }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _extract_registrable_domain(hostname: str) -> str:
    host = hostname.strip().lower().rstrip(".")
    if not host or re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return host
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    last2 = ".".join(parts[-2:])
    if last2 in SECOND_LEVEL_CCTLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last2


def _domain_matches_set(hostname: str, domain_set: set) -> Optional[str]:
    if not domain_set or not hostname:
        return None
    h = hostname.lower().lstrip("www.")
    parts = hostname.lower().split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in domain_set:
            return cand
    if h in domain_set:
        return h
    return None


def _safe_json_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 6.0) -> Tuple[int, Optional[Any]]:
    try:
        hdrs = {"User-Agent": USER_AGENT}
        if headers:
            hdrs.update(headers)
        r = requests.get(url, headers=hdrs, timeout=timeout)
        if r.status_code == 200:
            return 200, r.json()
        return r.status_code, None
    except Exception:
        return 0, None


def _safe_json_post(
    url: str,
    json_body: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 6.0,
) -> Tuple[int, Optional[Any]]:
    try:
        hdrs = {"User-Agent": USER_AGENT}
        if headers:
            hdrs.update(headers)
        r = requests.post(url, json=json_body, data=data, headers=hdrs, timeout=timeout)
        if r.status_code == 200:
            return 200, r.json()
        return r.status_code, None
    except Exception:
        return 0, None


# ---------------------------------------------------------------------------
# Feed Cache Loaders (OpenPhish, Phishing Army, ScamSniffer)
# ---------------------------------------------------------------------------

def _load_feed_cached(
    name: str,
    url: str,
    ttl_seconds: int,
    parser,
    timeout: float = 10.0,
) -> Any:
    now = time.time()
    mem = _FEED_CACHE.get(name)
    if mem and (now - mem[0] < ttl_seconds):
        return mem[1]

    lock = _FEED_LOCKS[name]
    with lock:
        mem = _FEED_CACHE.get(name)
        if mem and (time.time() - mem[0] < ttl_seconds):
            return mem[1]

        cache_file = os.path.join(CACHE_DIR, f"{name}.cache")
        if os.path.isfile(cache_file):
            age = time.time() - os.path.getmtime(cache_file)
            if age < ttl_seconds:
                try:
                    with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
                        parsed = parser(f.read())
                    _FEED_CACHE[name] = (time.time(), parsed)
                    return parsed
                except Exception:
                    pass

        # Download fresh
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if r.status_code == 200 and r.text:
                with open(cache_file, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)
                parsed = parser(r.text)
                _FEED_CACHE[name] = (time.time(), parsed)
                return parsed
        except Exception:
            pass

        # Fallback to stale disk cache if network fails
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8", errors="ignore") as f:
                    parsed = parser(f.read())
                _FEED_CACHE[name] = (time.time(), parsed)
                return parsed
            except Exception:
                pass
    return None


def _parse_openphish(text: str) -> Tuple[set, set]:
    urls = set()
    hosts = set()
    for line in text.splitlines():
        u = line.strip()
        if not u or u.startswith("#"):
            continue
        urls.add(u.rstrip("/").lower())
        try:
            p = urllib.parse.urlparse(u)
            if p.hostname:
                hosts.add(p.hostname.lower())
        except Exception:
            pass
    return urls, hosts


def _parse_domain_lines(text: str) -> set:
    domains = set()
    for line in text.splitlines():
        s = line.strip().lower()
        if not s or s.startswith("#"):
            continue
        domains.add(s)
    return domains


def _parse_json_list_lower(text: str) -> set:
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return {str(x).strip().lower() for x in arr if x}
    except Exception:
        pass
    return set()


# ---------------------------------------------------------------------------
# 1. URL / DOMAIN AUDITOR
# ---------------------------------------------------------------------------

def _de_leet(s: str) -> str:
    return (
        s.lower()
        .replace("0", "o")
        .replace("1", "l")
        .replace("3", "e")
        .replace("4", "a")
        .replace("5", "s")
        .replace("7", "t")
        .replace("@", "a")
        .replace("rn", "m")
        .replace("vv", "w")
    )


def _check_brand_impersonation(hostname: str, reg_domain: str) -> Tuple[bool, Optional[str], bool]:
    """
    Returns (is_official_brand, impersonated_brand_name, has_strong_spoof).
    """
    host_l = hostname.lower()
    reg_l = reg_domain.lower()
    for brand, official_domains in KNOWN_BRANDS.items():
        if reg_l in official_domains or host_l in official_domains:
            return True, brand, False

    labels = host_l.replace(".", "-").split("-")
    deleet_host = _de_leet(host_l)
    deleet_reg = _de_leet(reg_l)
    for brand in KNOWN_BRANDS:
        if len(brand) < 4:
            continue
        # Brand appears inside non-official domain or subdomain
        if brand in host_l or brand in deleet_host or brand in deleet_reg:
            # Exclude harmless blog/news mentions unless suspicious indicators exist
            strong_tokens = (
                "login", "signin", "verify", "seguro", "soporte", "support",
                "sorteo", "promo", "deals", "gratis", "claim", "airdrop",
                "wallet", "connect", "update", "bloqueo", "cuenta", "webmail",
                "outlet", "recover", "auth",
            )
            has_tld = any(host_l.endswith(t) for t in SUSPICIOUS_TLDS)
            leet_changed = (brand not in host_l and brand in deleet_host)
            if leet_changed or has_tld or any(tok in host_l for tok in strong_tokens) or (brand in labels and "-" in reg_l):
                return False, brand, True
            return False, brand, False
    return False, None, False


def _trace_http_redirects(target_url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "reachable": False,
        "status_code": None,
        "final_url": target_url,
        "final_host": "",
        "redirect_count": 0,
        "hops": [],
        "error": None,
        "used_http_fallback": False,
    }
    try:
        r = requests.get(
            target_url,
            allow_redirects=True,
            stream=True,
            timeout=6.5,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"},
        )
        out["reachable"] = True
        out["status_code"] = r.status_code
        out["final_url"] = r.url
        out["hops"] = [h.url for h in r.history] + [r.url]
        out["redirect_count"] = len(r.history)
        try:
            out["final_host"] = (urllib.parse.urlparse(r.url).hostname or "").lower()
        except Exception:
            pass
        r.close()
        return out
    except Exception as e:
        out["error"] = str(e)[:120]
        if target_url.startswith("https://"):
            http_url = "http://" + target_url[len("https://"):]
            try:
                r2 = requests.get(
                    http_url,
                    allow_redirects=True,
                    stream=True,
                    timeout=5.5,
                    headers={"User-Agent": "Mozilla/5.0 Chrome/124.0"},
                )
                out["reachable"] = True
                out["used_http_fallback"] = True
                out["status_code"] = r2.status_code
                out["final_url"] = r2.url
                out["hops"] = [h.url for h in r2.history] + [r2.url]
                out["redirect_count"] = len(r2.history)
                out["final_host"] = (urllib.parse.urlparse(r2.url).hostname or "").lower()
                r2.close()
            except Exception:
                pass
        return out


def _check_dns_and_cloudflare_sec(host: str, reg_domain: str) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "ips": [],
        "cf_blocked": False,
        "has_mx": False,
        "has_spf": False,
    }
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        res["ips"] = [host]
        return res

    # Standard Cloudflare DoH 1.1.1.1
    st, data = _safe_json_get(
        f"https://cloudflare-dns.com/dns-query?name={urllib.parse.quote(host)}&type=A",
        headers={"Accept": "application/dns-json"},
        timeout=5.0,
    )
    if st == 200 and data and data.get("Answer"):
        for ans in data["Answer"]:
            if ans.get("type") == 1 and ans.get("data"):
                res["ips"].append(ans["data"])
    if not res["ips"]:
        try:
            ip = socket.gethostbyname(host)
            if ip:
                res["ips"].append(ip)
        except Exception:
            pass

    # Cloudflare Security DoH 1.1.1.2 (blocks malware & phishing -> 0.0.0.0)
    st_sec, data_sec = _safe_json_get(
        f"https://security.cloudflare-dns.com/dns-query?name={urllib.parse.quote(host)}&type=A",
        headers={"Accept": "application/dns-json"},
        timeout=5.0,
    )
    if st_sec == 200 and data_sec and data_sec.get("Answer"):
        sec_ips = [a.get("data") for a in data_sec["Answer"] if a.get("type") == 1]
        if "0.0.0.0" in sec_ips:
            res["cf_blocked"] = True

    # MX + SPF TXT on registrable domain
    st_mx, data_mx = _safe_json_get(
        f"https://cloudflare-dns.com/dns-query?name={urllib.parse.quote(reg_domain)}&type=MX",
        headers={"Accept": "application/dns-json"},
        timeout=4.5,
    )
    if st_mx == 200 and data_mx and data_mx.get("Answer"):
        res["has_mx"] = any(a.get("type") == 15 for a in data_mx["Answer"])

    st_txt, data_txt = _safe_json_get(
        f"https://cloudflare-dns.com/dns-query?name={urllib.parse.quote(reg_domain)}&type=TXT",
        headers={"Accept": "application/dns-json"},
        timeout=4.5,
    )
    if st_txt == 200 and data_txt and data_txt.get("Answer"):
        res["has_spf"] = any("v=spf1" in str(a.get("data", "")).lower() for a in data_txt["Answer"])

    return res


def _check_ssl_cert(host: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "valid": False,
        "present": False,
        "issuer": None,
        "days_left": None,
        "expires_at": None,
        "error": None,
    }
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=4.5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                out["valid"] = True
                out["present"] = True
                der = ssock.getpeercert(binary_form=True)
                cert_dict = ssock.getpeercert()
                if HAS_CRYPTOGRAPHY and der:
                    xcert = x509.load_der_x509_certificate(der, default_backend())
                    issuer_attrs = {a.oid._name: a.value for a in xcert.issuer}
                    out["issuer"] = issuer_attrs.get("organizationName") or issuer_attrs.get("commonName") or "Autoridad SSL"
                    exp = getattr(xcert, "not_valid_after_utc", None)
                    if exp is None:
                        exp = xcert.not_valid_after.replace(tzinfo=timezone.utc)
                    out["days_left"] = (exp - datetime.now(timezone.utc)).days
                    out["expires_at"] = exp.strftime("%Y-%m-%d")
                elif cert_dict:
                    issuer_d = dict(x[0] for x in cert_dict.get("issuer", []))
                    out["issuer"] = issuer_d.get("organizationName") or issuer_d.get("commonName") or "SSL"
                    not_after = cert_dict.get("notAfter")
                    if not_after:
                        try:
                            dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                            out["days_left"] = (dt - datetime.now(timezone.utc)).days
                            out["expires_at"] = dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
    except ssl.SSLCertVerificationError as ve:
        out["error"] = f"Certificado inválido/no confiable: {str(ve.verify_message)[:80]}"
        out["present"] = True
    except Exception as e:
        out["error"] = str(e)[:90]
    return out


def _check_rdap(reg_domain: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "found": False,
        "created_date": None,
        "age_days": None,
        "registrar": None,
    }
    if not reg_domain or re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", reg_domain):
        return out
    st, data = _safe_json_get(f"https://rdap.org/domain/{urllib.parse.quote(reg_domain)}", timeout=6.5)
    if st != 200 or not isinstance(data, dict):
        return out

    out["found"] = True
    for ev in data.get("events", []):
        if ev.get("eventAction") == "registration" and ev.get("eventDate"):
            raw_d = ev["eventDate"]
            try:
                dt = datetime.fromisoformat(raw_d.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                out["created_date"] = dt.strftime("%Y-%m-%d")
                out["age_days"] = max(0, (datetime.now(timezone.utc) - dt).days)
            except Exception:
                out["created_date"] = raw_d[:10]

    for ent in data.get("entities", []):
        roles = ent.get("roles") or []
        if "registrar" in roles:
            vcard = ent.get("vcardArray")
            if isinstance(vcard, list) and len(vcard) >= 2:
                for item in vcard[1]:
                    if isinstance(item, list) and len(item) >= 4 and item[0] == "fn":
                        out["registrar"] = str(item[3])
                        break
            if not out["registrar"] and ent.get("handle"):
                out["registrar"] = str(ent.get("handle"))
            break
    return out


def _check_virustotal_url(target_url: str, domain: str, api_key: str) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "configured": bool(api_key),
        "queried": False,
        "malicious": 0,
        "suspicious": 0,
        "harmless": 0,
        "total_engines": 0,
        "flagged_by": [],
        "source": None,
        "error": None,
    }
    if not api_key:
        return res

    headers = {"x-apikey": api_key, "Accept": "application/json"}
    url_id = base64.urlsafe_b64encode(target_url.encode("utf-8")).decode("ascii").rstrip("=")
    st, data = _safe_json_get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=7.0)
    if st == 200 and data:
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        res["queried"] = True
        res["source"] = "URL Report"
        res["malicious"] = int(stats.get("malicious", 0))
        res["suspicious"] = int(stats.get("suspicious", 0))
        res["harmless"] = int(stats.get("harmless", 0))
        res["total_engines"] = sum(int(v) for v in stats.values() if isinstance(v, (int, float)))
        results_map = attrs.get("last_analysis_results", {})
        res["flagged_by"] = [
            eng for eng, info in results_map.items()
            if isinstance(info, dict) and info.get("category") in ("malicious", "phishing", "suspicious")
        ][:6]
        return res

    # Fallback: submit URL briefly or check domain report
    if domain:
        st_d, data_d = _safe_json_get(f"https://www.virustotal.com/api/v3/domains/{urllib.parse.quote(domain)}", headers=headers, timeout=7.0)
        if st_d == 200 and data_d:
            attrs = data_d.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            res["queried"] = True
            res["source"] = "Domain Report"
            res["malicious"] = int(stats.get("malicious", 0))
            res["suspicious"] = int(stats.get("suspicious", 0))
            res["harmless"] = int(stats.get("harmless", 0))
            res["total_engines"] = sum(int(v) for v in stats.values() if isinstance(v, (int, float)))
            results_map = attrs.get("last_analysis_results", {})
            res["flagged_by"] = [
                eng for eng, info in results_map.items()
                if isinstance(info, dict) and info.get("category") in ("malicious", "phishing", "suspicious")
            ][:6]
            return res

    # Submit URL for fresh scan if nothing cached
    if st == 404:
        st_sub, _ = _safe_json_post("https://www.virustotal.com/api/v3/urls", data={"url": target_url}, headers=headers, timeout=6.0)
        if st_sub == 200:
            res["error"] = "URL enviada a VirusTotal para análisis inicial (vuelve a escanear en 15s)"
    elif st in (401, 403):
        res["error"] = "VT_API_KEY inválida o sin permisos"
    elif st == 429:
        res["error"] = "Cuota por minuto de VirusTotal alcanzada"
    return res


def _check_otx_domain(host: str, reg_domain: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"queried": False, "pulses": 0, "whitelisted": False, "validations": []}
    for cand in dict.fromkeys([reg_domain, host]):
        if not cand:
            continue
        st, data = _safe_json_get(f"https://otx.alienvault.com/api/v1/indicators/domain/{urllib.parse.quote(cand)}/general", timeout=6.0)
        if st == 200 and isinstance(data, dict):
            out["queried"] = True
            pulses = int((data.get("pulse_info") or {}).get("count") or 0)
            vals = [v.get("name", "") for v in (data.get("validation") or []) if isinstance(v, dict)]
            wl = any(
                k in " ".join(vals).lower()
                for k in ("whitelist", "alexa", "akamai", "false positive", "cloudflare")
            )
            out["pulses"] = max(out["pulses"], pulses)
            out["validations"] = list(dict.fromkeys(out["validations"] + vals))
            if wl:
                out["whitelisted"] = True
                break
    return out


def _check_urlscan_domain(host: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"queried": False, "total": 0, "malicious_hits": 0}
    st, data = _safe_json_get(f"https://urlscan.io/api/v1/search/?q=page.domain:{urllib.parse.quote(host)}&size=5", timeout=6.0)
    if st == 200 and isinstance(data, dict):
        out["queried"] = True
        results = data.get("results") or []
        out["total"] = int(data.get("total") or len(results))
        for item in results:
            verdicts = (item.get("verdicts") or {}).get("overall") or {}
            if verdicts.get("malicious") is True:
                out["malicious_hits"] += 1
    return out


def audit_url(raw_url: str) -> Dict[str, Any]:
    clean = (raw_url or "").strip()
    # Strip trailing punctuation when extracted from prose
    clean = clean.rstrip(".,;:!?)\"'<>")
    if not clean:
        return {"error": "URL vacía", "risk_score": 0, "verdict_level": "warn", "checks": []}

    has_scheme = bool(re.match(r"^https?://", clean, re.I))
    target_url = clean if has_scheme else f"https://{clean}"
    parsed = urllib.parse.urlparse(target_url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return {"error": "Dominio inválido", "risk_score": 30, "verdict_level": "warn", "checks": []}

    reg_domain = _extract_registrable_domain(hostname)
    keys = get_api_keys()

    # Fast local lexical flags
    is_punycode = "xn--" in hostname
    has_userinfo = "@" in (parsed.netloc or "")
    is_ip_host = bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", hostname))
    is_shortener = hostname.lstrip("www.") in URL_SHORTENERS or reg_domain in URL_SHORTENERS

    checks: List[Dict[str, Any]] = []
    risk = 0
    sources_used: List[str] = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        f_http = pool.submit(_trace_http_redirects, target_url)
        f_dns = pool.submit(_check_dns_and_cloudflare_sec, hostname, reg_domain)
        f_ssl = pool.submit(_check_ssl_cert, hostname)
        f_rdap = pool.submit(_check_rdap, reg_domain)
        f_vt = pool.submit(_check_virustotal_url, target_url, reg_domain, keys["vt"])
        f_gp_phish = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/phishing_site?url={urllib.parse.quote(target_url)}", None, 5.5)
        f_gp_dapp = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/dapp_security?url={urllib.parse.quote(target_url)}", None, 5.5)
        f_otx = pool.submit(_check_otx_domain, hostname, reg_domain)
        f_urlscan = pool.submit(_check_urlscan_domain, hostname)
        f_openphish = pool.submit(_load_feed_cached, "openphish", "https://openphish.com/feed.txt", 1800, _parse_openphish, 5.0)
        f_army = pool.submit(_load_feed_cached, "phishing_army", "https://phishing.army/download/phishing_army_blocklist.txt", 21600, _parse_domain_lines, 9.0)
        f_ss_dom = pool.submit(_load_feed_cached, "scamsniffer_domains", "https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/domains.json", 21600, _parse_json_list_lower, 10.0)
        f_urlhaus = (
            pool.submit(
                _safe_json_post,
                "https://urlhaus-api.abuse.ch/v1/host/",
                None,
                {"host": hostname},
                {"Auth-Key": keys["abusech"]},
                5.5,
            )
            if keys["abusech"]
            else None
        )

        http_res = f_http.result()
        dns_res = f_dns.result()
        ssl_res = f_ssl.result()
        rdap_res = f_rdap.result()
        vt_res = f_vt.result()
        gp_phish_st, gp_phish_data = f_gp_phish.result()
        gp_dapp_st, gp_dapp_data = f_gp_dapp.result()
        otx_res = f_otx.result()
        urlscan_res = f_urlscan.result()
        openphish_data = f_openphish.result()
        army_set = f_army.result()
        ss_dom_set = f_ss_dom.result()
        urlhaus_res = f_urlhaus.result() if f_urlhaus else (0, None)

    final_url = http_res.get("final_url") or target_url
    final_host = http_res.get("final_host") or hostname
    final_reg = _extract_registrable_domain(final_host) if final_host else reg_domain

    # If redirected to a DIFFERENT registrable domain, also verify CF Security + feeds on destination
    redirected_external = bool(final_host and final_reg != reg_domain)
    if redirected_external:
        ext_dns = _check_dns_and_cloudflare_sec(final_host, final_reg)
        if ext_dns.get("cf_blocked"):
            dns_res["cf_blocked"] = True
        checks.append({
            "label": "Redirección a otro dominio",
            "status": f"{hostname} -> {final_host} ({http_res['redirect_count']} saltos)",
            "ok": False if is_shortener or any(final_host.endswith(t) for t in SUSPICIOUS_TLDS) else True,
            "severity": "warn",
        })
    elif http_res.get("redirect_count", 0) > 0:
        checks.append({
            "label": "Redirección HTTP",
            "status": f"OK -> {final_host} ({http_res.get('status_code')})",
            "ok": True,
            "severity": "safe",
        })

    # DNS + Cloudflare Security
    sources_used.append("Cloudflare DNS + 1.1.1.2")
    ips = dns_res.get("ips") or []
    if dns_res.get("cf_blocked"):
        risk = max(risk, 94)
        checks.append({
            "label": "Cloudflare Security (1.1.1.2)",
            "status": "BLOQUEADO: Malware / Phishing activo",
            "ok": False,
            "severity": "danger",
        })
    elif ips:
        checks.append({
            "label": "Resolución DNS & 1.1.1.2",
            "status": f"Limpio en 1.1.1.2 | IP: {ips[0]}",
            "ok": True,
            "severity": "safe",
        })
    else:
        risk += 45
        checks.append({
            "label": "Resolución DNS",
            "status": "El dominio no resuelve IP (caído, inexistente o bloqueado)",
            "ok": False,
            "severity": "danger",
        })

    # Shodan InternetDB on primary IP
    if ips and not re.fullmatch(r"127\..*|10\..*|192\.168\..*|0\.0\.0\.0", ips[0]):
        sh_st, sh_data = _safe_json_get(f"https://internetdb.shodan.io/{ips[0]}", timeout=4.0)
        if sh_st == 200 and isinstance(sh_data, dict):
            sources_used.append("Shodan InternetDB")
            ports = sh_data.get("ports") or []
            vulns = sh_data.get("vulns") or []
            if vulns:
                checks.append({
                    "label": "Shodan InternetDB (IP)",
                    "status": f"Puertos {ports[:6]} | {len(vulns)} CVEs en IP compartida",
                    "ok": True,
                    "severity": "info",
                })

    # SSL/TLS Certificate
    if ssl_res["valid"]:
        days_left = ssl_res.get("days_left")
        exp_info = f" ({days_left}d restantes)" if days_left is not None else ""
        checks.append({
            "label": "Certificado SSL/TLS (HTTPS)",
            "status": f"Válido — {ssl_res.get('issuer', 'CA')}{exp_info}",
            "ok": True,
            "severity": "safe",
        })
        if days_left is not None and days_left < 7:
            risk += 8
    elif ips:
        risk += 32 if http_res.get("used_http_fallback") or not http_res.get("reachable") else 22
        checks.append({
            "label": "Certificado SSL/TLS (HTTPS)",
            "status": f"Fallo TLS: {ssl_res.get('error') or 'Sin HTTPS confiable'}",
            "ok": False,
            "severity": "danger",
        })

    # RDAP Domain Age & Mail Records
    if rdap_res["found"]:
        sources_used.append("RDAP/WHOIS")
        age_days = rdap_res.get("age_days")
        created = rdap_res.get("created_date") or "?"
        reg_name = rdap_res.get("registrar") or "Registrador no listado"
        if age_days is not None:
            if age_days < 30:
                risk += 28
                checks.append({
                    "label": "Antigüedad RDAP/WHOIS",
                    "status": f"RECIÉN CREADO: {age_days} días ({created}) — {reg_name[:28]}",
                    "ok": False,
                    "severity": "danger",
                })
            elif age_days < 180:
                risk += 12
                checks.append({
                    "label": "Antigüedad RDAP/WHOIS",
                    "status": f"Dominio joven: {age_days} días ({created}) — {reg_name[:28]}",
                    "ok": False,
                    "severity": "warn",
                })
            else:
                yrs = age_days / 365.25
                checks.append({
                    "label": "Antigüedad RDAP/WHOIS",
                    "status": f"{yrs:.1f} años ({created}) — {reg_name[:28]}",
                    "ok": True,
                    "severity": "safe",
                })
        else:
            checks.append({
                "label": "Registro RDAP",
                "status": f"Registrador: {reg_name[:38]}",
                "ok": True,
                "severity": "info",
            })

    if not dns_res["has_mx"] and ips:
        # Not malicious by itself, just informational for fake shops claiming corporate email
        checks.append({
            "label": "Correo Corporativo (MX/SPF)",
            "status": "Sin servidores MX/SPF configurados",
            "ok": True,
            "severity": "info",
        })

    # VirusTotal v3
    vt_gui = f"https://www.virustotal.com/gui/domain/{urllib.parse.quote(final_reg or reg_domain)}"
    if vt_res["queried"]:
        sources_used.append("VirusTotal API v3")
        mal = vt_res["malicious"]
        susp = vt_res["suspicious"]
        tot = vt_res["total_engines"]
        if mal >= 2:
            risk = max(risk, 93)
            engines_txt = ", ".join(vt_res["flagged_by"][:4])
            checks.append({
                "label": "VirusTotal (Motores AV)",
                "status": f"MALICIOSO: {mal}/{tot} motores ({engines_txt})",
                "ok": False,
                "severity": "danger",
            })
        elif mal == 1 or susp >= 2:
            risk = max(risk, 65)
            checks.append({
                "label": "VirusTotal (Motores AV)",
                "status": f"SOSPECHOSO: {mal} maliciosos / {susp} sospechosos de {tot}",
                "ok": False,
                "severity": "warn",
            })
        else:
            checks.append({
                "label": "VirusTotal (Motores AV)",
                "status": f"Limpio: 0/{tot} motores ({vt_res['source']})",
                "ok": True,
                "severity": "safe",
            })
    elif vt_res["configured"]:
        checks.append({
            "label": "VirusTotal API v3",
            "status": vt_res.get("error") or "Pendiente de análisis",
            "ok": True,
            "severity": "info",
        })
    else:
        checks.append({
            "label": "VirusTotal API v3",
            "status": "Sin VT_API_KEY en el servidor (ver enlace manual abajo)",
            "ok": True,
            "severity": "info",
        })

    # GoPlus Phishing & dApp
    is_goplus_trusted_dapp = False
    if gp_phish_st == 200 and isinstance(gp_phish_data, dict):
        sources_used.append("GoPlus Phishing")
        ph_res = gp_phish_data.get("result") or {}
        if str(ph_res.get("phishing_site")) == "1":
            risk = max(risk, 96)
            checks.append({
                "label": "GoPlus Web3 Phishing",
                "status": "SITIO PHISHING REPORTADO",
                "ok": False,
                "severity": "danger",
            })
        else:
            checks.append({
                "label": "GoPlus Web3 Phishing",
                "status": "0 alertas de sitio drainer/phishing",
                "ok": True,
                "severity": "safe",
            })

    if gp_dapp_st == 200 and isinstance(gp_dapp_data, dict):
        dr = gp_dapp_data.get("result") or {}
        if str(dr.get("trust_list")) == "1":
            is_goplus_trusted_dapp = True
            proj = dr.get("project_name") or final_reg
            checks.append({
                "label": "GoPlus dApp Verificada",
                "status": f"Lista de confianza: {proj}" + (" (Auditada)" if str(dr.get("is_audit")) == "1" else ""),
                "ok": True,
                "severity": "safe",
            })

    # OpenPhish + Phishing Army + ScamSniffer + URLhaus
    feed_hits: List[str] = []
    if openphish_data:
        sources_used.append("OpenPhish")
        op_urls, op_hosts = openphish_data
        norm_u = target_url.rstrip("/").lower()
        norm_f = final_url.rstrip("/").lower()
        if norm_u in op_urls or norm_f in op_urls or hostname in op_hosts or final_host in op_hosts:
            feed_hits.append("OpenPhish")
    if isinstance(army_set, set) and army_set:
        sources_used.append("Phishing Army")
        if _domain_matches_set(hostname, army_set) or _domain_matches_set(final_host, army_set):
            feed_hits.append("Phishing Army")
    if isinstance(ss_dom_set, set) and ss_dom_set:
        sources_used.append("ScamSniffer")
        if _domain_matches_set(hostname, ss_dom_set) or _domain_matches_set(final_host, ss_dom_set):
            feed_hits.append("ScamSniffer")

    uh_st, uh_data = urlhaus_res
    if uh_st == 200 and isinstance(uh_data, dict):
        sources_used.append("Abuse.ch URLhaus")
        if uh_data.get("query_status") == "ok" and uh_data.get("url_count", 0) > 0:
            feed_hits.append(f"URLhaus ({uh_data.get('url_count')} payloads)")

    if feed_hits:
        risk = max(risk, 96)
        checks.append({
            "label": "Listas Negras Activas",
            "status": f"REPORTADO EN: {', '.join(feed_hits)}",
            "ok": False,
            "severity": "danger",
        })
    elif openphish_data or army_set or ss_dom_set:
        checks.append({
            "label": "Listas Negras (OpenPhish/Army/ScamSniffer)",
            "status": "Sin coincidencias activas",
            "ok": True,
            "severity": "safe",
        })

    # AlienVault OTX
    if otx_res["queried"]:
        sources_used.append("AlienVault OTX")
        pulses = otx_res["pulses"]
        if otx_res["whitelisted"]:
            checks.append({
                "label": "AlienVault OTX",
                "status": "Dominio reconocido en listas legítimas",
                "ok": True,
                "severity": "safe",
            })
        elif pulses >= 2:
            risk = max(risk, 78)
            checks.append({
                "label": "AlienVault OTX",
                "status": f"ALERTA: {pulses} pulsos de amenaza reportados",
                "ok": False,
                "severity": "danger",
            })
        elif pulses == 1:
            risk += 18
            checks.append({
                "label": "AlienVault OTX",
                "status": "1 pulso de amenaza reportado",
                "ok": False,
                "severity": "warn",
            })
        else:
            checks.append({
                "label": "AlienVault OTX",
                "status": "0 pulsos de amenaza",
                "ok": True,
                "severity": "safe",
            })

    # urlscan.io
    if urlscan_res["queried"]:
        sources_used.append("urlscan.io")
        if urlscan_res["malicious_hits"] > 0:
            risk = max(risk, 86)
            checks.append({
                "label": "Historial urlscan.io",
                "status": f"MARCADO MALICIOSO en {urlscan_res['malicious_hits']} escaneo(s)",
                "ok": False,
                "severity": "danger",
            })
        elif urlscan_res["total"] > 0:
            checks.append({
                "label": "Historial urlscan.io",
                "status": f"{urlscan_res['total']} escaneos previos limpios",
                "ok": True,
                "severity": "safe",
            })

    # Lexical / Brand Impersonation Checks (checked on both initial and final host)
    is_off, brand_name, strong_spoof = _check_brand_impersonation(hostname, reg_domain)
    if not strong_spoof and final_host and final_host != hostname:
        is_off2, b2, spo2 = _check_brand_impersonation(final_host, final_reg)
        if spo2:
            is_off, brand_name, strong_spoof = is_off2, b2, spo2

    if strong_spoof and not otx_res.get("whitelisted") and not is_goplus_trusted_dapp:
        risk = max(risk, 88)
        checks.append({
            "label": "Suplantación de Marca (Typosquatting)",
            "status": f"Posible clon de '{brand_name}' fuera del dominio oficial",
            "ok": False,
            "severity": "danger",
        })
    elif is_off:
        # Trusted official domain bonus if clean on security feeds
        if not feed_hits and not dns_res["cf_blocked"] and vt_res["malicious"] == 0 and ips:
            risk = min(risk, 8)
        checks.append({
            "label": "Dominio de Marca Oficial",
            "status": f"Coincide con dominio oficial de {brand_name}",
            "ok": True,
            "severity": "safe",
        })

    if is_punycode:
        risk += 24
        checks.append({
            "label": "Ataque Homógrafo IDN",
            "status": "Dominio Punycode (xn--) detectado",
            "ok": False,
            "severity": "warn",
        })
    if has_userinfo:
        risk += 35
        checks.append({
            "label": "Engaño de Credencial (@)",
            "status": "La URL contiene '@' para ocultar el host real",
            "ok": False,
            "severity": "danger",
        })
    if is_ip_host:
        risk += 30
        checks.append({
            "label": "IP Directa en lugar de Dominio",
            "status": f"Host numérico ({hostname}) sin nombre verificable",
            "ok": False,
            "severity": "warn",
        })

    has_risky_tld = any((final_host or hostname).endswith(t.lower()) for t in SUSPICIOUS_TLDS)
    if has_risky_tld and not (otx_res.get("whitelisted") and vt_res["malicious"] == 0):
        risk += 16
        checks.append({
            "label": "Extensión de Dominio (TLD)",
            "status": "TLD económico de abuso frecuente en phishing",
            "ok": False,
            "severity": "warn",
        })

    # Strong positive trust calibration for old verified domains
    if (
        (rdap_res.get("age_days") or 0) >= 730
        and ssl_res["valid"]
        and not feed_hits
        and not dns_res["cf_blocked"]
        and vt_res["malicious"] == 0
        and urlscan_res["malicious_hits"] == 0
        and not strong_spoof
    ):
        risk = min(risk, 12)

    risk = max(0, min(100, int(round(risk))))
    if risk >= 70:
        level = "danger"
        verdict = "PELIGRO CRÍTICO: RIESGO DE PHISHING / MALWARE"
        advice = "No abras este enlace, no descargues archivos ni introduzcas contraseñas o tarjetas bancarias."
    elif risk >= 35:
        level = "warn"
        verdict = "PRECAUCIÓN: SEÑALES SOSPECHOSAS O INCOMPLETAS"
        advice = "Verifica el dominio por otro canal oficial antes de pagar o iniciar sesión; evita datos sensibles si el dominio es reciente."
    else:
        level = "safe"
        verdict = "SIN AMENAZAS DETECTADAS EN FUENTES CONSULTADAS"
        advice = "Las fuentes consultadas no reportan malware ni phishing activo. Confirma siempre el candado HTTPS exacto en tu navegador."

    return {
        "type": "url",
        "target": target_url,
        "domain": hostname,
        "registrable_domain": reg_domain,
        "final_url": final_url,
        "risk_score": risk,
        "verdict_level": level,
        "verdict_title": verdict,
        "checks": checks,
        "evidence_sources": sources_used,
        "vt_url": vt_gui,
        "advice": advice,
        "sha256_report": _sha256_text(f"url|{target_url}|{risk}|{final_url}"),
    }


# ---------------------------------------------------------------------------
# 2. FILE / HASH AUDITOR
# ---------------------------------------------------------------------------

def audit_file_or_hash(
    file_path: Optional[str] = None,
    raw_bytes: Optional[bytes] = None,
    filename: str = "",
    hash_str: Optional[str] = None,
) -> Dict[str, Any]:
    if raw_bytes is None and file_path and os.path.isfile(file_path):
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        if not filename:
            filename = os.path.basename(file_path)

    if raw_bytes is not None:
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        md5 = hashlib.md5(raw_bytes).hexdigest()
        size_bytes = len(raw_bytes)
    elif hash_str:
        sha256 = hash_str.strip().lower()
        md5 = sha256 if len(sha256) == 32 else ""
        size_bytes = 0
    else:
        return {"error": "Archivo o hash vacío", "risk_score": 0, "verdict_level": "warn", "checks": []}

    keys = get_api_keys()
    checks: List[Dict[str, Any]] = []
    sources: List[str] = []
    risk = 0

    if raw_bytes is not None:
        checks.append({
            "label": "Huella SHA-256",
            "status": f"{sha256[:18]}...{sha256[-10:]} ({size_bytes / 1024:.1f} KB)",
            "ok": True,
            "severity": "info",
        })
        # Check extension & magic bytes spoofing
        lower_fn = (filename or "").lower()
        ext = os.path.splitext(lower_fn)[1]
        head = raw_bytes[:16]
        is_pe = head.startswith(b"MZ")
        is_elf = head.startswith(b"\x7fELF")
        is_pdf = head.startswith(b"%PDF")
        is_zip = head.startswith(b"PK\x03\x04")
        is_apk = is_zip and (ext == ".apk" or b"AndroidManifest.xml" in raw_bytes[:65536])

        # Double extension check like factura.pdf.exe
        if re.search(r"\.(pdf|jpg|jpeg|png|docx?|xlsx?)\.(exe|scr|bat|vbs|ps1|apk|js|msi)$", lower_fn):
            risk += 65
            checks.append({
                "label": "Doble Extensión Engañosa",
                "status": f"Posible malware disfrazado: {filename}",
                "ok": False,
                "severity": "danger",
            })
        elif (is_pe or is_elf) and ext not in (".exe", ".dll", ".sys", ".elf", ""):
            risk += 70
            checks.append({
                "label": "Cabecera Binaria (Magic Bytes)",
                "status": f"Ejecutable binario real oculto bajo extensión '{ext}'",
                "ok": False,
                "severity": "danger",
            })
        elif is_apk:
            risk += 28
            checks.append({
                "label": "Paquete Instalador Android (APK)",
                "status": "Los APK fuera de Google Play son vía común de troyanos bancarios",
                "ok": False,
                "severity": "warn",
            })
        elif ext in EXECUTABLE_EXTENSIONS or is_pe or is_elf:
            risk += 25
            checks.append({
                "label": "Tipo de Archivo Ejecutable/Script",
                "status": f"Contiene código ejecutable ({ext or 'binario'})",
                "ok": False,
                "severity": "warn",
            })
        elif is_pdf:
            has_js_action = b"/JavaScript" in raw_bytes or b"/Launch" in raw_bytes or b"/OpenAction" in raw_bytes
            if has_js_action:
                risk += 35
                checks.append({
                    "label": "Inspección de Estructura PDF",
                    "status": "Contiene acciones automáticas (/OpenAction o /JavaScript)",
                    "ok": False,
                    "severity": "warn",
                })
            else:
                checks.append({
                    "label": "Cabecera PDF",
                    "status": "PDF estándar sin macros /JavaScript ni /Launch",
                    "ok": True,
                    "severity": "safe",
                })

    # Query VirusTotal API v3, AlienVault OTX & MalwareBazaar in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_vt = (
            pool.submit(
                _safe_json_get,
                f"https://www.virustotal.com/api/v3/files/{sha256}",
                {"x-apikey": keys["vt"]},
                7.0,
            )
            if keys["vt"]
            else None
        )
        f_otx = pool.submit(
            _safe_json_get,
            f"https://otx.alienvault.com/api/v1/indicators/file/{sha256}/general",
            None,
            6.5,
        )
        f_mb = (
            pool.submit(
                _safe_json_post,
                "https://mb-api.abuse.ch/api/v1/",
                None,
                {"query": "get_info", "hash": sha256},
                {"Auth-Key": keys["abusech"]},
                6.0,
            )
            if keys["abusech"]
            else None
        )

        vt_res = f_vt.result() if f_vt else (0, None)
        otx_st, otx_data = f_otx.result()
        mb_st, mb_data = f_mb.result() if f_mb else (0, None)

    vt_gui = f"https://www.virustotal.com/gui/file/{sha256}"

    if keys["vt"]:
        vt_st, vt_data = vt_res
        if vt_st == 200 and isinstance(vt_data, dict):
            sources.append("VirusTotal API v3")
            attrs = vt_data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats") or {}
            mal = int(stats.get("malicious", 0))
            susp = int(stats.get("suspicious", 0))
            tot = sum(int(v) for v in stats.values() if isinstance(v, (int, float)))
            if mal >= 2:
                risk = max(risk, 96)
                checks.append({
                    "label": "VirusTotal (Antivirus)",
                    "status": f"MALWARE DETECTADO: {mal}/{tot} motores",
                    "ok": False,
                    "severity": "danger",
                })
            elif mal == 1 or susp >= 2:
                risk = max(risk, 68)
                checks.append({
                    "label": "VirusTotal (Antivirus)",
                    "status": f"SOSPECHOSO: {mal} maliciosos / {susp} sospechosos de {tot}",
                    "ok": False,
                    "severity": "warn",
                })
            else:
                checks.append({
                    "label": "VirusTotal (Antivirus)",
                    "status": f"0/{tot} detecciones en archivo conocido",
                    "ok": True,
                    "severity": "safe",
                })
        elif vt_st == 404:
            sources.append("VirusTotal API v3")
            checks.append({
                "label": "VirusTotal (Antivirus)",
                "status": "Hash aún no registrado en VirusTotal",
                "ok": True,
                "severity": "info",
            })
        else:
            checks.append({
                "label": "VirusTotal API v3",
                "status": f"Error HTTP {vt_st} consultando VirusTotal",
                "ok": True,
                "severity": "info",
            })
    else:
        checks.append({
            "label": "VirusTotal API v3",
            "status": "Requiere VT_API_KEY (gratis) para consulta automática en 70+ AV",
            "ok": True,
            "severity": "info",
        })

    if otx_st == 200 and isinstance(otx_data, dict):
        sources.append("AlienVault OTX")
        pulses = int((otx_data.get("pulse_info") or {}).get("count") or 0)
        if pulses > 0:
            risk = max(risk, 92 if pulses >= 3 else 72)
            checks.append({
                "label": "AlienVault OTX (Malware Intel)",
                "status": f"HASH MALICIOSO CONOCIDO: {pulses} pulsos de amenaza",
                "ok": False,
                "severity": "danger",
            })
        else:
            checks.append({
                "label": "AlienVault OTX",
                "status": "0 pulsos de malware registrados para este hash",
                "ok": True,
                "severity": "safe",
            })

    if mb_st == 200 and isinstance(mb_data, dict):
        sources.append("MalwareBazaar")
        if mb_data.get("query_status") == "ok" and mb_data.get("data"):
            sig = mb_data["data"][0].get("signature") or "Malware"
            risk = max(risk, 98)
            checks.append({
                "label": "Abuse.ch MalwareBazaar",
                "status": f"CONFIRMADO MALWARE ({sig})",
                "ok": False,
                "severity": "danger",
            })

    risk = max(0, min(100, risk))
    if risk >= 70:
        level = "danger"
        verdict = "PELIGRO CRÍTICO: MALWARE O ARCHIVO DE ALTO RIESGO"
        advice = "NO ejecutes ni instales este archivo. Elimínalo inmediatamente."
    elif risk >= 25:
        level = "warn"
        verdict = "PRECAUCIÓN: ARCHIVO EJECUTABLE / REQUIERE VERIFICACIÓN"
        advice = "Evita abrir ejecutables, scripts o APK de remitentes desconocidos; verifica el hash en VirusTotal antes de ejecutar."
    else:
        level = "safe"
        verdict = "SIN DETECCIONES EN BASES CONSULTADAS"
        advice = "No se hallaron coincidencias maliciosas para este hash."

    return {
        "type": "file",
        "target": filename or sha256,
        "sha256": sha256,
        "md5": md5,
        "risk_score": risk,
        "verdict_level": level,
        "verdict_title": verdict,
        "checks": checks,
        "evidence_sources": sources,
        "vt_url": vt_gui,
        "advice": advice,
        "sha256_report": sha256,
    }


# ---------------------------------------------------------------------------
# 3. REAL BANK RECEIPT / IMAGE FORENSICS
# ---------------------------------------------------------------------------

def _analyze_jpeg_ghosts(arr_rgb: np.ndarray) -> Tuple[bool, str]:
    """
    Re-compresses the image across JPEG qualities and compares which quality yields
    the minimum residual in top/middle/bottom horizontal bands.
    A pasted snippet from another compression history causes a band's best-fit quality
    to diverge sharply from the rest of the receipt.
    """
    h = arr_rgb.shape[0]
    if h < 180:
        return False, ""
    pil_orig = Image.fromarray(arr_rgb.astype(np.uint8), mode="RGB")
    qualities = [65, 75, 82, 88, 93]
    t1, t2 = h // 3, (2 * h) // 3
    band_errors: List[List[float]] = [[], [], []]
    f_orig = arr_rgb.astype(np.float32)

    for q in qualities:
        buf = io.BytesIO()
        pil_orig.save(buf, format="JPEG", quality=q, subsampling=0)
        buf.seek(0)
        rec = np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32)
        diff = np.mean(np.abs(f_orig - rec), axis=2)
        # Focus on higher-detail rows so large flat white borders don't mask signal
        band_errors[0].append(float(np.percentile(diff[:t1, :], 85)))
        band_errors[1].append(float(np.percentile(diff[t1:t2, :], 85)))
        band_errors[2].append(float(np.percentile(diff[t2:, :], 85)))

    best_qs = [qualities[int(np.argmin(errs))] for errs in band_errors]
    min_errs = [min(errs) for errs in band_errors]
    max_errs = [max(errs) for errs in band_errors]
    # Real divergence only if error curves actually separate meaningfully (> 0.6 level diff)
    q_spread = max(best_qs) - min(best_qs)
    curves_distinct = all((mx - mn) > 0.6 for mx, mn in zip(max_errs, min_errs))
    if q_spread >= 13 and curves_distinct:
        return True, f"Historial de compresión divergente entre franjas (Q óptima: {best_qs})"
    return False, f"Historial de compresión consistente por franja (Q: {best_qs})"


def _build_ela_side_by_side(orig_rgb: np.ndarray, diff_map: np.ndarray, out_path: Optional[str]) -> Optional[str]:
    """Creates a readable [Original | ELA Forensic Heatmap] PNG and returns base64 if needed."""
    h, w, _ = orig_rgb.shape
    max_side = 760
    scale = min(1.0, max_side / max(w, h))
    nw, nh = max(120, int(w * scale)), max(120, int(h * scale))

    orig_im = Image.fromarray(orig_rgb.astype(np.uint8), mode="RGB").resize((nw, nh), Image.Resampling.LANCZOS)

    # Per-pixel ELA magnitude scaled adaptively so tampered spikes glow bright cyan/yellow/red
    ela_mag = np.mean(diff_map, axis=2)
    p99 = float(np.percentile(ela_mag, 99.5))
    gain = 255.0 / max(18.0, min(60.0, p99 * 1.15))
    norm = np.clip(ela_mag * gain, 0.0, 255.0)

    # Cyber forensic colormap: deep navy -> cyan -> yellow -> magenta/red
    r = np.clip((norm - 95.0) * 2.1, 0, 255)
    g = np.clip(np.where(norm < 175.0, norm * 1.3, 255.0 - (norm - 175.0) * 2.5), 0, 255)
    b = np.clip(np.where(norm < 120.0, 24 + norm * 1.8, 240.0 - (norm - 120.0) * 1.7), 0, 255)
    heat_rgb = np.stack([r, g, b], axis=2).astype(np.uint8)
    heat_im = Image.fromarray(heat_rgb, mode="RGB").resize((nw, nh), Image.Resampling.BILINEAR)

    gap = 10
    canvas = Image.new("RGB", (nw * 2 + gap, nh + 34), (10, 14, 26))
    canvas.paste(orig_im, (0, 34))
    canvas.paste(heat_im, (nw + gap, 34))

    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        canvas.save(out_path, format="PNG", optimize=True)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def audit_bank_receipt(
    image_bytes: Optional[bytes] = None,
    image_path: Optional[str] = None,
    filename: str = "",
    save_heatmap_path: Optional[str] = None,
    include_b64_heatmap: bool = False,
) -> Dict[str, Any]:
    if image_bytes is None and image_path and os.path.isfile(image_path):
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        if not filename:
            filename = os.path.basename(image_path)

    if not image_bytes:
        return {"error": "No se recibieron bytes de imagen", "risk_score": 0, "verdict_level": "warn", "checks": []}

    sha256 = hashlib.sha256(image_bytes).hexdigest()
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img_format = (img.format or "UNKNOWN").upper()
        orig_size = img.size
        exif = img.getexif()
        info_dict = dict(img.info or {})
        quant_tables = getattr(img, "quantization", None)
        rgb = img.convert("RGB")
    except Exception as e:
        return {
            "error": f"Archivo de imagen inválido o corrupto: {e}",
            "risk_score": 50,
            "verdict_level": "warn",
            "checks": [],
        }

    checks: List[Dict[str, Any]] = []
    risk = 0
    w, h = orig_size

    checks.append({
        "label": "Archivo & Huella Digital",
        "status": f"{img_format} {w}x{h}px ({len(image_bytes)/1024:.1f} KB) | SHA256: {sha256[:12]}...",
        "ok": True,
        "severity": "info",
    })

    # ------------------------------------------------------------------
    # Check 1: Real Binary Metadata (EXIF + PNG text chunks + XMP + 8BIM)
    # ------------------------------------------------------------------
    meta_blobs: List[str] = []
    for k, v in info_dict.items():
        if isinstance(v, (str, bytes)):
            meta_blobs.append(f"{k}:{v[:800] if isinstance(v, str) else v[:800].decode('latin1', 'ignore')}")
    if exif:
        for tag_id, val in exif.items():
            # Tag 305 = Software, 271 = Make, 272 = Model, 306 = DateTime, 11 = ProcessingSoftware
            if tag_id in (11, 271, 272, 305, 306, 315, 33432, 37510):
                meta_blobs.append(f"tag{tag_id}:{str(val)[:300]}")

    # Scan header & trailer raw bytes + PNG text chunks
    raw_scan = image_bytes[:131072] + image_bytes[-65536:]
    if img_format == "PNG":
        pos = 8
        while pos + 12 <= len(image_bytes):
            try:
                clen = int.from_bytes(image_bytes[pos:pos + 4], "big")
                ctype = image_bytes[pos + 4:pos + 8]
                cdata = image_bytes[pos + 8:pos + 8 + clen]
                if ctype in (b"tEXt", b"iTXt"):
                    meta_blobs.append(cdata[:1000].decode("latin1", "ignore"))
                elif ctype == b"zTXt" and b"\x00\x00" in cdata:
                    key_b, comp_b = cdata.split(b"\x00", 1)
                    if comp_b[:1] == b"\x00":
                        try:
                            decomp = zlib.decompress(comp_b[1:])
                            meta_blobs.append(f"{key_b.decode('latin1', 'ignore')}:{decomp[:1000].decode('latin1', 'ignore')}")
                        except Exception:
                            pass
                pos += 12 + clen
            except Exception:
                break

    combined_meta = "\n".join(meta_blobs) + "\n" + raw_scan.decode("latin1", errors="ignore")
    found_editors: List[str] = []
    for needle, label in EDITOR_SIGNATURES:
        if needle.lower() in combined_meta.lower():
            if label not in found_editors:
                found_editors.append(label)

    # Ignore benign ICC/sRGB profile hits unless explicit editor tool present
    has_xmp_agent = "stEvt:softwareAgent" in combined_meta or "xmp:CreatorTool" in combined_meta
    if found_editors:
        risk += 68
        checks.append({
            "label": "Metadatos / Software Editor",
            "status": f"FIRMA DE EDICIÓN DETECTADA: {', '.join(found_editors[:3])}",
            "ok": False,
            "severity": "danger",
        })
    elif has_xmp_agent:
        risk += 38
        checks.append({
            "label": "Metadatos XMP",
            "status": "Contiene trazas XMP de software de edición gráfica",
            "ok": False,
            "severity": "warn",
        })
    elif exif and any(t in exif for t in (271, 272, 305)):
        sw = str(exif.get(305) or exif.get(272) or exif.get(271) or "").strip()
        checks.append({
            "label": "Metadatos EXIF",
            "status": f"Origen cámara/dispositivo: {sw[:45]}",
            "ok": True,
            "severity": "safe",
        })
    else:
        checks.append({
            "label": "Metadatos EXIF",
            "status": "Sin EXIF (normal al enviar foto comprimida por Telegram/WhatsApp)",
            "ok": True,
            "severity": "info",
        })

    # JPEG Quantization table inspection (detect non-standard quality vs re-save hints)
    if img_format == "JPEG" and quant_tables:
        q_luma = list(quant_tables.get(0, []))
        if q_luma and sum(q_luma[:4]) <= 6 and not found_editors:
            # Very high quality save-for-web / uncompressed buffer re-export check (informational)
            checks.append({
                "label": "Tabla de Cuantización JPEG",
                "status": f"Calidad muy alta detectada (DC_Q={q_luma[0]})",
                "ok": True,
                "severity": "info",
            })

    # ------------------------------------------------------------------
    # Check 2: Multi-Quality (Q90 & Q75) Error Level Analysis (ELA)
    # ------------------------------------------------------------------
    arr = np.asarray(rgb, dtype=np.float32)

    def _compute_ela_diff(q_val: int) -> np.ndarray:
        buf_q = io.BytesIO()
        rgb.save(buf_q, format="JPEG", quality=q_val, subsampling=0)
        buf_q.seek(0)
        arr_q = np.asarray(Image.open(buf_q).convert("RGB"), dtype=np.float32)
        return np.abs(arr - arr_q)

    diff_rgb_90 = _compute_ela_diff(90)
    diff_rgb_75 = _compute_ela_diff(75)

    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

    # Edge magnitude via finite differences
    gx = np.abs(gray[:, 1:] - gray[:, :-1])
    gy = np.abs(gray[1:, :] - gray[:-1, :])
    edge_2d = np.zeros_like(gray)
    edge_2d[:, :-1] += gx
    edge_2d[:-1, :] += gy

    # High-frequency Laplacian for smooth-patch / cover-up detection
    lap_2d = np.zeros_like(gray)
    lap_2d[1:-1, 1:-1] = np.abs(
        4.0 * gray[1:-1, 1:-1]
        - gray[:-2, 1:-1] - gray[2:, 1:-1]
        - gray[1:-1, :-2] - gray[1:-1, 2:]
    )

    bs = 16
    bh = h // bs
    bw = w // bs
    chosen_diff_map = diff_rgb_90

    if bh >= 4 and bw >= 4:
        ch, cw = bh * bs, bw * bs
        edge_blk = edge_2d[:ch, :cw].reshape(bh, bs, bw, bs).mean(axis=(1, 3))
        lap_blk = lap_2d[:ch, :cw].reshape(bh, bs, bw, bs).mean(axis=(1, 3))
        g_blk = gray[:ch, :cw].reshape(bh, bs, bw, bs)
        blk_ptp = g_blk.max(axis=(1, 3)) - g_blk.min(axis=(1, 3))
        blk_bg = np.median(g_blk, axis=(1, 3))

        # 2a) Text-stroke foreground ELA cluster analysis across BOTH Q90 & Q75
        stroke_mask = blk_ptp > 40.0
        best_cluster_ratio = 1.0
        best_cluster_z = 0.0
        best_cluster_diff = 0.0
        best_cluster_zone = "central"
        best_q_label = 90
        anom_blocks_90: List[Tuple[int, int]] = []

        for q_val, diff_rgb_q in ((90, diff_rgb_90), (75, diff_rgb_75)):
            ela_2d_q = np.mean(diff_rgb_q, axis=2)
            ela_blk = ela_2d_q[:ch, :cw].reshape(bh, bs, bw, bs).mean(axis=(1, 3))

            # Edge-normalized block outliers at Q90
            if q_val == 90:
                content_mask = edge_blk >= max(4.0, float(np.percentile(edge_blk, 58)))
                n_content = int(np.sum(content_mask))
                if n_content >= 10:
                    c_ela = ela_blk[content_mask]
                    c_edge = edge_blk[content_mask]
                    ratio = c_ela / np.sqrt(c_edge + 2.0)
                    med_r = float(np.median(ratio))
                    scale_r = max(1.4826 * float(np.median(np.abs(ratio - med_r))), 0.22)
                    z_r = (ratio - med_r) / scale_r
                    med_ela = float(np.median(c_ela))
                    scale_ela = max(1.4826 * float(np.median(np.abs(c_ela - med_ela))), 1.0)
                    z_raw = (c_ela - med_ela) / scale_ela
                    coords = np.argwhere(content_mask)
                    for idx in range(n_content):
                        if z_r[idx] > 4.2 and z_raw[idx] > 3.5 and (c_ela[idx] - med_ela) > 5.0 and c_ela[idx] > 10.5:
                            anom_blocks_90.append((int(coords[idx, 0]), int(coords[idx, 1])))

            # Text-stroke cluster disparity (catches both low-Q AND fresh high-Q pasted digits)
            e_blk_px = ela_2d_q[:ch, :cw].reshape(bh, bs, bw, bs)
            ink_tiles: List[Tuple[int, int, float]] = []
            for r_i, c_i in np.argwhere(stroke_mask):
                sub_g = g_blk[r_i, :, c_i, :]
                sub_e = e_blk_px[r_i, :, c_i, :]
                fg = np.abs(sub_g - blk_bg[r_i, c_i]) > 18.0
                if int(fg.sum()) >= 10:
                    ink_tiles.append((int(r_i), int(c_i), float(sub_e[fg].mean())))

            if len(ink_tiles) >= 8:
                vals = np.array([t[2] for t in ink_tiles])
                med_v = float(np.median(vals))
                mad_v = float(np.median(np.abs(vals - med_v)))
                row_groups: Dict[Tuple[int, int], List[float]] = {}
                for r_i, c_i, v in ink_tiles:
                    row_groups.setdefault((r_i // 2, c_i // 12), []).append(v)
                rg_stats = [
                    (k, float(np.mean(vs)))
                    for k, vs in row_groups.items()
                    if len(vs) >= 3
                ]
                if len(rg_stats) >= 4:
                    rg_med = float(np.median([x[1] for x in rg_stats]))
                    top_k, top_v = max(rg_stats, key=lambda x: x[1])
                    ratio_rg = top_v / max(rg_med, 0.25)
                    z_rg = (top_v - med_v) / max(1.4826 * mad_v, 0.8)
                    diff_rg = top_v - rg_med
                    if ratio_rg > best_cluster_ratio and diff_rg > 2.5:
                        best_cluster_ratio = ratio_rg
                        best_cluster_z = z_rg
                        best_cluster_diff = diff_rg
                        best_q_label = q_val
                        avg_y = (top_k[0] * 2) / max(1, bh)
                        best_cluster_zone = "superior" if avg_y < 0.36 else "central" if avg_y < 0.68 else "inferior"
                        chosen_diff_map = diff_rgb_q

        # Combine both localized block spike and word-cluster multi-Q disparity
        n_anom_90 = len(anom_blocks_90)
        cluster_flag = best_cluster_ratio >= 1.95 and best_cluster_z >= 4.0 and best_cluster_diff >= 3.5
        block_flag = 2 <= n_anom_90 <= max(18, bw * bh // 8) and (
            (max(p[0] / bh for p in anom_blocks_90) - min(p[0] / bh for p in anom_blocks_90)) < 0.45 or n_anom_90 >= 4
        )

        if cluster_flag:
            risk += 48
            checks.append({
                "label": f"Mapa ELA Multi-Calidad (Q{best_q_label})",
                "status": f"ANOMALÍA LOCALIZADA en textos de zona {best_cluster_zone} ({best_cluster_ratio:.1f}x frente al resto del recibo)",
                "ok": False,
                "severity": "danger",
            })
        elif block_flag:
            ys = [pt[0] / bh for pt in anom_blocks_90]
            avg_y = sum(ys) / len(ys)
            zone_name = "superior" if avg_y < 0.36 else "central" if avg_y < 0.68 else "inferior"
            risk += 44 if n_anom_90 >= 4 else 28
            checks.append({
                "label": "Mapa ELA (Nivel de Error JPEG)",
                "status": f"ANOMALÍA LOCALIZADA en zona {zone_name} ({n_anom_90} bloques atípicos)",
                "ok": False,
                "severity": "danger" if n_anom_90 >= 4 else "warn",
            })
        else:
            checks.append({
                "label": "Mapa ELA (Q90 y Q75)",
                "status": "Distribución de compresión uniforme en los bloques de texto",
                "ok": True,
                "severity": "safe",
            })

        # 2b) Flat Cover-Up Patch / Eraser Detection in JPEG receipts:
        flat_bg_mask = edge_blk < 1.8
        n_flat_bg = int(np.sum(flat_bg_mask))
        suspicious_patches = 0
        patch_zones: List[str] = []
        if n_flat_bg >= 15:
            ambient_noise = float(np.median(lap_blk[flat_bg_mask]))
            ambient_luma = float(np.median(blk_bg[flat_bg_mask]))
            if ambient_noise >= 0.45:
                for r_i in range(1, bh - 1):
                    for c_i in range(1, bw - 1):
                        if edge_blk[r_i, c_i] < 4.5:
                            continue
                        block_gray = gray[r_i * bs:(r_i + 1) * bs, c_i * bs:(c_i + 1) * bs]
                        block_edge = edge_2d[r_i * bs:(r_i + 1) * bs, c_i * bs:(c_i + 1) * bs]
                        block_lap = lap_2d[r_i * bs:(r_i + 1) * bs, c_i * bs:(c_i + 1) * bs]
                        interior_bg = block_edge < 1.5
                        if np.sum(interior_bg) >= 60:
                            local_noise = float(np.median(block_lap[interior_bg]))
                            local_luma = float(np.median(block_gray[interior_bg]))
                            if local_noise < 0.06 and abs(local_luma - ambient_luma) < 35.0:
                                suspicious_patches += 1
                                patch_zones.append("superior" if (r_i / bh) < 0.36 else "central" if (r_i / bh) < 0.68 else "inferior")

        if suspicious_patches >= 3:
            dom_zone = max(set(patch_zones), key=patch_zones.count)
            risk += 40
            checks.append({
                "label": "Detector de Parches / Borrador",
                "status": f"Parche plano artificial junto a texto en zona {dom_zone} ({suspicious_patches} bloques)",
                "ok": False,
                "severity": "danger",
            })
        else:
            checks.append({
                "label": "Ruido de Fondo en Textos",
                "status": "Sin parches de borrado/tapado detectados",
                "ok": True,
                "severity": "safe",
            })

    heatmap_b64 = _build_ela_side_by_side(arr, chosen_diff_map, save_heatmap_path)

    # 2c) Multi-quality JPEG Ghost / Band Divergence
    ghost_flag, ghost_msg = _analyze_jpeg_ghosts(arr)
    if ghost_flag:
        risk += 34
        checks.append({
            "label": "Consistencia JPEG por Franjas",
            "status": ghost_msg,
            "ok": False,
            "severity": "danger",
        })
    else:
        checks.append({
            "label": "Consistencia JPEG por Franjas",
            "status": ghost_msg,
            "ok": True,
            "severity": "safe",
        })

    risk = max(0, min(100, int(round(risk))))
    if risk >= 60:
        level = "danger"
        verdict = "EVIDENCIA FORENSE DE EDICIÓN DETECTADA"
        advice = (
            "Se encontraron indicios técnicos reales de manipulación (metadatos de editor, anomalía ELA o parches). "
            "NO entregues productos ni dinero; verifica directamente en la app de tu banco."
        )
    elif risk >= 28:
        level = "warn"
        verdict = "ANOMALÍAS TÉCNICAS / POSIBLE RETOQUE"
        advice = (
            "La imagen presenta anomalías localizadas. Solicita el comprobante enviado como Documento original (sin comprimir) "
            "y confirma el abono directamente en tu cuenta bancaria."
        )
    else:
        level = "safe"
        verdict = "SIN RASTROS TÉCNICOS DE EDICIÓN EN PÍXELES"
        advice = (
            "El análisis de ELA, metadatos y compresión no detectó signos de Photoshop/recortes. "
            "⚠️ IMPORTANTE: ninguna herramienta externa puede consultar los saldos privados de tu banco ni detectar capturas creadas por apps simuladoras limpias. "
            "Verifica SIEMPRE el dinero acreditado dentro de tu app bancaria oficial."
        )

    out: Dict[str, Any] = {
        "type": "receipt",
        "target": filename or "Comprobante Bancario",
        "sha256": sha256,
        "dimensions": f"{w}x{h}",
        "format": img_format,
        "risk_score": risk,
        "verdict_level": level,
        "verdict_title": verdict,
        "checks": checks,
        "evidence_sources": ["EXIF/PNG/XMP Scanner", "Localized 16x16 ELA", "Patch Noise Detector", "JPEG Ghost Analysis"],
        "advice": advice,
        "sha256_report": sha256,
    }
    if include_b64_heatmap and heatmap_b64:
        out["ela_heatmap_base64"] = heatmap_b64
    return out


# ---------------------------------------------------------------------------
# 4. MULTI-CHAIN CRYPTO CONTRACT, WALLET, LICENSE & REPUTATION AUDITOR
# ---------------------------------------------------------------------------

def _rpc_call(rpc_url: str, method: str, params: list, timeout: float = 5.0) -> Any:
    st, data = _safe_json_post(
        rpc_url,
        json_body={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=timeout,
    )
    if st == 200 and isinstance(data, dict):
        return data.get("result")
    return None


def _probe_evm_chain(chain_tuple: Tuple[str, str, str, str, str], addr: str) -> Dict[str, Any]:
    cid, cname, native_sym, rpc_url, explorer = chain_tuple
    code = _rpc_call(rpc_url, "eth_getCode", [addr, "latest"])
    bal_hex = _rpc_call(rpc_url, "eth_getBalance", [addr, "latest"])
    nonce_hex = _rpc_call(rpc_url, "eth_getTransactionCount", [addr, "latest"])
    has_code = isinstance(code, str) and len(code) > 2 and code != "0x"
    bal = (int(bal_hex, 16) / 1e18) if isinstance(bal_hex, str) and bal_hex.startswith("0x") else 0.0
    nonce = int(nonce_hex, 16) if isinstance(nonce_hex, str) and nonce_hex.startswith("0x") else 0
    return {
        "chain_id": cid,
        "name": cname,
        "symbol": native_sym,
        "explorer": explorer + addr,
        "is_contract": has_code,
        "code_size": max(0, (len(code) - 2) // 2) if has_code else 0,
        "balance": bal,
        "nonce": nonce,
        "active": has_code or bal > 0 or nonce > 0,
    }


def _extract_spdx_from_sources(sources: Any) -> Optional[str]:
    if not isinstance(sources, dict):
        return None
    found: List[str] = []
    for _, val in sources.items():
        txt = val.get("content", "") if isinstance(val, dict) else str(val)
        m = re.search(r"SPDX-License-Identifier:\s*([^\r\n*/]+)", txt)
        if m:
            lic = m.group(1).strip()
            if lic and lic not in found:
                found.append(lic)
        else:
            m2 = re.search(r"@license\s+([^\r\n*/]+)", txt, re.I)
            if m2:
                lic = m2.group(1).strip()
                if lic and lic not in found:
                    found.append(lic)
    if not found:
        # Fallback: inspect textual license headers inside first source files
        for _, val in list(sources.items())[:8]:
            txt = (val.get("content", "") if isinstance(val, dict) else str(val))[:2000]
            if "GNU General Public License" in txt:
                found.append("GPL (texto en cabecera)")
                break
            if "MIT License" in txt or "Permission is hereby granted, free of charge" in txt:
                found.append("MIT (texto en cabecera)")
                break
            if "Apache License" in txt:
                found.append("Apache (texto en cabecera)")
                break
    return ", ".join(found[:3]) if found else None


def _lookup_evm_contract_source_and_license(chain_id: str, addr: str, etherscan_key: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "verified": False,
        "contract_name": None,
        "license_type": None,
        "compiler": None,
        "proxy_type": None,
        "implementation": None,
        "source": None,
    }

    # 1. Blockscout v2 where available (ETH & Optimism — gives exact license_type + proxy impl)
    bs_host = BLOCKSCOUT_V2_HOSTS.get(chain_id)
    if bs_host:
        st, bs = _safe_json_get(f"{bs_host}/api/v2/smart-contracts/{addr}", timeout=6.5)
        if st == 200 and isinstance(bs, dict) and (bs.get("is_verified") or bs.get("name")):
            out["verified"] = bool(bs.get("is_verified"))
            out["contract_name"] = bs.get("name")
            out["compiler"] = bs.get("compiler_version")
            out["proxy_type"] = bs.get("proxy_type")
            lic = bs.get("license_type")
            out["license_type"] = "Sin Licencia declarada (none)" if lic == "none" else (lic or None)
            out["source"] = "Blockscout v2"
            impls = bs.get("implementations") or []
            if impls and isinstance(impls[0], dict):
                out["implementation"] = impls[0].get("address_hash")
                if not lic or lic == "none":
                    _, impl_bs = _safe_json_get(f"{bs_host}/api/v2/smart-contracts/{out['implementation']}", timeout=5.5)
                    if isinstance(impl_bs, dict) and impl_bs.get("license_type") and impl_bs.get("license_type") != "none":
                        out["license_type"] = f"{impl_bs.get('license_type')} (en implementación)"

    # 2. Sourcify v2 (works across all EVM chains including BSC, Polygon, Arbitrum, Base, Avax)
    st_s, sdata = _safe_json_get(
        f"https://sourcify.dev/server/v2/contract/{chain_id}/{addr}?fields=compilation,sources",
        timeout=6.5,
    )
    if st_s == 200 and isinstance(sdata, dict):
        comp = sdata.get("compilation") or {}
        spdx = _extract_spdx_from_sources(sdata.get("sources"))
        out["verified"] = True
        out["contract_name"] = out["contract_name"] or comp.get("name")
        out["compiler"] = out["compiler"] or comp.get("compilerVersion")
        if spdx:
            out["license_type"] = spdx if not out["license_type"] or "none" in str(out["license_type"]).lower() else out["license_type"]
        out["source"] = (out["source"] + " + Sourcify v2") if out["source"] else "Sourcify v2"

    # 3. Etherscan v2 API (optional key — supports LicenseType directly across all chains)
    if etherscan_key and (not out["verified"] or not out["license_type"]):
        st_e, edata = _safe_json_get(
            f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=contract&action=getsourcecode&address={addr}&apikey={urllib.parse.quote(etherscan_key)}",
            timeout=6.5,
        )
        if st_e == 200 and isinstance(edata, dict) and edata.get("status") == "1":
            res_list = edata.get("result") or []
            if res_list and isinstance(res_list[0], dict):
                item = res_list[0]
                if item.get("SourceCode"):
                    out["verified"] = True
                    out["contract_name"] = out["contract_name"] or item.get("ContractName")
                    if item.get("LicenseType"):
                        out["license_type"] = item["LicenseType"]
                    out["source"] = (out["source"] + " + Etherscan v2") if out["source"] else "Etherscan v2"

    return out


def _format_goplus_address_complaints(gp_addr: Dict[str, Any]) -> Tuple[List[str], int, str]:
    """Extracts exact GoPlus address_security abuse flags and data sources."""
    flags_map = [
        ("sanctioned", "Sancionada (OFAC/Regulador)", 98),
        ("stealing_attack", "Robo de Fondos / Exploit Confirmado", 96),
        ("phishing_activities", "Actividades de Phishing / Drainer", 95),
        ("cybercrime", "Ciberdelito Reportado", 92),
        ("money_laundering", "Lavado de Activos", 90),
        ("financial_crime", "Delito Financiero", 90),
        ("blackmail_activities", "Extorsión / Chantaje", 90),
        ("darkweb_transactions", "Transacciones en Darknet", 88),
        ("blacklist_doubt", "En Lista Negra / Denuncias Sospechosas", 85),
        ("honeypot_related_address", "Relacionada a Contratos Honeypot", 88),
        ("fake_token", "Creador de Tokens Falsos", 85),
        ("fake_kyc", "KYC Falso Reportado", 75),
        ("malicious_mining_activities", "Minería Maliciosa", 82),
        ("mixer", "Uso de Mezclador / Tornado", 65),
        ("gas_abuse", "Abuso de Gas", 55),
    ]
    hits: List[str] = []
    max_risk = 0
    for field, desc, rscore in flags_map:
        if str(gp_addr.get(field)) == "1":
            hits.append(desc)
            max_risk = max(max_risk, rscore)
    mal_created = int(gp_addr.get("number_of_malicious_contracts_created") or 0)
    if mal_created > 0:
        hits.append(f"Creó {mal_created} contrato(s) malicioso(s)")
        max_risk = max(max_risk, 92)
    src = str(gp_addr.get("data_source") or "").strip()
    return hits, max_risk, src


def _detect_crypto_network(clean: str) -> str:
    if re.fullmatch(r"0x[a-fA-F0-9]{40}", clean):
        return "evm"
    if re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", clean):
        return "tron"
    if re.fullmatch(r"(?:EQ|UQ|kQ|0Q)[A-Za-z0-9_-]{46}", clean) or re.fullmatch(r"0:[a-fA-F0-9]{64}", clean):
        return "ton"
    if re.fullmatch(r"(?:1|3)[1-9A-HJ-NP-Za-km-z]{25,34}", clean) or re.fullmatch(r"bc1[a-z0-9]{25,62}", clean, re.I):
        return "btc"
    if SOLANA_B58_RE.fullmatch(clean):
        return "solana"
    return "unknown"


def _evaluate_token_security_fields(res: Dict[str, Any], checks: List[Dict[str, Any]], base_risk: int) -> int:
    risk = base_risk
    t_name = res.get("token_name") or "Token"
    t_sym = res.get("token_symbol") or ""
    if t_name or t_sym:
        checks.append({
            "label": "Token Detectado",
            "status": f"{t_name} ({t_sym})".strip(),
            "ok": True,
            "severity": "info",
        })

    holders_int = int(res.get("holder_count") or 0)
    is_cex_listed = isinstance(res.get("is_in_cex"), dict) and str(res["is_in_cex"].get("listed")) == "1"
    is_trusted_issuer = str(res.get("trust_list")) == "1" or is_cex_listed or holders_int >= 500000

    is_hp = str(res.get("is_honeypot")) == "1"
    cannot_sell = str(res.get("cannot_sell_all")) == "1"
    cannot_buy = str(res.get("cannot_buy")) == "1"
    try:
        buy_tax = float(res.get("buy_tax") or 0) * 100.0
    except Exception:
        buy_tax = 0.0
    try:
        sell_tax = float(res.get("sell_tax") or 0) * 100.0
    except Exception:
        sell_tax = 0.0

    if is_hp or cannot_sell or sell_tax >= 50.0:
        risk = max(risk, 98)
        checks.append({
            "label": "Prueba Honeypot & Venta",
            "status": f"TRAMPA HONEYPOT (Imp. Venta {sell_tax:.1f}% | Bloquea venta)",
            "ok": False,
            "severity": "danger",
        })
    else:
        warn_tax = sell_tax > 10.0 or buy_tax > 10.0 or cannot_buy
        if warn_tax:
            risk = max(risk, 48)
        checks.append({
            "label": "Prueba Honeypot & Comisiones",
            "status": f"Sin Honeypot | Compra {buy_tax:.1f}% / Venta {sell_tax:.1f}%",
            "ok": not warn_tax,
            "severity": "warn" if warn_tax else "safe",
        })

    flags = []
    priv_risk = risk
    if str(res.get("is_mintable")) == "1":
        flags.append("Mintable")
    if str(res.get("hidden_owner")) == "1":
        flags.append("Dueño oculto")
        priv_risk = max(priv_risk, 55)
    if str(res.get("owner_change_balance")) == "1":
        flags.append("Emisor puede modificar/congelar fondos")
        if not is_trusted_issuer:
            priv_risk = max(priv_risk, 92)
    if str(res.get("selfdestruct")) == "1":
        flags.append("Autodestruible (selfdestruct)")
        priv_risk = max(priv_risk, 75)
    if str(res.get("can_take_back_ownership")) == "1":
        flags.append("Puede recuperar ownership")
        if not is_trusted_issuer:
            priv_risk = max(priv_risk, 60)
    if str(res.get("transfer_pausable")) == "1":
        flags.append("Transferencias pausables")
    if str(res.get("is_blacklisted")) == "1":
        flags.append("Lista negra de cumplimiento")

    risk = max(risk, priv_risk)
    if flags:
        if is_trusted_issuer and priv_risk < 50:
            checks.append({
                "label": "Privilegios (Emisor Oficial / Trust List)",
                "status": f"Controles centralizados conocidos ({', '.join(flags[:3])})",
                "ok": True,
                "severity": "info",
            })
        else:
            checks.append({
                "label": "Privilegios del Contrato",
                "status": ", ".join(flags[:4]),
                "ok": False if priv_risk >= 55 else True,
                "severity": "danger" if priv_risk >= 70 else "warn" if priv_risk >= 45 else "info",
            })

    if "is_open_source" in res:
        is_os = str(res.get("is_open_source")) == "1"
        if not is_os:
            risk = max(risk, 62)
        checks.append({
            "label": "Código Fuente en GoPlus",
            "status": "Open Source Verificado" if is_os else "NO VERIFICADO (Código cerrado)",
            "ok": is_os,
            "severity": "safe" if is_os else "danger",
        })

    holders = res.get("holder_count")
    if holders:
        checks.append({
            "label": "Holders On-Chain",
            "status": f"{int(holders):,} titulares",
            "ok": True,
            "severity": "info",
        })
    return risk


def audit_crypto_address(raw_addr: str) -> Dict[str, Any]:
    clean = (raw_addr or "").strip()
    net = _detect_crypto_network(clean)
    keys = get_api_keys()
    checks: List[Dict[str, Any]] = []
    sources: List[str] = []
    risk = 0
    detected_chain = "Desconocida"
    account_type = "Desconocido"
    license_label = "N/A"
    explorer_url = ""

    if net == "unknown":
        return {
            "type": "crypto",
            "target": clean,
            "network": "Formato no reconocido",
            "account_type": "Inválido",
            "license_type": "N/A",
            "risk_score": 45,
            "verdict_level": "warn",
            "verdict_title": "DIRECCIÓN INVÁLIDA O FORMATO NO SOPORTADO",
            "checks": [{
                "label": "Validación de Formato",
                "status": "No coincide con EVM (0x), TRON (T...), Solana, Bitcoin ni TON",
                "ok": False,
                "severity": "warn",
            }],
            "evidence_sources": ["Validador Multi-Red"],
            "advice": "Verifica que copiaste la dirección completa sin espacios ni caracteres extra.",
            "sha256_report": _sha256_text(clean),
        }

    # ---------------- EVM (ETH, BSC, Polygon, Arb, Base, OP, Avax) ----------------
    if net == "evm":
        lower_addr = clean.lower()
        with ThreadPoolExecutor(max_workers=9) as pool:
            f_chains = [pool.submit(_probe_evm_chain, ch, clean) for ch in EVM_CHAINS]
            f_ss = pool.submit(_load_feed_cached, "scamsniffer_addrs", "https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json", 21600, _parse_json_list_lower, 8.0)
            chain_results = [fc.result() for fc in f_chains]
            ss_set = f_ss.result()

        sources.append("7x PublicNode EVM RPCs")
        contracts_on = [c for c in chain_results if c["is_contract"]]
        active_on = [c for c in chain_results if c["active"]]
        is_contract = len(contracts_on) > 0

        # If address holds bytecode on multiple EVM chains (e.g. CREATE2 bridge stub on ETH vs main contract on BSC),
        # inspect source verification + GoPlus token data across up to 3 contract chains and select the canonical primary.
        selected_src_info = None
        selected_gp_tok = (0, None)
        primary = contracts_on[0] if contracts_on else (active_on[0] if active_on else chain_results[0])

        if len(contracts_on) > 1:
            candidates = sorted(contracts_on, key=lambda c: c["code_size"], reverse=True)[:3]
            with ThreadPoolExecutor(max_workers=6) as pool:
                src_futs = [(cand, pool.submit(_lookup_evm_contract_source_and_license, cand["chain_id"], clean, keys["etherscan"])) for cand in candidates]
                tok_futs = [(cand, pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/token_security/{cand['chain_id']}?contract_addresses={clean}", None, 6.5)) for cand in candidates]
                best_score = -1
                for (cand, sf), (_, tf) in zip(src_futs, tok_futs):
                    s_info = sf.result()
                    t_res = tf.result()
                    has_tok = t_res[0] == 200 and bool((t_res[1] or {}).get("result"))
                    cand_score = (10 if s_info["verified"] else 0) + (5 if has_tok else 0) + min(4, cand["code_size"] // 1000)
                    if cand_score > best_score:
                        best_score = cand_score
                        primary = cand
                        selected_src_info = s_info
                        selected_gp_tok = t_res

        primary_cid = primary["chain_id"]
        detected_chain = primary["name"] if (contracts_on or active_on) else "EVM (Sin actividad en 7 redes principales)"
        explorer_url = primary["explorer"]
        account_type = f"Smart Contract ({primary['code_size']} bytes)" if is_contract else "Wallet Estándar (EOA)"

        if contracts_on:
            net_names = ", ".join(c["name"] for c in contracts_on)
            checks.append({
                "label": "Red y Tipo de Cuenta",
                "status": f"Principal: {primary['name']} (presente en: {net_names})" if len(contracts_on) > 1 else f"Smart Contract en {net_names}",
                "ok": True,
                "severity": "info",
            })
        elif active_on:
            net_names = ", ".join(f"{c['name']} ({c['balance']:.4f} {c['symbol']}, {c['nonce']} txs)" for c in active_on[:3])
            checks.append({
                "label": "Red y Tipo de Cuenta",
                "status": f"Wallet EOA activa en: {net_names}",
                "ok": True,
                "severity": "info",
            })
        else:
            risk = 25
            checks.append({
                "label": "Actividad en 7 Redes EVM",
                "status": "Dirección válida pero sin código ni historial en ETH/BSC/Poly/Arb/Base/OP/Avax",
                "ok": True,
                "severity": "warn",
            })

        with ThreadPoolExecutor(max_workers=4) as pool:
            f_gp_addr = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/address_security/{clean}?chain_id={primary_cid}", None, 6.5)
            f_gp_tok = (
                pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/token_security/{primary_cid}?contract_addresses={clean}", None, 6.5)
                if (is_contract and selected_gp_tok[0] == 0) else None
            )
            f_src = (
                pool.submit(_lookup_evm_contract_source_and_license, primary_cid, clean, keys["etherscan"])
                if (is_contract and selected_src_info is None) else None
            )
            gp_addr_st, gp_addr_data = f_gp_addr.result()
            gp_tok_res = f_gp_tok.result() if f_gp_tok else selected_gp_tok
            src_info = f_src.result() if f_src else selected_src_info

        # Reputation / Complaints check
        complaints: List[str] = []
        complaint_sources: List[str] = []
        if isinstance(ss_set, set) and lower_addr in ss_set:
            sources.append("ScamSniffer")
            complaints.append("Marcada como Wallet Drainer / Phishing en ScamSniffer")
            complaint_sources.append("ScamSniffer")
            risk = max(risk, 97)

        if gp_addr_st == 200 and isinstance(gp_addr_data, dict) and gp_addr_data.get("result"):
            sources.append("GoPlus Address Security")
            gp_hits, gp_risk, gp_ds = _format_goplus_address_complaints(gp_addr_data["result"])
            complaints.extend(gp_hits)
            if gp_ds:
                complaint_sources.append(gp_ds)
            risk = max(risk, gp_risk)
        else:
            checks.append({
                "label": "Denuncias GoPlus Address Security",
                "status": "API no disponible temporalmente",
                "ok": True,
                "severity": "warn",
            })

        if complaints:
            src_note = f" (Fuente: {', '.join(complaint_sources)})" if complaint_sources else ""
            checks.append({
                "label": "Denuncias y Reputación On-Chain",
                "status": f"REPORTADA: {'; '.join(complaints[:4])}{src_note}",
                "ok": False,
                "severity": "danger",
            })
        elif gp_addr_st == 200:
            checks.append({
                "label": "Denuncias y Reputación On-Chain",
                "status": "0 denuncias de phishing, robo o sanciones (GoPlus + ScamSniffer)",
                "ok": True,
                "severity": "safe",
            })

        # Contract verification, SPDX License & Token Security
        if is_contract and src_info:
            if src_info.get("source"):
                sources.append(src_info["source"])
            if src_info["verified"]:
                cname_txt = src_info.get("contract_name") or "Verificado"
                checks.append({
                    "label": "Contrato Fuente",
                    "status": f"Verificado ({cname_txt})" + (f" [Proxy {src_info['proxy_type']}]" if src_info.get("proxy_type") else ""),
                    "ok": True,
                    "severity": "safe",
                })
                lic = src_info.get("license_type") or "Sin identificador SPDX explícito en cabecera"
                license_label = lic
                checks.append({
                    "label": "Tipo de Licencia (SPDX)",
                    "status": lic,
                    "ok": True,
                    "severity": "safe" if "Sin Licencia" not in lic else "info",
                })
            else:
                license_label = "No Verificado (Bytecode Cerrado)"
                risk = max(risk, 55)
                checks.append({
                    "label": "Contrato & Tipo de Licencia",
                    "status": "NO VERIFICADO en Sourcify/Blockscout (código cerrado, sin licencia auditable)",
                    "ok": False,
                    "severity": "warn",
                })

            tok_st, tok_data = gp_tok_res
            if tok_st == 200 and isinstance(tok_data, dict):
                tok_map = tok_data.get("result") or {}
                tok = tok_map.get(lower_addr) or (next(iter(tok_map.values())) if tok_map else None)
                if isinstance(tok, dict) and tok:
                    sources.append("GoPlus Token Security")
                    risk = _evaluate_token_security_fields(tok, checks, risk)

    # ---------------- TRON ----------------
    elif net == "tron":
        detected_chain = "TRON (TRC-20 / Mainnet)"
        explorer_url = f"https://tronscan.org/#/address/{clean}"
        tron_headers = {"TRON-PRO-API-KEY": keys["tron"]} if keys["tron"] else None
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_addr = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/address_security/{clean}?chain_id=tron", None, 6.5)
            f_tok = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/token_security/tron?contract_addresses={clean}", None, 6.5)
            f_tg = pool.submit(_safe_json_post, "https://api.trongrid.io/wallet/getcontract", {"value": clean, "visible": True}, None, tron_headers, 6.0)
            addr_st, addr_data = f_addr.result()
            tok_st, tok_data = f_tok.result()
            tg_st, tg_data = f_tg.result()

        is_tron_contract = tg_st == 200 and isinstance(tg_data, dict) and bool(tg_data.get("bytecode") or tg_data.get("abi"))
        account_type = f"Smart Contract TRON ({tg_data.get('name') or 'Contrato'})" if is_tron_contract else "Wallet TRON"
        if is_tron_contract:
            sources.append("TronGrid")
            has_abi = bool((tg_data.get("abi") or {}).get("entrys"))
            license_label = "Código ABI público en TronGrid (SPDX requiere API TronScan)" if has_abi else "Bytecode sin ABI público"
        checks.append({
            "label": "Red y Tipo de Cuenta",
            "status": f"{detected_chain} — {account_type}",
            "ok": True,
            "severity": "info",
        })

        if addr_st == 200 and isinstance(addr_data, dict) and addr_data.get("result"):
            sources.append("GoPlus Address Security")
            hits, gp_risk, gp_ds = _format_goplus_address_complaints(addr_data["result"])
            risk = max(risk, gp_risk)
            if hits:
                checks.append({
                    "label": "Denuncias y Reputación TRON",
                    "status": f"REPORTADA: {'; '.join(hits[:4])} ({gp_ds})",
                    "ok": False,
                    "severity": "danger",
                })
            else:
                checks.append({
                    "label": "Denuncias y Reputación TRON",
                    "status": "0 denuncias de phishing, robo o sanciones en GoPlus",
                    "ok": True,
                    "severity": "safe",
                })

        if tok_st == 200 and isinstance(tok_data, dict):
            tok = (tok_data.get("result") or {}).get(clean) or (tok_data.get("result") or {}).get(clean.lower())
            if isinstance(tok, dict) and tok:
                sources.append("GoPlus Token Security TRON")
                risk = _evaluate_token_security_fields(tok, checks, risk)

    # ---------------- SOLANA ----------------
    elif net == "solana":
        detected_chain = "Solana Mainnet"
        explorer_url = f"https://solscan.io/account/{clean}"
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_rpc = pool.submit(_rpc_call, "https://solana-rpc.publicnode.com", "getAccountInfo", [clean, {"encoding": "jsonParsed"}], 6.5)
            f_gp = pool.submit(_safe_json_get, f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={clean}", None, 6.5)
            f_rc = pool.submit(_safe_json_get, f"https://api.rugcheck.xyz/v1/tokens/{clean}/report/summary", None, 6.5)
            rpc_res = f_rpc.result()
            gp_st, gp_data = f_gp.result()
            rc_st, rc_data = f_rc.result()

        val = (rpc_res or {}).get("value") if isinstance(rpc_res, dict) else None
        if isinstance(val, dict):
            sources.append("Solana Mainnet RPC")
            lamports = int(val.get("lamports") or 0)
            sol_bal = lamports / 1e9
            pdata = val.get("data")
            if isinstance(pdata, dict) and pdata.get("program") == "spl-token":
                account_type = "Token SPL (Mint)"
                info = (pdata.get("parsed") or {}).get("info") or {}
                mint_auth = info.get("mintAuthority")
                freeze_auth = info.get("freezeAuthority")
                license_label = "Programa estándar SPL Token (TokenkegQfe...)"
                checks.append({
                    "label": "Red y Tipo de Cuenta",
                    "status": f"Token SPL en Solana | FreezeAuth: {'Sí' if freeze_auth else 'Renunciada'} | MintAuth: {'Activa' if mint_auth else 'Fija'}",
                    "ok": True,
                    "severity": "info",
                })
            elif val.get("executable"):
                account_type = "Programa / Smart Contract Solana"
                license_label = f"Owner: {val.get('owner', 'BPF Loader')}"
                checks.append({
                    "label": "Red y Tipo de Cuenta",
                    "status": f"Programa Ejecutable Solana ({sol_bal:.4f} SOL)",
                    "ok": True,
                    "severity": "info",
                })
            else:
                account_type = f"Wallet Solana ({sol_bal:.4f} SOL)"
                checks.append({
                    "label": "Red y Tipo de Cuenta",
                    "status": account_type,
                    "ok": True,
                    "severity": "info",
                })
        else:
            account_type = "Cuenta Solana sin saldo/inexistente"
            checks.append({
                "label": "Estado en Solana RPC",
                "status": "Cuenta sin fondos ni estado activo en Mainnet",
                "ok": True,
                "severity": "warn",
            })
            risk = 20

        if gp_st == 200 and isinstance(gp_data, dict):
            tok = (gp_data.get("result") or {}).get(clean)
            if isinstance(tok, dict) and tok:
                sources.append("GoPlus Solana")
                sol_trusted = str(tok.get("trusted_token")) == "1" or int(tok.get("holder_count") or 0) >= 250000
                meta = tok.get("metadata") or {}
                if meta.get("name"):
                    checks.append({
                        "label": "Metadata Token SPL",
                        "status": f"{meta.get('name')} ({meta.get('symbol')})" + (" — Token Confiable" if sol_trusted else ""),
                        "ok": True,
                        "severity": "safe" if sol_trusted else "info",
                    })
                if str((tok.get("freezable") or {}).get("status")) == "1":
                    if sol_trusted:
                        checks.append({"label": "Control de Emisor Oficial", "status": "Autoridad de congelamiento regulado (trusted_token)", "ok": True, "severity": "info"})
                    else:
                        risk = max(risk, 40)
                        checks.append({"label": "Control de Congelación", "status": "El creador puede congelar fondos (Freezable)", "ok": False, "severity": "warn"})
                if str((tok.get("mintable") or {}).get("status")) == "1":
                    checks.append({"label": "Suministro Mintable", "status": "Autoridad de minteo activa", "ok": True, "severity": "info"})

        if rc_st == 200 and isinstance(rc_data, dict) and "score" in rc_data:
            sources.append("RugCheck.xyz")
            rc_risks = rc_data.get("risks") or []
            dangers = [r.get("name") for r in rc_risks if isinstance(r, dict) and r.get("level") in ("danger", "error")]
            warns = [r.get("name") for r in rc_risks if isinstance(r, dict) and r.get("level") == "warn"]
            if dangers:
                risk = max(risk, 82)
                checks.append({
                    "label": "RugCheck.xyz Solana",
                    "status": f"RIESGOS CRÍTICOS: {', '.join(dangers[:3])}",
                    "ok": False,
                    "severity": "danger",
                })
            elif warns:
                risk = max(risk, 42)
                checks.append({
                    "label": "RugCheck.xyz Solana",
                    "status": f"Advertencias: {', '.join(warns[:3])}",
                    "ok": False,
                    "severity": "warn",
                })
            else:
                checks.append({
                    "label": "RugCheck.xyz Solana",
                    "status": f"Limpio (0 alertas | LP Locked: {rc_data.get('lpLockedPct', 0):.0f}%)",
                    "ok": True,
                    "severity": "safe",
                })

    # ---------------- BITCOIN ----------------
    elif net == "btc":
        detected_chain = "Bitcoin Mainnet"
        account_type = "Wallet Bitcoin (UTXO)"
        explorer_url = f"https://mempool.space/address/{clean}"
        st_b, bdata = _safe_json_get(f"https://mempool.space/api/address/{clean}", timeout=6.5)
        if st_b == 200 and isinstance(bdata, dict):
            sources.append("Mempool.space API")
            cs = bdata.get("chain_stats") or {}
            ms = bdata.get("mempool_stats") or {}
            txs = int(cs.get("tx_count") or 0) + int(ms.get("tx_count") or 0)
            funded = int(cs.get("funded_txo_sum") or 0)
            spent = int(cs.get("spent_txo_sum") or 0)
            bal_btc = max(0, funded - spent) / 1e8
            checks.append({
                "label": "Actividad Bitcoin (Mempool.space)",
                "status": f"Saldo: {bal_btc:.6f} BTC | {txs:,} transacciones reales",
                "ok": True,
                "severity": "safe" if txs > 0 else "info",
            })
            checks.append({
                "label": "Nota de Reputación BTC",
                "status": "Bitcoin no usa smart contracts; verifica denuncias de sextorsión/ransomware en Chainabuse",
                "ok": True,
                "severity": "info",
            })
        else:
            risk = 20
            checks.append({"label": "Mempool.space", "status": "No se pudo consultar la dirección en Mempool.space", "ok": True, "severity": "warn"})

    # ---------------- TON ----------------
    elif net == "ton":
        detected_chain = "TON Blockchain"
        explorer_url = f"https://tonviewer.com/{clean}"
        st_t, tdata = _safe_json_get(f"https://tonapi.io/v2/accounts/{urllib.parse.quote(clean)}", timeout=6.5)
        if st_t == 200 and isinstance(tdata, dict):
            sources.append("TonAPI v2")
            bal_ton = int(tdata.get("balance") or 0) / 1e9
            ifaces = tdata.get("interfaces") or []
            acc_name = tdata.get("name") or ""
            is_scam = bool(tdata.get("is_scam"))
            is_wallet = any("wallet" in str(i).lower() for i in ifaces)
            account_type = f"{'Wallet TON' if is_wallet else 'Smart Contract / Cuenta TON'}" + (f" ({acc_name})" if acc_name else "")
            license_label = ", ".join(ifaces[:3]) if ifaces else "Estándar TON"
            checks.append({
                "label": "Estado On-Chain TonAPI",
                "status": f"{account_type} | Saldo: {bal_ton:,.2f} TON | Estado: {tdata.get('status')}",
                "ok": True,
                "severity": "safe",
            })
            if is_scam:
                risk = 96
                checks.append({
                    "label": "Bandera Scam TonAPI",
                    "status": "MARCADA COMO SCAM (is_scam=true) EN TON",
                    "ok": False,
                    "severity": "danger",
                })
            else:
                checks.append({
                    "label": "Reputación TonAPI",
                    "status": "0 alertas scam (is_scam=false)",
                    "ok": True,
                    "severity": "safe",
                })
        else:
            risk = 25
            checks.append({"label": "TonAPI v2", "status": "Cuenta sin actividad registrada o API temporalmente limitada", "ok": True, "severity": "warn"})

    risk = max(0, min(100, int(round(risk))))
    if risk >= 70:
        level = "danger"
        verdict = "PELIGRO CRÍTICO: DENUNCIAS / CONTRATO MALICIOSO"
        advice = "NO envíes fondos ni firmes aprobaciones (Approve/Sign) con esta dirección."
    elif risk >= 35:
        level = "warn"
        verdict = "PRECAUCIÓN: CÓDIGO NO VERIFICADO O RIESGOS MODERADOS"
        advice = "Revisa permisos de contrato, liquidez y origen del proyecto antes de interactuar."
    else:
        level = "safe"
        verdict = "SIN DENUNCIAS NI TRAMPAS DETECTADAS"
        advice = "No se detectaron denuncias de robo ni honeypot en las fuentes consultadas. Revisa siempre lo que firmas en tu wallet."

    return {
        "type": "crypto",
        "target": clean,
        "network": detected_chain,
        "account_type": account_type,
        "license_type": license_label,
        "explorer_url": explorer_url,
        "risk_score": risk,
        "verdict_level": level,
        "verdict_title": verdict,
        "checks": checks,
        "evidence_sources": sources,
        "advice": advice,
        "sha256_report": _sha256_text(f"crypto|{clean}|{detected_chain}|{risk}"),
    }


# ---------------------------------------------------------------------------
# 5. MESSAGE & SOCIAL ENGINEERING AUDITOR (WITH AUTO URL/WALLET EXTRACTION)
# ---------------------------------------------------------------------------

def audit_message(text: str) -> Dict[str, Any]:
    clean = (text or "").strip()
    lower = clean.lower()
    checks: List[Dict[str, Any]] = []
    sources: List[str] = ["NLP Ingeniería Social + Extractores en Vivo"]
    risk = 0
    scam_categories: List[str] = []

    # 1. Social engineering pattern bank
    rules = [
        ("Empleo Falso de Likes / Tareas", 92, [
            (r"(dar likes|ver videos|suscrib|tiktok|youtube|mercadeo).*?(diarios|desde casa|reclutamiento|gana \$|usd diarios|salario diario)", 2),
            (r"(deposito|recarga|subir de nivel|vip\d|misi[oó]n prepagada).*(retirar|liberar)", 1),
        ]),
        ("Esquema Ponzi / Rentabilidad Garantizada", 94, [
            (r"(5% diario|10% diario|ganancias? garantizad|duplica tu capital|sin riesgo|arbitraje con ia|retiros instant[aá]neos)", 1),
            (r"(deposita m[ií]nimo|rendimiento fijo|ingresos pasivos garantizados)", 1),
        ]),
        ("Phishing Bancario / Urgencia de Bloqueo", 95, [
            (r"(cuenta (ha sido )?suspendida|bloqueo definitivo|actividad sospechosa|reactivar tu cuenta|actualiza tus datos bancarios|verificaci[oó]n urgente)", 1),
            (r"(c[oó]digo otp|token de seguridad|clave din[aá]mica|cvv|nip)", 1),
        ]),
        ("Robo de Frase Semilla / Cripto", 98, [
            (r"(frase semilla|seed phrase|12 palabras|24 palabras|clave privada|sincronizar wallet|validar billetera|connect wallet.*reclamar)", 1),
        ]),
        ("Estafa Aduanal / Romance / Paquetería", 90, [
            (r"(caja de rescate|aduana|tarifa aduanal|paquete retenido|herencia|sargento|misi[oó]n de paz|pagar el env[ií]o para liberar)", 1),
        ]),
        ("Falso Soporte / Recuperación de Fondos", 90, [
            (r"(soporte oficial de telegram|recuperamos tus fondos|crypto recovery|agente de soporte.*deposita)", 1),
        ]),
    ]

    for title, cat_risk, patterns in rules:
        hits = sum(weight for pat, weight in patterns if re.search(pat, lower, re.I))
        if hits >= 1:
            scam_categories.append(title)
            risk = max(risk, cat_risk)
            checks.append({
                "label": "Patrón de Ingeniería Social",
                "status": f"DETECTADO: {title}",
                "ok": False,
                "severity": "danger",
            })

    # 2. Extract embedded URLs and Crypto Wallets inside the message and run REAL live audits
    url_matches = re.findall(r"(?:https?://[^\s<>\"']+|\b[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.(?:com|net|org|xyz|top|club|click|site|info|io|co|me|ly|ru|tk|shop)\b(?:/[^\s<>\"']*)?)", clean, re.I)
    evm_matches = re.findall(r"\b0x[a-fA-F0-9]{40}\b", clean)
    tron_matches = re.findall(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b", clean)
    ton_matches = re.findall(r"\b(?:EQ|UQ)[A-Za-z0-9_-]{46}\b", clean)

    embedded_urls = list(dict.fromkeys([u.rstrip(".,;:!?)\"'") for u in url_matches]))[:2]
    embedded_wallets = list(dict.fromkeys(evm_matches + tron_matches + ton_matches))[:2]

    for eu in embedded_urls:
        u_res = audit_url(eu)
        sources.extend([f"URL({s})" for s in (u_res.get("evidence_sources") or [])[:2]])
        u_risk = int(u_res.get("risk_score", 0))
        risk = max(risk, u_risk)
        checks.append({
            "label": f"Enlace Incrustado ({u_res.get('domain', eu)[:26]})",
            "status": f"Riesgo {u_risk}% — {u_res.get('verdict_title', '')[:46]}",
            "ok": u_risk < 35,
            "severity": u_res.get("verdict_level", "warn"),
        })

    for ew in embedded_wallets:
        w_res = audit_crypto_address(ew)
        w_risk = int(w_res.get("risk_score", 0))
        risk = max(risk, w_risk)
        checks.append({
            "label": f"Wallet Incrustada ({ew[:10]}...{ew[-4:]})",
            "status": f"{w_res.get('network')} | Riesgo {w_risk}% — {w_res.get('verdict_title', '')[:40]}",
            "ok": w_risk < 35,
            "severity": w_res.get("verdict_level", "warn"),
        })

    if not checks:
        checks.append({
            "label": "Análisis Lingüístico & Extractores",
            "status": "Sin patrones de fraude conocidos ni enlaces/wallets sospechosos",
            "ok": True,
            "severity": "safe",
        })

    risk = max(0, min(100, risk))
    scam_title = ", ".join(scam_categories) if scam_categories else (
        "AMENAZA DETECTADA EN ENLACE/WALLET DEL MENSAJE" if risk >= 70 else "SIN PATRONES DE ESTAFA EVIDENTES"
    )
    if risk >= 70:
        level = "danger"
        verdict = f"ALERTA ROJA: {scam_title}"
        advice = "Bloquea al remitente. Nunca deposites dinero para 'desbloquear' pagos ni abras los enlaces del mensaje."
    elif risk >= 35:
        level = "warn"
        verdict = "PRECAUCIÓN: ELEMENTOS NO VERIFICADOS EN MENSAJE"
        advice = "Desconfía si te piden pagos previos, códigos OTP o acceso remoto."
    else:
        level = "safe"
        verdict = "BAJO RIESGO EN ANÁLISIS DE TEXTO"
        advice = "No se identificaron ganchos de estafa estructurados, aunque mantén cautela ante solicitudes de dinero."

    return {
        "type": "message",
        "target": clean[:120],
        "scam_type": scam_title,
        "risk_score": risk,
        "verdict_level": level,
        "verdict_title": verdict,
        "checks": checks,
        "evidence_sources": list(dict.fromkeys(sources)),
        "advice": advice,
        "sha256_report": _sha256_text(clean),
    }


# ---------------------------------------------------------------------------
# 6. TELEGRAM HTML FORMATTER (100% SAFE ESCAPING)
# ---------------------------------------------------------------------------

def classify_and_audit_text(raw_text: str) -> Dict[str, Any]:
    """Routes arbitrary user text (hash, crypto address, URL/domain, or prose) to the right real auditor."""
    clean = (raw_text or "").strip()
    if not clean:
        return {"type": "message", "target": "", "risk_score": 0, "verdict_level": "warn", "verdict_title": "TEXTO VACÍO", "checks": [], "advice": "Envía un enlace, dirección cripto o mensaje.", "sha256_report": _sha256_text("")}

    if " " not in clean:
        if re.fullmatch(r"(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", clean):
            return audit_file_or_hash(hash_str=clean)
        if _detect_crypto_network(clean) != "unknown":
            return audit_crypto_address(clean)
        if re.match(r"^https?://", clean, re.I) or ("." in clean and len(clean) >= 4):
            return audit_url(clean)

    # Single URL inside short text
    words = clean.split()
    if len(words) == 1 and re.match(r"^https?://", words[0], re.I):
        return audit_url(words[0])
    return audit_message(clean)


def format_telegram_html(res: Dict[str, Any]) -> str:
    esc = html.escape
    rtype = res.get("type", "url")
    score = res.get("risk_score", 0)
    level = res.get("verdict_level", "safe")
    verdict = res.get("verdict_title", "")
    badge = "🚨" if level == "danger" else "⚠️" if level == "warn" else "✅"

    titles = {
        "url": "🛡️ <b>INFORME FORENSE DE ENLACE / DOMINIO</b>",
        "file": "🛡️ <b>INFORME FORENSE DE ARCHIVO / HASH</b>",
        "receipt": "🛡️ <b>AUDITORÍA FORENSE DE COMPROBANTE</b>",
        "crypto": "🛡️ <b>AUDITORÍA MULTI-RED DE CONTRATO / WALLET</b>",
        "message": "🛡️ <b>INFORME DE INGENIERÍA SOCIAL</b>",
    }

    lines = [
        titles.get(rtype, "🛡️ <b>INFORME CYBERSHIELD AI</b>"),
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>Objetivo:</b> <code>{esc(str(res.get('target', ''))[:90])}</code>",
    ]

    if rtype == "url" and res.get("final_url") and res["final_url"].rstrip("/") != str(res.get("target", "")).rstrip("/"):
        lines.append(f"↪️ <b>Destino Final:</b> <code>{esc(str(res['final_url'])[:90])}</code>")

    if rtype == "crypto":
        lines.append(f"⛓️ <b>Red Detectada:</b> <code>{esc(str(res.get('network', '')))}</code>")
        lines.append(f"🧬 <b>Tipo:</b> <code>{esc(str(res.get('account_type', '')))}</code>")
        lines.append(f"📜 <b>Licencia SPDX:</b> <code>{esc(str(res.get('license_type', 'N/A')))}</code>")

    lines.append(f"📊 <b>Riesgo Real:</b> <code>{score}%</code> — {badge} <b>{esc(verdict)}</b>")
    lines.append("")
    lines.append("🔍 <b>Evidencia Verificada:</b>")

    check_lines: List[str] = []
    for chk in res.get("checks", [])[:12]:
        sev = chk.get("severity", "info")
        icon = "🚨" if sev == "danger" else "⚠️" if sev == "warn" else "✅" if sev == "safe" else "⚪"
        check_lines.append(f"{icon} <b>{esc(str(chk.get('label', '')))}:</b> {esc(str(chk.get('status', '')))}")

    footer: List[str] = []
    if res.get("evidence_sources"):
        footer.append("")
        footer.append(f"🛰️ <i>Fuentes: {esc(', '.join(res['evidence_sources'][:8]))}</i>")

    if res.get("vt_url"):
        footer.append(f"🔎 <a href=\"{esc(res['vt_url'])}\">Ver ficha directa en VirusTotal</a>")
    if res.get("explorer_url"):
        footer.append(f"🧭 <a href=\"{esc(res['explorer_url'])}\">Abrir en Explorador Oficial</a>")

    footer.append("")
    footer.append(f"💡 <b>Recomendación:</b> {esc(str(res.get('advice', '')))}")
    footer.append(f"🔐 <b>Evidencia SHA-256:</b> <code>{esc(str(res.get('sha256_report', ''))[:24])}...</code>")

    # Ensure Telegram 4096-char limit without cutting inside an HTML tag
    while check_lines and len("\n".join(lines + check_lines + footer)) > 4000:
        check_lines.pop()

    msg = "\n".join(lines + check_lines + footer)
    if len(msg) > 4050:
        msg = "\n".join(lines + footer)[:4050]
    return msg

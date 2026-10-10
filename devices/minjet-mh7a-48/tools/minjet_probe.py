#!/usr/bin/env python3
"""Read-only Testskript für die Minjet-Cloud (nur Standardbibliothek).

Ablauf: Login -> getInfo -> device/queryUserDeviceList -> optional Gerätedetails
und WebSocket-Mitschnitt. Es wird nichts am Gerät verändert.

Zugangsdaten per Umgebungsvariablen MINJET_USER / MINJET_PASS (sonst Prompt).
Die Ausgabe ist maskiert (Token, Seriennummer, MAC, E-Mail), kann also geteilt
werden. Mit --raw wird nichts maskiert (nur lokal ansehen!).
"""

import argparse
import base64
import getpass
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

BASE = "https://app.minjet-energy.com/prod-api"
WS_HOST = "app.minjet-energy.com"
WS_PATH = "/ws/device"

MASK_KEYS = {
    "token",
    "access_token",
    "password",
    "serialNum",
    "macAddress",
    "email",
    "userName",
    "nickName",
    "ip0",
    "deviceId",
    "avatar",
}


def mask(value):
    """Wert bis auf die ersten/letzten 2 Zeichen ausblenden."""
    text = str(value)
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def redact(obj, raw=False):
    if raw:
        return obj
    if isinstance(obj, dict):
        return {
            k: (mask(v) if k in MASK_KEYS and v not in (None, "") else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def request(path, method="GET", token=None, body=None, base=BASE, params=None):
    url = base + "/" + path.lstrip("/")
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as err:
        payload = err.read().decode(errors="replace")
        status = err.code
    try:
        return status, json.loads(payload)
    except ValueError:
        return status, {"_raw": payload[:500]}


def show(title, status, data, raw):
    print(f"\n=== {title} (HTTP {status})")
    print(json.dumps(redact(data, raw), indent=2, ensure_ascii=False))


def _recv_exact(sock, buf, count):
    """Puffer auf mindestens count Bytes auffüllen; EOFError bei Verbindungsende."""
    while len(buf) < count:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError
        buf += chunk
    return buf


def ws_listen(token, seconds, raw, host=WS_HOST, port=80):
    """Minimaler WebSocket-Client (ws://, ohne Fragmentierung/Kompression)."""
    key = base64.b64encode(os.urandom(16)).decode()
    deadline = time.monotonic() + seconds
    sock = socket.create_connection((host, port), timeout=10)
    handshake = (
        f"GET {WS_PATH}?token={token} HTTP/1.1\r\n"
        f"Host: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(handshake.encode())
    buf = b""
    try:
        while b"\r\n\r\n" not in buf:
            buf = _recv_exact(sock, buf, len(buf) + 1)
        header, _, buf = buf.partition(b"\r\n\r\n")
        print("\n=== WebSocket:", header.split(b"\r\n")[0].decode(errors="replace"))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print(f"(Ende nach {seconds}s)")
                break
            sock.settimeout(remaining)
            buf = _recv_exact(sock, buf, 2)
            opcode, length = buf[0] & 0x0F, buf[1] & 0x7F
            pos = 2
            if length in (126, 127):
                size = 2 if length == 126 else 8
                buf = _recv_exact(sock, buf, 2 + size)
                length, pos = int.from_bytes(buf[2 : 2 + size], "big"), 2 + size
            buf = _recv_exact(sock, buf, pos + length)
            payload, buf = buf[pos : pos + length], buf[pos + length :]
            if opcode == 8:
                print("(Server hat geschlossen)")
                break
            if opcode in (1, 2):
                text = payload.decode(errors="replace")
                try:
                    text = json.dumps(redact(json.loads(text), raw), ensure_ascii=False)
                except ValueError:
                    if not raw:
                        text = re.sub(r"[A-Za-z0-9]{16,}", "***", text)
                print("<-", text[:2000])
    except EOFError:
        print("(Verbindung beendet)")
    except (TimeoutError, OSError):
        print(f"(Ende nach {seconds}s)")
    finally:
        sock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", action="store_true", help="nichts maskieren")
    ap.add_argument(
        "--ws", type=int, metavar="SEK", help="WebSocket SEK Sekunden mitschneiden"
    )
    ap.add_argument("--base", default=BASE, help="API-Basis (Standard: Minjet-Cloud)")
    ap.add_argument("--out", help="Ausgabe zusätzlich als JSON in Datei schreiben")
    args = ap.parse_args()

    user = os.environ.get("MINJET_USER") or input("Minjet-Login (E-Mail): ")
    pw = os.environ.get("MINJET_PASS") or getpass.getpass("Passwort: ")

    results = {}
    status, data = request(
        "login", "POST", body={"username": user, "password": pw}, base=args.base
    )
    token = data.get("token") if isinstance(data, dict) else None
    show("login", status, data, args.raw)
    if not token:
        print("\nKein Token erhalten, Abbruch.")
        return 1
    results["login"] = data

    status, data = request("getInfo", token=token, base=args.base)
    show("getInfo", status, data, args.raw)
    results["getInfo"] = data

    status, data = request("device/queryUserDeviceList", token=token, base=args.base)
    show("device/queryUserDeviceList", status, data, args.raw)
    results["devices"] = data

    devices = []
    if isinstance(data, dict):
        found = data.get("data", data.get("rows"))
        if isinstance(found, list):
            devices = [d for d in found if isinstance(d, dict)]
    for dev in devices[:3]:
        for ident_key in ("deviceId", "serialNum"):
            ident = dev.get(ident_key)
            if ident is None:
                continue
            status, detail = request(
                f"photovoltaic/queryPhotovoltaic/{ident}", token=token, base=args.base
            )
            show(
                f"photovoltaic/queryPhotovoltaic/<{ident_key}>",
                status,
                detail,
                args.raw,
            )
            results[f"pv_{ident_key}"] = detail

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(redact(results, args.raw), fh, indent=2, ensure_ascii=False)
        print(f"\nGespeichert: {args.out}")

    if args.ws:
        ws_listen(token, args.ws, args.raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())

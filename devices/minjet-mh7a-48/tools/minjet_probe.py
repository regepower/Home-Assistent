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
import datetime
import getpass
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
import zoneinfo

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
    "deviceName",
    "productKey",
    "userId",
    "loginIp",
    "createTime",
    "loginDate",
    "bindTime",
    "activeTime",
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


def ws_listen(token, seconds, raw, host=WS_HOST, port=443, tls=True):
    """Minimaler WebSocket-Client (wss://, ohne Fragmentierung/Kompression)."""
    key = base64.b64encode(os.urandom(16)).decode()
    deadline = time.monotonic() + seconds
    sock = socket.create_connection((host, port), timeout=10)
    if tls:
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
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


WRITABLE_KEYS = {
    "batteryChargeLimit",
    "batteryDischargeLimit",
    "batteryPriorityModeStatus",
    "emCommStatus",
    "ratedPower",
}


def parse_value(text):
    for conv in (int, float):
        try:
            return conv(text)
        except ValueError:
            continue
    return text


def read_property(token, serial, key, base):
    _, data = request(
        f"photovoltaic/queryPhotovoltaic/{serial}", token=token, base=base
    )
    props = ((data.get("data") if isinstance(data, dict) else None) or {}).get(
        "properties"
    ) or {}
    return props.get(key)


def set_property(token, serial, key, value, base, raw):
    """Einzelnen Gerätewert setzen (Balcony: photovoltaic/setRatedPower/{SN})."""
    before = read_property(token, serial, key, base)
    print(f"\n=== SET {key}: {before!r} -> {value!r}")
    status, data = request(
        f"photovoltaic/setRatedPower/{serial}",
        "POST",
        token=token,
        base=base,
        body={"key": key, "value": value},
    )
    show("setRatedPower", status, data, raw)
    time.sleep(5)
    after = read_property(token, serial, key, base)
    print(f"Wert danach (nach 5 s): {after!r}")


def probe_extra(token, devices, base, raw, results):
    """Statistik- und Benachrichtigungsaufrufe der App (nur lesend)."""
    try:
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
    except zoneinfo.ZoneInfoNotFoundError:
        tz = datetime.timezone.utc
    today = datetime.datetime.now(tz).date()
    ranges = {
        "month": (today.replace(day=1), 1),
        "year": (today.replace(month=1, day=1), 2),
        "lifetime": (datetime.date(2023, 1, 1), 3),
    }
    for dev in devices[:1]:
        serial = dev.get("serialNum")
        if serial:
            # Die App nutzt dateType 1=Monat, 2=Jahr, 3=Lebensdauer
            for name, (start, date_type) in ranges.items():
                params = {
                    "serialNum": serial,
                    "startDate": start.isoformat(),
                    "endDate": today.isoformat(),
                    "dateType": date_type,
                }
                status, data = request(
                    "deviceReport/queryDeviceStatistics",
                    token=token,
                    base=base,
                    params=params,
                )
                show(f"queryDeviceStatistics [{name}]", status, data, raw)
                results[f"stats_{name}"] = data
            status, data = request(
                "deviceReport/queryPhotovoltaicPowerStatistics",
                token=token,
                base=base,
                params={"serialNum": serial, "dateTime": today.isoformat()},
            )
            show("queryPhotovoltaicPowerStatistics [heute]", status, data, raw)
            results["pv_power_today"] = data
        dev_id = dev.get("deviceId")
        if dev_id is not None:
            status, data = request(
                f"app/notice/queryDeviceDetailNoticeList/{dev_id}",
                token=token,
                base=base,
            )
            show("queryDeviceDetailNoticeList", status, data, raw)
            results["device_notices"] = data
    for path in ("app/notice/queryAppNoticeList", "app/notice/queryUnreadMessageCount"):
        status, data = request(path, token=token, base=base)
        show(path, status, data, raw)
        results[path] = data


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", action="store_true", help="nichts maskieren")
    ap.add_argument(
        "--ws", type=int, metavar="SEK", help="WebSocket SEK Sekunden mitschneiden"
    )
    ap.add_argument(
        "--extra",
        action="store_true",
        help="zusätzlich Statistik (Tag/Monat/Jahr) und Benachrichtigungen abrufen",
    )
    ap.add_argument(
        "--set",
        metavar="KEY=VALUE",
        help="Gerätewert schreiben (nur: " + ", ".join(sorted(WRITABLE_KEYS)) + ")",
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

    if args.extra:
        probe_extra(token, devices, args.base, args.raw, results)

    if args.set:
        key, _, text = args.set.partition("=")
        if key not in WRITABLE_KEYS or not text:
            print(f"--set: Key nicht erlaubt/leer: {key!r}")
            return 2
        serial = next((d.get("serialNum") for d in devices if d.get("serialNum")), None)
        if not serial:
            print("--set: keine Seriennummer gefunden")
            return 2
        set_property(token, serial, key, parse_value(text), args.base, args.raw)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(redact(results, args.raw), fh, indent=2, ensure_ascii=False)
        print(f"\nGespeichert: {args.out}")

    if args.ws:
        ws_listen(token, args.ws, args.raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())

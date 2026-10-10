# Minjet MH7A-48

Ziel: Auslesen/Steuern des Akkus in Home Assistant.

## App
- Name: Minjet, Paket `com.minjet.iot`, v2.0.4 (Android, Play Store)
- Hersteller laut App Store: Minjet Smart Energy Technology
- Gerät hat laut Besitzer BLE/WLAN/RS485/CAN, Zugriff bisher nur über App

## Offen
- Schnittstelle klären: BLE / WLAN / RS485 / CAN / Cloud?
- App identifizieren (Name, Paket-ID, Version)
- Traffic mitschneiden (HCI-Snoop / mitmproxy)
- Protokoll dokumentieren → `docs/protocol.md`

## Daten selbst extrahieren (Reproduktion)

Das Repo enthält keine Herstellerdateien (APK, `libapp.so`), nur eigene Erkenntnisse. Wer die Daten nachvollziehen will, extrahiert sie aus der eigenen, rechtmäßig installierten App:

1. APK vom eigenen Handy holen (Android, USB-Debugging an):
   ```sh
   adb shell pm path com.minjet.iot
   adb pull <Pfad>/base.apk
   adb pull <Pfad>/split_config.arm64_v8a.apk
   ```
2. `lib/arm64-v8a/libapp.so` und `libflutter.so` mit einem normalen `unzip` entpacken (nicht über Tools, die Binärdateien als Text behandeln, sonst ist die Datei beschädigt).
3. Strings/Endpunkte lesen: `strings -n 6 libapp.so`
4. Dart-AOT dekompilieren mit [blutter](https://github.com/worawit/blutter) (benötigt `cmake`, `ninja`, `clang`, `libicu-dev`, `libcapstone-dev`):
   ```sh
   python3 blutter.py <ordner_mit_libapp_und_libflutter> out
   ```
5. Optional: Live-Mitschnitt der eigenen Verbindung (mitmproxy / HAR-Export) zur Verifikation.

Ergebnisse stehen in [docs/protocol.md](docs/protocol.md). Nur für Interoperabilität mit dem eigenen Gerät und privat gedacht; Zugangsdaten und Tokens gehören nie ins Repo.

## Testskript (read-only)

`tools/minjet_probe.py` loggt sich in die Minjet-Cloud ein, listet die Geräte und liest die PV-Daten. Es ändert nichts am Gerät, nutzt nur die Standardbibliothek (Python ≥ 3.11) und maskiert Token, Seriennummer, MAC und E-Mail in der Ausgabe.

```sh
export MINJET_USER='mail@example.com'   # oder weglassen -> Prompt
export MINJET_PASS='...'
python3 tools/minjet_probe.py --out /tmp/minjet.json --ws 60
```

- `--ws SEK`: WebSocket zusätzlich SEK Sekunden mitschneiden
- `--extra`: zusätzlich Statistik und Benachrichtigungen abrufen
- `--set KEY=VALUE`: **schreibt** einen Wert am Gerät (nur `batteryChargeLimit`, `batteryDischargeLimit`, `batteryPriorityModeStatus`), zeigt Wert vor/nach 5 s. **Ungetestet gegen das echte Gerät**; `ratedPower` und `emCommStatus` sind bewusst gesperrt
- `--raw`: nicht maskieren (nur lokal ansehen, nie teilen)
- Zugangsdaten nie ins Repo schreiben

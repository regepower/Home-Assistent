# Reverse-Engineering-Notizen (Minjet MH7A-48)

Diese Notizen dokumentieren, wie die inoffizielle Cloud-Schnittstelle des Minjet-Balkonspeichers ermittelt wurde. Sie dienen der Interoperabilität mit dem **eigenen** Gerät (Home Assistant).

- Protokoll, Endpunkte, Felder und verifizierte Schreibzugriffe: [protocol.md](protocol.md)
- Nur lesendes Prüfskript: [`tools/minjet_probe.py`](../tools/minjet_probe.py)

## App

- Name: Minjet, Paket `com.minjet.iot` (Android, Play Store); Flutter-App (Dart AOT)
- Hersteller laut App Store: Minjet Smart Energy Technology
- Das Gerät hat laut Besitzer BLE, WLAN, RS485 und CAN; die Cloud ist der praktikable Weg (BLE nur für die Erstinbetriebnahme)

## Daten selbst extrahieren (Reproduktion)

Das Repo enthält keine Herstellerdateien (APK, `libapp.so`, dekompilierter Code), nur eigene Erkenntnisse. Wer die Daten nachvollziehen will, extrahiert sie aus der eigenen, rechtmäßig installierten App:

1. APK vom eigenen Handy holen (Android, USB-Debugging an):
   ```sh
   adb shell pm path com.minjet.iot
   adb pull <Pfad>/base.apk
   adb pull <Pfad>/split_config.arm64_v8a.apk
   ```
2. `lib/arm64-v8a/libapp.so` und `libflutter.so` mit einem normalen `unzip` entpacken (nicht über Tools, die Binärdateien als Text behandeln, sonst ist die Datei beschädigt). Beide Dateien müssen aus **derselben** APK-Version stammen.
3. Strings/Endpunkte lesen: `strings -n 6 libapp.so`
4. Dart-AOT dekompilieren mit [blutter](https://github.com/worawit/blutter) (benötigt `cmake`, `ninja`, `clang`, `libicu-dev`, `libcapstone-dev`):
   ```sh
   python3 blutter.py <ordner_mit_libapp_und_libflutter> out
   ```
5. Optional: Live-Mitschnitt der eigenen Verbindung (mitmproxy / HAR-Export) zur Verifikation.

Zugangsdaten und Tokens gehören nie ins Repo.

## Testskript (read-only)

`tools/minjet_probe.py` loggt sich in die Minjet-Cloud ein, listet die Geräte und liest die PV-Daten. Es nutzt nur die Standardbibliothek (Python ≥ 3.11) und maskiert Token, Seriennummer, MAC und E-Mail in der Ausgabe.

```sh
export MINJET_USER='mail@example.com'   # oder weglassen -> Prompt
export MINJET_PASS='...'
python3 tools/minjet_probe.py --out /tmp/minjet.json --ws 60
```

- `--ws SEK`: WebSocket zusätzlich SEK Sekunden mitschneiden (**nur kurz verwenden**: solange der WebSocket offen ist, steht das Gerät im 2-s-Echtzeit-Modus)
- `--extra`: zusätzlich Statistik und Benachrichtigungen abrufen
- `--set KEY=VALUE`: **schreibt** einen Wert am Gerät (nur `batteryChargeLimit`, `batteryDischargeLimit`, `batteryPriorityModeStatus`), zeigt Wert vor/nach 5 s. Gegen das echte Gerät verifiziert sind `batteryChargeLimit` und `batteryPriorityModeStatus`; `ratedPower` und `emCommStatus` sind bewusst gesperrt
- `--raw`: nicht maskieren (nur lokal ansehen, nie teilen)
- Der GitHub-Workflow „Minjet probe" läuft **nur in privaten Repos** (Logs öffentlicher Repos sind für alle lesbar)

## Rechtliches

- Es sind keine Herstellerdateien (APK, Bibliotheken, dekompilierter Code) enthalten; Binärdateien werden per `.gitignore` ausgeschlossen.
- Die Cloud-Schnittstelle ist inoffiziell und kann sich jederzeit ändern. Prüfe die Nutzungsbedingungen von Minjet für deinen Fall.

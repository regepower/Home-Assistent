# Minjet für Home Assistant

🇬🇧 [English documentation](README.md)

Custom Integration für **Minjet-Balkonspeicher** (entwickelt gegen den **MH7A-48**). Sie nutzt dieselbe Cloud wie die offizielle Minjet-App und liefert Live-Daten per WebSocket (`cloud_push`), mit einem REST-Abruf alle 60 s als Rückfallebene.

> **Inoffiziell.** Dieses Projekt steht in keiner Verbindung zu Minjet und wird nicht von Minjet unterstützt. Die Cloud-Schnittstelle wurde zur Interoperabilität mit dem eigenen Gerät per Reverse Engineering ermittelt und kann sich jederzeit ändern. Nutzung auf eigene Gefahr.

[![Dieses Repository im HACS öffnen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=regepower&repository=Minjet&category=integration)

## Funktionen

- Batterie (%), Batterieleistung mit Vorzeichen, Batteriezustand, Solarleistung, Ausgangsleistung, Netzleistung (Smart Meter)
- Gesamtzähler (kWh) für das Energie-Dashboard und `utility_meter`
- Online-Status, Smart-Meter-Verbindung, Temperaturen, Zellspannungen, Limits (Diagnose)
- Steuerung: **Batterie-Prioritätsmodus** und **Ladegrenze**
- Reauth-Dialog, Diagnose-Download (Zugangsdaten und Seriennummer geschwärzt), deutsche und englische Texte

## Voraussetzungen

- Konto der Minjet-App (E-Mail und Passwort), Gerät dort bereits eingerichtet
- Home Assistant 2025.6 oder neuer (getestet mit 2026.2), Internetzugang zu `app.minjet-energy.com`

## Installation

### HACS (empfohlen)

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/regepower/Minjet`, Kategorie **Integration** (oder den Button oben nutzen).
2. **Minjet** installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Minjet* und mit den Zugangsdaten der Minjet-App anmelden.

### Manuell

Ordner `custom_components/minjet` in den Ordner `custom_components` deiner Home-Assistant-Konfiguration kopieren und neu starten.

## Entitäten

| Entität | Plattform | Hinweis |
|---|---|---|
| Batterie | sensor | Ladezustand in % |
| Batterieleistung | sensor | W, **positiv = lädt, negativ = entlädt** |
| Batteriezustand | sensor | `idle`, `charging`, `discharging` |
| Solarleistung | sensor | W |
| Ausgangsleistung | sensor | W, zum Wechselrichter |
| Netzleistung (Smart Meter) | sensor | W, **positiv = Bezug, negativ = Einspeisung** |
| Erzeugte / Verwendete Energie (gesamt) | sensor | kWh, `total_increasing` |
| Temperatur 1/2, Zellspannung min/max, Entladegrenze, Nennleistung | sensor | Diagnose |
| WLAN-Signal | sensor | Diagnose, standardmäßig deaktiviert |
| Online, Smart Meter verbunden | binary sensor | Konnektivität |
| Batterie-Prioritätsmodus | select | *Zuerst entladen* / *Energiespeicherung zuerst* |
| Ladegrenze | number | 20–100 %, nur im Modus *Energiespeicherung zuerst* |

### Steuerung

Nur diese zwei Einstellungen sind schreibbar, beide gegen die echte Cloud verifiziert:

- **Batterie-Prioritätsmodus** (`select`).
- **Ladegrenze** (`number`): Die Minjet-App blendet die Limits im Modus *Zuerst entladen* aus, daher ist die Entität dort **nicht verfügbar**. Der Wert muss über der Entladegrenze liegen.

Die Nennleistung ist bewusst **nur lesbar**: Bei eingeschaltetem Smart-Meter-Schalter regelt das Gerät sie selbst anhand deines Smart Meters.

## Tageswerte und Energie-Dashboard

Die Felder „heute" und „Monat" der Cloud sind in Wirklichkeit Gesamtzähler, und der Statistik-Endpunkt liefert nur Nullen. Tages- und Monatswerte bildest du in Home Assistant, zum Beispiel:

```yaml
utility_meter:
  minjet_solar_taeglich:
    source: sensor.akku_energy_generated_total   # an den Gerätenamen anpassen
    cycle: daily
  minjet_verbrauch_taeglich:
    source: sensor.akku_energy_used_total
    cycle: daily
```

Als Solarquelle im Energie-Dashboard nimmst du *Erzeugte Energie (gesamt)*. Die Cloud meldet keine Lade-/Entladeenergie der Batterie; bei Bedarf einen Integration-Helfer (Riemann-Summe) auf die *Batterieleistung* setzen.

## Fehlersuche

- **Login schlägt fehl:** Dieselbe E-Mail und dasselbe Passwort wie in der Minjet-App verwenden. Nach einer Passwortänderung fragt Home Assistant nach einer erneuten Anmeldung.
- **Keine Daten / Entitäten nicht verfügbar:** In der Minjet-App prüfen, ob das Gerät online ist. Der Sensor *Online* zeigt die Sicht der Cloud.
- **Debug-Logs:**
  ```yaml
  logger:
    logs:
      custom_components.minjet: debug
  ```
- **Fehler melden:** *Diagnose* der Integration herunterladen (Zugangsdaten, Seriennummer und IP sind geschwärzt) und dem Issue anhängen.

## Datenschutz und Sicherheit

Zugangsdaten liegen im Config-Entry-Speicher von Home Assistant und gehen nur an `app.minjet-energy.com`. Die WebSocket-URL enthält deinen Sitzungs-Token (so arbeitet der Dienst des Herstellers); Debug-Logs mit diesem Token nicht öffentlich posten. Es wird nichts an andere Stellen gesendet.

## Entwicklung

```sh
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

Das Repository enthält außerdem Recherche-Notizen und ein kleines, nur lesendes Prüfskript für die Minjet-Cloud, siehe [`docs/`](docs). Herstellerdateien sind nicht enthalten.

## Lizenz

[MIT](LICENSE). „Minjet" und verwandte Namen gehören ihren jeweiligen Inhabern.

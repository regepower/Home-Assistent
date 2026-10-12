# Minjet für Home Assistant

🇬🇧 [English documentation](README.md)

Custom Integration für **Minjet-Balkonspeicher** (entwickelt gegen den **MH7A-48**). Sie nutzt dieselbe Cloud wie die offizielle Minjet-App und fragt sie alle 60 s ab (`cloud_polling`), im selben Takt, in dem das Gerät selbst meldet.

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
| Letzte Warnung | sensor | Zeitpunkt der letzten Warnung (z. B. „Niedrige SOC"); Text in den Attributen `message` und `title` |
| Warnung | event | Löst `warning` aus, wenn die Cloud eine **neue** Meldung ausgibt; als Automations-Trigger nutzbar |
| Batterie-Prioritätsmodus | select | *Zuerst entladen* / *Energiespeicherung zuerst* |
| Ladegrenze | number | 20–100 %, nur im Modus *Energiespeicherung zuerst* |

### Warnmeldungen

Die Cloud gibt Meldungen wie *Niedrige SOC* einmal täglich aus. Die Integration liest sie alle 60 s. Die Entität **Warnung** löst nur für Meldungen aus, die neuer sind als die beim Start bekannte; ein Neustart löst alte Warnungen also nicht erneut aus. Beispiel für einen Automations-Trigger:

```yaml
trigger:
  - trigger: state
    entity_id: event.akku_warning   # an den Gerätenamen anpassen
action:
  - action: notify.mobile_app_handy
    data:
      message: "{{ trigger.to_state.attributes.message }}"
```

Die Cloud sendet Zeitstempel **ohne Zeitzone** in chinesischer Standardzeit (UTC+8). Die Integration rechnet sie um, daher stimmt *Letzte Warnung* in Home Assistant. Die Minjet-App zeigt dagegen die rohe Serverzeit an, deshalb steht dort z. B. 13:16 bei einer Meldung, die um 07:16 Ortszeit bei dir ankam.

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

Zugangsdaten liegen im Config-Entry-Speicher von Home Assistant und gehen nur an `app.minjet-energy.com`. Es wird nichts an andere Stellen gesendet. Debug-Logs vor dem Veröffentlichen auf Tokens prüfen.

## Zuletzt bekannte Werte

Fehlt ein Wert in der Cloud-Antwort, nach einem Neustart oder während einer kurzen Störung (bis 5 Minuten), zeigt die Integration den zuletzt bekannten Wert statt *unbekannt*/*nicht verfügbar*. Ob das Gerät selbst noch meldet, zeigt der Sensor *Online*.

## Warum kein Live-WebSocket?

Die Cloud bietet auch einen Live-WebSocket an. Solange er offen ist, schaltet die Cloud das Gerät aber in einen 2-Sekunden-„Echtzeit"-Upload. Die Minjet-App beendet diesen Modus, sobald man ihre Live-Ansicht verlässt. Eine dauerhaft offene Verbindung (Version 0.3.0) hielt das Gerät in diesem Modus und ließ es offline gehen. Deshalb fragt die Integration nur noch alle 60 s ab, wie die App im Hintergrund.

## Entwicklung

```sh
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

Das Repository enthält außerdem Recherche-Notizen und ein kleines, nur lesendes Prüfskript für die Minjet-Cloud, siehe [`docs/`](docs). Herstellerdateien sind nicht enthalten.

## Lizenz

[MIT](LICENSE). „Minjet" und verwandte Namen gehören ihren jeweiligen Inhabern.

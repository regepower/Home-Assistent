# Home-Assistent

Eigene Home-Assistant-Anbindungen für Hardware ohne brauchbare API/App (Reverse Engineering, nur privat).

## Home Assistant Integration „Minjet" (HACS)

Cloud-Anbindung für Minjet-Balkonspeicher (getestet mit **MH7A-48**). Live-Daten per WebSocket (`cloud_push`), REST-Abruf als Fallback alle 60 s.

**Installation über HACS**
1. HACS → ⋮ → *Benutzerdefinierte Repositories* → URL dieses Repos, Kategorie *Integration*.
2. „Minjet" installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → *Integration hinzufügen* → „Minjet" → Login der Minjet-App (E-Mail/Passwort).

**Entitäten pro Gerät:** Batterie (%), Batterieleistung (W, **+ = lädt, − = entlädt**), Batteriezustand, Solarleistung, Ausgangsleistung, Gesamt-Erzeugung/-Verbrauch (kWh, `total_increasing`, für Energie-Dashboard und `utility_meter`), Temperaturen, Zellspannungen, Entladegrenze, Nennleistung, Netzleistung (Smart Meter, **+ = Bezug, − = Einspeisung**), Online-Status, Smart-Meter-Verbindung. Standardmäßig deaktiviert: WLAN-Signal.

**Steuerung (v0.2):**
- `select` **Batterie-Prioritätsmodus**: „Zuerst entladen" / „Energiespeicherung zuerst".
- `number` **Ladegrenze** (20–100 %): nur im Modus „Energiespeicherung zuerst" verfügbar (die App blendet die Limits im anderen Modus ebenfalls aus); muss über der Entladegrenze liegen.
- Geschrieben werden nur diese zwei Werte, beide gegen die echte Cloud verifiziert. Nennleistung und Smart-Meter-Schalter werden bewusst nicht geschrieben (das Gerät regelt die Leistung selbst über den Smart Meter).

**Hinweise**
- Die „heute"-Felder der Cloud sind in Wahrheit Gesamtzähler; Tageswerte per `utility_meter` (daily/monthly) aus den Gesamt-Sensoren bilden.
- Details zum Protokoll und zu den Schreibzugriffen: [devices/minjet-mh7a-48](devices/minjet-mh7a-48).
- Inoffizielle Schnittstelle: kann sich jederzeit ändern. Zugangsdaten liegen nur in Home Assistant.

## Geräte

| Ordner | Gerät | Status |
|---|---|---|
| [devices/minjet-mh7a-48](devices/minjet-mh7a-48) | Minjet MH7A-48 Akku | HACS-Integration v0.2 (lesen + 2 Einstellungen) |

Struktur pro Gerät: `docs/` (Findings, Protokoll), `captures/` (Roh-Mitschnitte), `tools/` (Skripte).

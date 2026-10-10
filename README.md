# Home-Assistent

Eigene Home-Assistant-Anbindungen für Hardware ohne brauchbare API/App (Reverse Engineering, nur privat).

## Home Assistant Integration „Minjet" (HACS)

Cloud-Anbindung für Minjet-Balkonspeicher (getestet mit **MH7A-48**). Rein lesend, Live-Daten per WebSocket (`cloud_push`), REST-Abruf als Fallback alle 60 s.

**Installation über HACS**
1. HACS → ⋮ → *Benutzerdefinierte Repositories* → URL dieses Repos, Kategorie *Integration*.
2. „Minjet" installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → *Integration hinzufügen* → „Minjet" → Login der Minjet-App (E-Mail/Passwort).

**Entitäten pro Gerät:** Batterie (%), Batterieleistung (W, **+ = lädt, − = entlädt**), Batteriezustand, Solarleistung, Ausgangsleistung, Gesamt-Erzeugung/-Verbrauch (kWh, `total_increasing`, für Energie-Dashboard und `utility_meter`), Temperaturen, Zellspannungen, Lade-/Entladegrenze, Nennleistung, Prioritätsmodus, Online-Status, Smart-Meter-Verbindung. Standardmäßig deaktiviert: Smart-Meter-Leistung, WLAN-Signal.

**Hinweise**
- Die „heute"-Felder der Cloud sind in Wahrheit Gesamtzähler; Tageswerte per `utility_meter` (daily/monthly) aus den Gesamt-Sensoren bilden.
- Schreibzugriffe (Limits, Modus) sind bewusst nicht enthalten, siehe [devices/minjet-mh7a-48](devices/minjet-mh7a-48).
- Inoffizielle Schnittstelle: kann sich jederzeit ändern. Zugangsdaten liegen nur in Home Assistant.

## Geräte

| Ordner | Gerät | Status |
|---|---|---|
| [devices/minjet-mh7a-48](devices/minjet-mh7a-48) | Minjet MH7A-48 Akku | HACS-Integration v0.1 (lesend) |

Struktur pro Gerät: `docs/` (Findings, Protokoll), `captures/` (Roh-Mitschnitte), `tools/` (Skripte).

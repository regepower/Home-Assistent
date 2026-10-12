# Changelog

## 0.5.6
- Integration icon is now the Minjet logo from the app.

## 0.5.5
- Priority mode, charge limit, discharge limit and *Live 5 min* are back in the **Controls** section (no entity category), so the auto-generated dashboard shows them.

## 0.5.4
- **Discharge limit** is now writable (`number`, 20–100 % in steps of 5, must stay below the charge limit). The old read-only sensor is removed automatically.
- Both limits are unavailable (greyed out) in *Discharge first* mode, as in the app.
- Priority mode, both limits and the *Live 5 min* button are now in the **Configuration** section; the *Controls* section is gone.

## 0.5.3
- New **Live 5 min** button: about 2-second updates for 5 minutes, like the live view in the Minjet app. The realtime mode is always ended afterwards (`closeRealTimeStatus`), also on reload, unload and Home Assistant shutdown.
- New **Live active** binary sensor (`on` while live mode runs).

## 0.5.2
- German names use Σ instead of „gesamt“: *Solar Σ*, *Erzeugt Σ*, *Verbraucht Σ* (English names and entity IDs unchanged).
- README: fixed `utility_meter` example entity IDs.

## 0.5.1
- All entity names and states shortened to at most 18 characters so they fit the companion app (for example *Solar total*, *Solar direct*, *To inverter*, *Charging power*, *Priority mode* / *Storage first*). A test enforces the limit for German and English.

## 0.5.0
- Clearer names: *Solar production* (total), *Output to inverter*, *Battery power (+ charging / − discharging)*. Entity IDs stay the same.
- New sensors: *Battery charging power*, *Battery discharging power* (both ≥ 0) and *Solar direct to inverter* (solar production minus charging).
- README explains the power flow with real examples.

## 0.4.1
- Sensors keep their last known value instead of showing *unknown* when the cloud leaves a value out (missing or `null`).
- After a Home Assistant restart, sensors show the last value from before the restart until the cloud delivers a new one.
- Short cloud outages (up to 5 minutes) keep the last values instead of switching everything to *unavailable*; longer outages still show *unavailable*.

## 0.4.0
- **Important fix:** the integration no longer keeps a WebSocket open. An open WebSocket switches the device into a 2-second realtime upload mode that the Minjet app normally ends when its live view closes; keeping it open permanently made the device drop offline (app and Home Assistant showed no values). The integration now only polls the cloud every 60 s (`cloud_polling`).
- Warning messages are read every 10 minutes instead of every minute.
- Please update and re-enable the integration if you disabled it because of the outage.

## 0.3.0
- New `event` entity "Warning": fires when the cloud issues a new warning message (for example low SOC). The message known at startup does not fire.
- New diagnostic `sensor` "Last warning" (timestamp, message and title as attributes).
- Cloud timestamps are converted from UTC+8 to UTC (the Minjet app shows the raw server time).

## 0.2.1
- Fix: an expired token on the WebSocket is renewed with a fresh login instead of immediately asking for reauthentication.
- Added brand icon, license, English and German documentation.
- Repository is now Minjet-only: research notes moved to `docs/`, probe script to `tools/`.

## 0.2.0
- New `select`: battery priority mode (discharge first / energy storage first).
- New `number`: charge limit (20–100 %), only available in "energy storage first" mode; must be above the discharge limit.
- Only two properties can be written, both verified against the real cloud. Rated power and the smart meter switch are intentionally read-only.
- Removed the read-only "priority mode" and "charge limit" sensors (replaced by the new entities).
- Grid power (smart meter) sensor is enabled by default (positive = import, negative = export).

## 0.1.0
- First version: config flow with reauth, WebSocket push with REST fallback, sensors, binary sensors, diagnostics (German and English translations).

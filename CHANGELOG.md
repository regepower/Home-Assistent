# Changelog

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

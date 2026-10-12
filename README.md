# Minjet for Home Assistant

[![Tests](https://github.com/regepower/Minjet/actions/workflows/tests.yml/badge.svg)](https://github.com/regepower/Minjet/actions/workflows/tests.yml)
[![Validate](https://github.com/regepower/Minjet/actions/workflows/validate.yml/badge.svg)](https://github.com/regepower/Minjet/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Custom integration for **Minjet balcony storage batteries** (developed against the **MH7A-48**). It talks to the same cloud as the official Minjet app and polls it every 60 s (`cloud_polling`), the same interval the device itself reports at.

🇩🇪 [Deutsche Anleitung](README.de.md)

> **Unofficial.** This project is not affiliated with, endorsed by or supported by Minjet. The cloud interface was reverse engineered for interoperability with your own device and may change or break at any time. Use at your own risk.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=regepower&repository=Minjet&category=integration)

## Features

- Battery level, charging/discharging power, battery state, solar total, solar direct, power to the inverter, grid power (smart meter)
- Lifetime energy counters (kWh) for the Energy dashboard and `utility_meter`
- Online status, smart meter connection, temperatures, cell voltages, limits (diagnostic)
- Controls: **battery priority mode** and **charge limit**
- Reauthentication flow, diagnostics download with redaction, English and German translations

## Requirements

- A Minjet app account (email and password) with the device already bound in the app
- Home Assistant 2025.6 or newer (tested with 2026.2), internet access to `app.minjet-energy.com`

## Installation

### HACS (recommended)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/regepower/Minjet`, category **Integration** (or use the button above).
2. Install **Minjet** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Minjet* and log in with your Minjet app credentials.

### Manual

Copy `custom_components/minjet` into the `custom_components` folder of your Home Assistant configuration and restart.

## Entities

| Entity | Platform | Notes |
|---|---|---|
| Battery | sensor | State of charge in % |
| Battery power | sensor | W, signed |
| Charging power / Discharging power | sensor | W, always ≥ 0 (for the Energy dashboard or Riemann-sum helpers) |
| Battery state | sensor | `idle`, `charging`, `discharging` |
| Solar total | sensor | W, everything the panels produce |
| Solar direct | sensor | W, solar production minus battery charging |
| To inverter | sensor | W, solar direct + battery discharging |
| Grid power | sensor | W, **positive = import, negative = export** |
| Generated total | sensor | kWh, `total_increasing` |
| Used total | sensor | kWh, `total_increasing` |
| Temperature 1 / 2, Cell voltage min / max, Discharge limit, Rated power | sensor | diagnostic |
| Wi-Fi signal | sensor | diagnostic, disabled by default |
| Online, Smart meter | binary sensor | connectivity |
| Last warning | sensor | Time of the latest warning (e.g. "Niedrige SOC"); text in the attributes `message` and `title` |
| Warning | event | Fires `warning` when the cloud issues a **new** message; use it as an automation trigger |
| Priority mode | select | *Discharge first* / *Storage first* |
| Charge limit | number | 20–100 %, only in *Storage first* mode |

### Power flow

```
Solar total = Solar direct + Charging power
To inverter = Solar direct + Discharging power
```

Example while discharging: solar 44.5 W, battery −108 W → output 152.5 W. While charging: solar 137.5 W, battery +38.7 W → output 98.8 W.

### Warning messages

The cloud issues messages such as *low SOC* once a day. The integration reads them every 60 s. The **Warning** event entity fires only for messages that are newer than the one known at startup, so a restart does not re-trigger old warnings. Example automation trigger:

```yaml
trigger:
  - trigger: state
    entity_id: event.akku_warning   # adjust to your device name
action:
  - action: notify.mobile_app_phone
    data:
      message: "{{ trigger.to_state.attributes.message }}"
```

The cloud sends timestamps **without a time zone** in China standard time (UTC+8). The integration converts them, so the *Last warning* time is correct in Home Assistant. The Minjet app shows the raw server time instead, which is why the app displays e.g. 13:16 for a message that reached you at 07:16 local time.

### Controls

Only these two settings are writable, and both were verified against the real cloud:

- **Priority mode** (`select`).
- **Charge limit** (`number`). The Minjet app hides the limits in *Discharge first* mode, so the entity is **unavailable** there. The value must be above the discharge limit.

The rated output power is intentionally **read-only**: while the smart meter switch is on, the device regulates it by itself based on your smart meter.

## Daily values and the Energy dashboard

The cloud's "today" and "month" fields are actually lifetime totals, and its statistics endpoint returns zeros. Build daily or monthly values in Home Assistant, for example:

```yaml
utility_meter:
  minjet_solar_daily:
    source: sensor.akku_generated_total   # entity ID of "Generated total"
    cycle: daily
  minjet_used_daily:
    source: sensor.akku_used_total        # entity ID of "Used total"
    cycle: daily
```

Use *Generated total* as the solar production source in the Energy dashboard. The cloud does not report battery charge/discharge energy; if you need it, add one integration (Riemann sum) helper each on *Charging power* and *Discharging power*.

## How it works

- Login: `POST /login`, bearer token; an expired token is renewed automatically; you are only asked to reauthenticate if the login itself fails.
- Data: the device list (including all live values) is polled every 60 s; warning messages every 10 minutes.
- Last known values: if the cloud leaves a value out, after a restart, or during a short outage (up to 5 minutes) the last known value is shown instead of *unknown*/*unavailable*. Check the *Online* sensor to see whether the device itself is reporting.
- **No WebSocket on purpose:** the cloud also offers a live WebSocket, but while it is open the device is switched to a 2-second "realtime" upload mode. The Minjet app ends that mode when you leave its live view; a permanently open connection kept the device in it and made it drop offline (seen with version 0.3.0). Polling every 60 s matches what the app does in the background.
- Writes: a single REST call per change; the new value is shown immediately and confirmed by the next update.

Details of the reverse engineering are in [`docs/`](docs).

## Troubleshooting

- **Cannot log in:** use the same email and password as in the Minjet app. After a password change Home Assistant asks you to reauthenticate.
- **No data / entities unavailable:** check that the device is online in the Minjet app. The *Online* sensor mirrors the cloud's view.
- **Debug logs:**
  ```yaml
  logger:
    logs:
      custom_components.minjet: debug
  ```
- **Report an issue:** download the integration's *diagnostics* (credentials, serial number and IP are redacted) and attach them to the issue.

## Privacy and security

Credentials are stored in Home Assistant's config entry storage and only sent to `app.minjet-energy.com`. Nothing is sent anywhere else. Do not post debug logs publicly without checking them for tokens.

## Development

```sh
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

The repository also contains research notes and a small read-only probe script for the Minjet cloud, see [`docs/`](docs). No vendor files are included.

## License

[MIT](LICENSE). "Minjet" and related names belong to their respective owners.

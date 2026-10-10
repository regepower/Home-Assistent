# Minjet for Home Assistant

[![Tests](https://github.com/regepower/Home-Assistent/actions/workflows/tests.yml/badge.svg)](https://github.com/regepower/Home-Assistent/actions/workflows/tests.yml)
[![Validate](https://github.com/regepower/Home-Assistent/actions/workflows/validate.yml/badge.svg)](https://github.com/regepower/Home-Assistent/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Custom integration for **Minjet balcony storage batteries** (developed against the **MH7A-48**). It talks to the same cloud as the official Minjet app and delivers live data via WebSocket (`cloud_push`), with a 60 s REST poll as fallback.

🇩🇪 [Deutsche Anleitung](README.de.md)

> **Unofficial.** This project is not affiliated with, endorsed by or supported by Minjet. The cloud interface was reverse engineered for interoperability with your own device and may change or break at any time. Use at your own risk.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=regepower&repository=Home-Assistent&category=integration)

## Features

- Battery level, signed battery power, battery state, solar power, output power, grid power (smart meter)
- Lifetime energy counters (kWh) for the Energy dashboard and `utility_meter`
- Online status, smart meter connection, temperatures, cell voltages, limits (diagnostic)
- Controls: **battery priority mode** and **charge limit**
- Reauthentication flow, diagnostics download with redaction, English and German translations

## Requirements

- A Minjet app account (email and password) with the device already bound in the app
- Home Assistant 2025.6 or newer (tested with 2026.2), internet access to `app.minjet-energy.com`

## Installation

### HACS (recommended)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/regepower/Home-Assistent`, category **Integration** (or use the button above).
2. Install **Minjet** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Minjet* and log in with your Minjet app credentials.

### Manual

Copy `custom_components/minjet` into the `custom_components` folder of your Home Assistant configuration and restart.

## Entities

| Entity | Platform | Notes |
|---|---|---|
| Battery | sensor | State of charge in % |
| Battery power | sensor | W, **positive = charging, negative = discharging** |
| Battery state | sensor | `idle`, `charging`, `discharging` |
| Solar power | sensor | W |
| Output power | sensor | W, to the inverter |
| Grid power (smart meter) | sensor | W, **positive = import, negative = export** |
| Energy generated (total) | sensor | kWh, `total_increasing` |
| Energy used (total) | sensor | kWh, `total_increasing` |
| Temperature 1 / 2, lowest / highest cell voltage, discharge limit, rated power | sensor | diagnostic |
| Wi-Fi signal | sensor | diagnostic, disabled by default |
| Online, Smart meter connected | binary sensor | connectivity |
| Battery priority mode | select | *Discharge first* / *Energy storage first* |
| Charge limit | number | 20–100 %, only in *Energy storage first* mode |

### Controls

Only these two settings are writable, and both were verified against the real cloud:

- **Battery priority mode** (`select`).
- **Charge limit** (`number`). The Minjet app hides the limits in *Discharge first* mode, so the entity is **unavailable** there. The value must be above the discharge limit.

The rated output power is intentionally **read-only**: while the smart meter switch is on, the device regulates it by itself based on your smart meter.

## Daily values and the Energy dashboard

The cloud's "today" and "month" fields are actually lifetime totals, and its statistics endpoint returns zeros. Build daily or monthly values in Home Assistant, for example:

```yaml
utility_meter:
  minjet_solar_daily:
    source: sensor.akku_energy_generated_total   # adjust to your device name
    cycle: daily
  minjet_used_daily:
    source: sensor.akku_energy_used_total
    cycle: daily
```

Use *Energy generated (total)* as the solar production source in the Energy dashboard. The cloud does not report battery charge/discharge energy; use an integration (Riemann sum) helper on *Battery power* if you need it.

## How it works

- Login: `POST /login`, bearer token; an expired token is renewed automatically; you are only asked to reauthenticate if the login itself fails.
- Live data: a WebSocket pushes the full device object about once per second while connected. Updates are applied at most every 5 s.
- Fallback: the device list is polled every 60 s; if the WebSocket drops it reconnects with back-off.
- Writes: a single REST call per change; the new value is shown immediately and confirmed by the next update.

Details of the reverse engineering are in [`devices/minjet-mh7a-48`](devices/minjet-mh7a-48).

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

Credentials are stored in Home Assistant's config entry storage and only sent to `app.minjet-energy.com`. The WebSocket URL contains your session token (that is how the vendor's service works), so do not post debug logs that include it publicly. Nothing is sent anywhere else.

## Development

```sh
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

The repository also contains research notes and a small read-only probe script for the Minjet cloud, see [`devices/minjet-mh7a-48`](devices/minjet-mh7a-48). No vendor files are included.

## License

[MIT](LICENSE). "Minjet" and related names belong to their respective owners.

"""Constants for the Minjet integration."""

from datetime import timedelta

DOMAIN = "minjet"

BASE_URL = "https://app.minjet-energy.com/prod-api"
WS_URL = "wss://app.minjet-energy.com/ws/device"

# REST polling is only a fallback; live data arrives through the WebSocket.
SCAN_INTERVAL = timedelta(seconds=60)

# Ignore WebSocket pushes that arrive faster than this (the cloud sends ~1/s).
WS_MIN_UPDATE_INTERVAL = 5.0
WS_RECEIVE_TIMEOUT = 120
WS_BACKOFF_MIN = 5
WS_BACKOFF_MAX = 300

# batteryPriorityModeStatus: confirmed against the app (0 = discharge first).
PRIORITY_MODES = {0: "discharge_first", 1: "storage_first"}
PRIORITY_MODE_STORAGE_FIRST = 1

# Only keys that were verified against the real cloud may be written.
KEY_CHARGE_LIMIT = "batteryChargeLimit"
KEY_PRIORITY_MODE = "batteryPriorityModeStatus"
WRITABLE_KEYS = frozenset({KEY_CHARGE_LIMIT, KEY_PRIORITY_MODE})

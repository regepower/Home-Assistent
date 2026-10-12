"""Constants for the Minjet integration."""

from datetime import timedelta

DOMAIN = "minjet"

BASE_URL = "https://app.minjet-energy.com/prod-api"

# The device reports every 60 s on its own; polling faster gains nothing.
# A permanently open WebSocket keeps the device in a 2 s "realtime" upload mode
# (the app ends that mode when its live view closes), which made the device drop
# offline in practice, so this integration only polls.
SCAN_INTERVAL = timedelta(seconds=60)

# Warning messages are issued about once a day; no need to ask every minute.
NOTICE_INTERVAL = timedelta(minutes=10)

# Keep showing the last values during short cloud hiccups before going unavailable.
STALE_AFTER = timedelta(minutes=5)

# batteryPriorityModeStatus: confirmed against the app (0 = discharge first).
PRIORITY_MODES = {0: "discharge_first", 1: "storage_first"}
PRIORITY_MODE_STORAGE_FIRST = 1

# Only keys that were verified against the real cloud may be written.
KEY_CHARGE_LIMIT = "batteryChargeLimit"
KEY_PRIORITY_MODE = "batteryPriorityModeStatus"
WRITABLE_KEYS = frozenset({KEY_CHARGE_LIMIT, KEY_PRIORITY_MODE})

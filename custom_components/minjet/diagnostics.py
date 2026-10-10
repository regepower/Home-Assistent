"""Diagnostics for Minjet."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MinjetConfigEntry

TO_REDACT = {
    "username",
    "password",
    "token",
    "serialNum",
    "deviceName",
    "macAddress",
    "deviceId",
    "productKey",
    "ip0",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MinjetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            async_redact_data(device, TO_REDACT)
            for device in entry.runtime_data.data.values()
        ],
    }

"""The Minjet integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MinjetApi
from .const import DOMAIN
from .coordinator import MinjetCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

type MinjetConfigEntry = ConfigEntry[MinjetCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MinjetConfigEntry) -> bool:
    """Set up Minjet from a config entry."""
    api = MinjetApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = MinjetCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_old_entities(hass, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MinjetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_old_entities(hass: HomeAssistant, coordinator: MinjetCoordinator) -> None:
    """Remove entities replaced in newer versions (discharge limit is now a number)."""
    registry = er.async_get(hass)
    for serial in coordinator.data:
        if entity_id := registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{serial}_discharge_limit"
        ):
            registry.async_remove(entity_id)

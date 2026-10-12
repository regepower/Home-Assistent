"""Data coordinator: REST polling."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinjetApi, MinjetAuthError, MinjetError
from .const import DOMAIN, NOTICE_INTERVAL, SCAN_INTERVAL

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class MinjetCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Holds all devices of an account, keyed by serial number."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: MinjetApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self._notices_fetched: float | None = None
        self._last_notices: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.api.async_get_devices()
        except MinjetAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinjetError as err:
            raise UpdateFailed(str(err)) from err
        now = time.monotonic()
        if (
            self._notices_fetched is None
            or now - self._notices_fetched >= NOTICE_INTERVAL.total_seconds()
        ):
            try:
                self._last_notices = await self.api.async_get_notices()
                self._notices_fetched = now
            except MinjetAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except MinjetError as err:
                # warnings are a bonus: keep the previous ones, do not fail the update
                _LOGGER.debug("Could not read Minjet notices: %s", err)
        for serial, notice in self._last_notices.items():
            if serial in devices:
                devices[serial]["notice"] = notice
        return devices

    async def async_set_property(self, serial: str, key: str, value: int) -> None:
        """Write a property and update the local state optimistically.

        The device applies the value asynchronously; the next push or poll
        confirms it (or reverts the optimistic value if it was not applied).
        """
        try:
            await self.api.async_set_property(serial, key, value)
        except MinjetError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        data = dict(self.data)
        device = dict(data[serial])
        device["properties"] = {**(device.get("properties") or {}), key: value}
        data[serial] = device
        self.async_set_updated_data(data)

"""Data coordinator: REST polling plus WebSocket push."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinjetApi, MinjetAuthError, MinjetError
from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    WS_BACKOFF_MAX,
    WS_BACKOFF_MIN,
    WS_MIN_UPDATE_INTERVAL,
)

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
        self._last_push: dict[str, float] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.api.async_get_devices()
        except MinjetAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinjetError as err:
            raise UpdateFailed(str(err)) from err

    def start_websocket(self) -> None:
        """Start the push listener as a background task of the config entry."""
        assert self.config_entry is not None
        self.config_entry.async_create_background_task(
            self.hass, self._async_websocket_loop(), name="minjet websocket"
        )

    async def _async_websocket_loop(self) -> None:
        backoff = WS_BACKOFF_MIN
        while True:
            started = time.monotonic()
            try:
                await self.api.async_run_websocket(self.async_handle_push)
            except MinjetAuthError:
                # Most likely an expired token: log in again; only if that fails
                # too the credentials are wrong and the user has to reauthenticate.
                try:
                    await self.api.async_login()
                except MinjetAuthError:
                    _LOGGER.warning("Minjet login rejected, starting reauth")
                    assert self.config_entry is not None
                    self.config_entry.async_start_reauth(self.hass)
                    return
                except MinjetError as err:
                    _LOGGER.debug("Minjet re-login failed: %s", err)
            except MinjetError as err:
                _LOGGER.debug("Minjet websocket error: %s", err)
            if time.monotonic() - started > 60:
                backoff = WS_BACKOFF_MIN
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, WS_BACKOFF_MAX)

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

    def async_handle_push(self, device: dict[str, Any]) -> None:
        """Merge a pushed device object into the coordinator data."""
        serial = device["serialNum"]
        now = time.monotonic()
        if now - self._last_push.get(serial, 0.0) < WS_MIN_UPDATE_INTERVAL:
            return
        self._last_push[serial] = now
        data = dict(self.data or {})
        data[serial] = {**data.get(serial, {}), **device}
        self.async_set_updated_data(data)

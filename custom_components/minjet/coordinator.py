"""Data coordinator: REST polling."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinjetApi, MinjetAuthError, MinjetError
from .const import (
    DOMAIN,
    LIVE_DURATION,
    LIVE_MIN_UPDATE,
    NOTICE_INTERVAL,
    SCAN_INTERVAL,
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
        self._notices_fetched: float | None = None
        self._last_notices: dict[str, dict[str, Any]] = {}
        self.last_success: float | None = None
        self.live_serials: set[str] = set()
        self._last_push: dict[str, float] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.api.async_get_devices()
        except MinjetAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinjetError as err:
            raise UpdateFailed(str(err)) from err
        _keep_last_known_values(devices, self.data or {})
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
        self.last_success = now
        return devices

    async def _async_refresh(self, *args: Any, **kwargs: Any) -> None:
        await super()._async_refresh(*args, **kwargs)
        if not self.last_update_success:
            # Repeated failures do not notify listeners; let the entities re-check
            # whether the last values are now too old (STALE_AFTER).
            self.async_update_listeners()

    @callback
    def start_live(self, serial: str) -> None:
        """Start a time-limited live session (no-op while one is running)."""
        if serial in self.live_serials:
            return
        assert self.config_entry is not None
        self.live_serials.add(serial)
        self.config_entry.async_create_background_task(
            self.hass, self._async_live_session(serial), name=f"minjet live {serial}"
        )
        self.async_update_listeners()

    async def _async_live_session(self, serial: str) -> None:
        try:
            async with asyncio.timeout(LIVE_DURATION.total_seconds()):
                await self.api.async_query_detail(serial)
                await self.api.async_run_websocket(self._async_handle_push)
        except TimeoutError:
            pass
        except MinjetError as err:
            _LOGGER.warning("Minjet live mode ended early: %s", err)
        finally:
            # Always end the realtime mode, also on cancel (unload, shutdown).
            await asyncio.shield(self._async_end_live(serial))

    async def _async_end_live(self, serial: str) -> None:
        try:
            await self.api.async_close_realtime(serial)
        except MinjetError as err:
            _LOGGER.warning("Could not end the Minjet realtime mode: %s", err)
        finally:
            self.live_serials.discard(serial)
            self._last_push.pop(serial, None)
            self.async_update_listeners()

    @callback
    def _async_handle_push(self, device: dict[str, Any]) -> None:
        """Apply a live push (at most every LIVE_MIN_UPDATE seconds)."""
        serial = device.get("serialNum")
        if serial not in self.live_serials or serial not in (self.data or {}):
            return
        now = time.monotonic()
        if now - self._last_push.get(serial, 0.0) < LIVE_MIN_UPDATE:
            return
        self._last_push[serial] = now
        old = self.data[serial]
        merged = {**old, **device}
        merged["properties"] = {
            **(old.get("properties") or {}),
            **{
                k: v
                for k, v in (device.get("properties") or {}).items()
                if v is not None
            },
        }
        data = dict(self.data)
        data[serial] = merged
        self.last_success = now
        self.async_set_updated_data(data)

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


def _keep_last_known_values(
    devices: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]
) -> None:
    """Fill properties the cloud left out (missing or null) with the last value."""
    for serial, device in devices.items():
        old = (previous.get(serial) or {}).get("properties") or {}
        new = device.get("properties") or {}
        device["properties"] = {
            **old,
            **{key: value for key, value in new.items() if value is not None},
        }

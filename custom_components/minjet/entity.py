"""Base entity for Minjet."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STALE_AFTER
from .coordinator import MinjetCoordinator


class MinjetEntity(CoordinatorEntity[MinjetCoordinator]):
    """Entity bound to one device (serial number) of the account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial = serial
        device = coordinator.data[serial]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Minjet",
            model=device.get("productCode"),
            name=device.get("customName") or device.get("deviceName") or serial,
            serial_number=serial,
            sw_version=device.get("deviceCurrentVersion"),
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return the latest device object."""
        return self.coordinator.data.get(self._serial, {})

    @property
    def properties(self) -> dict[str, Any]:
        """Return the latest property dict of the device."""
        return self.device.get("properties") or {}

    @property
    def available(self) -> bool:
        """Stay available with the last values during short cloud outages."""
        if self._serial not in (self.coordinator.data or {}):
            return False
        if self.coordinator.last_update_success:
            return True
        last = self.coordinator.last_success
        return (
            last is not None and time.monotonic() - last < STALE_AFTER.total_seconds()
        )

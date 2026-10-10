"""Binary sensors for Minjet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .entity import MinjetEntity


@dataclass(frozen=True, kw_only=True)
class MinjetBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value extractor over the device object."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[MinjetBinarySensorDescription, ...] = (
    MinjetBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda device: (
            None
            if device.get("deviceStatus") is None
            else str(device["deviceStatus"]) == "1"
        ),
    ),
    MinjetBinarySensorDescription(
        key="smart_meter_connected",
        translation_key="smart_meter_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            None
            if (device.get("properties") or {}).get("emCommStatus") is None
            else (device["properties"]["emCommStatus"] == 1)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetBinarySensor(coordinator, serial, description)
        for serial in coordinator.data
        for description in BINARY_SENSORS
    )


class MinjetBinarySensor(MinjetEntity, BinarySensorEntity):
    """A binary sensor of a Minjet device."""

    entity_description: MinjetBinarySensorDescription

    def __init__(self, coordinator, serial: str, description) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"{serial}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.value_fn(self.device)

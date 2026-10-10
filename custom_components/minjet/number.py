"""Number entities for Minjet."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .const import (
    DOMAIN,
    KEY_CHARGE_LIMIT,
    KEY_PRIORITY_MODE,
    PRIORITY_MODE_STORAGE_FIRST,
)
from .coordinator import MinjetCoordinator
from .entity import MinjetEntity

DISCHARGE_LIMIT_KEY = "batteryDischargeLimit"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetChargeLimit(coordinator, serial) for serial in coordinator.data
    )


class MinjetChargeLimit(MinjetEntity, NumberEntity):
    """Charge limit in percent.

    The app only shows (and the device only uses) this limit in the mode
    "energy storage first", so the entity is unavailable otherwise.
    """

    _attr_translation_key = "charge_limit"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 20
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the number."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_charge_limit"

    @property
    def available(self) -> bool:
        """Only usable in the mode "energy storage first"."""
        return (
            super().available
            and self.properties.get(KEY_PRIORITY_MODE) == PRIORITY_MODE_STORAGE_FIRST
        )

    @property
    def native_value(self) -> float | None:
        """Return the current charge limit."""
        return self.properties.get(KEY_CHARGE_LIMIT)

    async def async_set_native_value(self, value: float) -> None:
        """Write the charge limit."""
        discharge = self.properties.get(DISCHARGE_LIMIT_KEY)
        if discharge is not None and value <= discharge:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="charge_limit_too_low",
                translation_placeholders={"discharge": str(int(discharge))},
            )
        await self.coordinator.async_set_property(
            self._serial, KEY_CHARGE_LIMIT, int(value)
        )

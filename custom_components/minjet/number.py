"""Number entities for Minjet."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .const import (
    DOMAIN,
    KEY_CHARGE_LIMIT,
    KEY_DISCHARGE_LIMIT,
    KEY_PRIORITY_MODE,
    PRIORITY_MODE_STORAGE_FIRST,
)
from .coordinator import MinjetCoordinator
from .entity import MinjetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for serial in coordinator.data
        for entity in (
            MinjetChargeLimit(coordinator, serial),
            MinjetDischargeLimit(coordinator, serial),
        )
    )


class MinjetLimit(MinjetEntity, NumberEntity):
    """Charge or discharge limit in percent.

    The app only shows (and the device only uses) the limits in the mode
    "energy storage first", so the entities are unavailable otherwise.
    """

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 20
    _attr_native_max_value = 100
    _attr_mode = NumberMode.BOX
    _key: str

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the number."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{self._attr_translation_key}"

    @property
    def available(self) -> bool:
        """Only usable in the mode "energy storage first"."""
        return (
            super().available
            and self.properties.get(KEY_PRIORITY_MODE) == PRIORITY_MODE_STORAGE_FIRST
        )

    @property
    def native_value(self) -> float | None:
        """Return the current limit."""
        return self.properties.get(self._key)

    def _validate(self, value: float) -> None:
        """Raise if the value conflicts with the other limit."""

    async def async_set_native_value(self, value: float) -> None:
        """Write the limit."""
        self._validate(value)
        await self.coordinator.async_set_property(self._serial, self._key, int(value))


class MinjetChargeLimit(MinjetLimit):
    """Charge limit; must stay above the discharge limit."""

    _attr_translation_key = "charge_limit"
    _attr_native_step = 1
    _key = KEY_CHARGE_LIMIT

    def _validate(self, value: float) -> None:
        discharge = self.properties.get(KEY_DISCHARGE_LIMIT)
        if discharge is not None and value <= discharge:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="charge_limit_too_low",
                translation_placeholders={"discharge": str(int(discharge))},
            )


class MinjetDischargeLimit(MinjetLimit):
    """Discharge limit; must stay below the charge limit.

    Only the app's values (20-100 in steps of 5) are offered.
    """

    _attr_translation_key = "discharge_limit"
    _attr_native_step = 5
    _key = KEY_DISCHARGE_LIMIT

    def _validate(self, value: float) -> None:
        charge = self.properties.get(KEY_CHARGE_LIMIT)
        if charge is not None and value >= charge:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="discharge_limit_too_high",
                translation_placeholders={"charge": str(int(charge))},
            )

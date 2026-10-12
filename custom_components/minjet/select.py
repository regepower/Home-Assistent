"""Select entities for Minjet."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .const import KEY_PRIORITY_MODE, PRIORITY_MODES
from .coordinator import MinjetCoordinator
from .entity import MinjetEntity

OPTION_TO_VALUE = {option: value for value, option in PRIORITY_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetPriorityModeSelect(coordinator, serial) for serial in coordinator.data
    )


class MinjetPriorityModeSelect(MinjetEntity, SelectEntity):
    """Battery priority mode: discharge first / energy storage first."""

    _attr_translation_key = "priority_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the select."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_priority_mode"
        self._attr_options = list(PRIORITY_MODES.values())

    @property
    def current_option(self) -> str | None:
        """Return the active mode."""
        raw = self.properties.get(KEY_PRIORITY_MODE)
        return None if raw is None else PRIORITY_MODES.get(int(raw))

    async def async_select_option(self, option: str) -> None:
        """Switch the mode."""
        await self.coordinator.async_set_property(
            self._serial, KEY_PRIORITY_MODE, OPTION_TO_VALUE[option]
        )

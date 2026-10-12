"""Button to start a short live session."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .coordinator import MinjetCoordinator
from .entity import MinjetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetLiveButton(coordinator, serial) for serial in coordinator.data
    )


class MinjetLiveButton(MinjetEntity, ButtonEntity):
    """Updates every ~2 s for 5 minutes, then back to the normal 60 s polling."""

    _attr_translation_key = "live"

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_live"

    async def async_press(self) -> None:
        """Start the live session."""
        self.coordinator.start_live(self._serial)

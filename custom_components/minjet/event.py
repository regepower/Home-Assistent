"""Event entity for Minjet warning messages."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MinjetConfigEntry
from .coordinator import MinjetCoordinator
from .entity import MinjetEntity

EVENT_WARNING = "warning"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinjetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinjetWarningEvent(coordinator, serial) for serial in coordinator.data
    )


class MinjetWarningEvent(MinjetEntity, EventEntity):
    """Fires when the cloud issues a new warning (for example "low SOC").

    The message that already exists at startup does not fire an event.
    """

    _attr_translation_key = "warning"

    def __init__(self, coordinator: MinjetCoordinator, serial: str) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_warning"
        self._attr_event_types = [EVENT_WARNING]
        self._last_time: datetime | None = (
            coordinator.data[serial].get("notice") or {}
        ).get("time")

    @callback
    def _handle_coordinator_update(self) -> None:
        notice = self.device.get("notice") or {}
        time = notice.get("time")
        if time is not None and (self._last_time is None or time > self._last_time):
            self._last_time = time
            self._trigger_event(
                EVENT_WARNING,
                {
                    "message": notice.get("message"),
                    "title": notice.get("title"),
                    "time": time.isoformat(),
                },
            )
        super()._handle_coordinator_update()

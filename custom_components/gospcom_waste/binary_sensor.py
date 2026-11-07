"""Binary sensor: is there a collection tomorrow?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import WasteEntity
from .texts import reminder_message, types_text
from .tracker import WasteConfigEntry, WasteTracker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    async_add_entities([TomorrowSensor(entry.runtime_data)])


class TomorrowSensor(WasteEntity, BinarySensorEntity):
    """On the day before a collection: time to put the waste out."""

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the binary sensor."""
        super().__init__(tracker, "tomorrow")

    @property
    def is_on(self) -> bool:
        """Return if there is a collection tomorrow."""
        return self.tracker.tomorrow() is not None

    @property
    def icon(self) -> str:
        """Show an alert bin while on."""
        return "mdi:delete-alert" if self.is_on else "mdi:delete-empty-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what goes out tomorrow."""
        collection = self.tracker.tomorrow()
        if collection is None:
            return {}
        return {
            "types": list(collection.types),
            "types_text": types_text(collection, self.tracker.language),
            "mixed": collection.has_mixed,
            "message": reminder_message(collection, self.tracker.language),
        }

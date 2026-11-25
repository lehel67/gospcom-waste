"""Binary sensor: is there a collection tomorrow?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BillEntity, WasteEntity
from .texts import reminder_message, types_text
from .tracker import WasteConfigEntry, WasteTracker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    tracker = entry.runtime_data
    async_add_entities([TomorrowSensor(tracker)])
    if tracker.bills is not None:
        async_add_entities(UnpaidSensor(tracker, code) for code in tracker.bills.data or {})


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


class UnpaidSensor(BillEntity, BinarySensorEntity):
    """On while something is left to pay on one customer code."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, tracker: WasteTracker, code: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(tracker, "unpaid", code)

    @property
    def is_on(self) -> bool | None:
        """Return if there is anything to pay."""
        return self.account.total_due > 0.005 if self.account else None

    @property
    def icon(self) -> str:
        """Show an alert receipt while on."""
        return "mdi:receipt-text-clock" if self.is_on else "mdi:receipt-text-check-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the open invoices."""
        if self.account is None:
            return {}
        return {
            "total_due": self.account.total_due,
            "open_invoices": [inv.as_dict() for inv in self.account.open_invoices],
        }

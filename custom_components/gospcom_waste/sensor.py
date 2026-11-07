"""Sensors: next collection, next mixed collection, countdown and what to put out."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PUT_OUT_ALL, PUT_OUT_SELECTIVE
from .entity import WasteEntity
from .schedule import Collection
from .texts import day_text, reminder_message, types_text
from .tracker import WasteConfigEntry, WasteTracker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    tracker = entry.runtime_data
    async_add_entities(
        [
            NextCollectionSensor(tracker),
            NextMixedSensor(tracker),
            DaysUntilSensor(tracker),
            PutOutSensor(tracker),
        ]
    )


def _details(tracker: WasteTracker, collection: Collection | None) -> dict[str, Any]:
    if collection is None:
        return {}
    language = tracker.language
    return {
        "date_text": day_text(collection.day, language),
        "types": list(collection.types),
        "types_text": types_text(collection, language),
        "mixed": collection.has_mixed,
        "moved": collection.moved,
        "planned": collection.planned.isoformat(),
        "days_until": (collection.day - tracker.today()).days,
        "message": reminder_message(collection, language),
    }


class NextCollectionSensor(WasteEntity, SensorEntity):
    """The day of the next collection (today included)."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the sensor."""
        super().__init__(tracker, "next_collection")

    @property
    def native_value(self) -> date | None:
        """Return the date of the next collection."""
        collection = self.tracker.next_collection()
        return collection.day if collection else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what is collected and the next few days."""
        upcoming = self.tracker.upcoming(6)
        return {
            **_details(self.tracker, upcoming[0] if upcoming else None),
            "upcoming": [
                {"date": c.day.isoformat(), "types": list(c.types), "moved": c.moved}
                for c in upcoming
            ],
            "street": self.tracker.street.hu,
            "street_ro": self.tracker.street.ro,
            "data_until": self.tracker.schedule.last_day.isoformat(),
        }


class NextMixedSensor(WasteEntity, SensorEntity):
    """The day mixed household waste is collected next (every other week)."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:trash-can"

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the sensor."""
        super().__init__(tracker, "next_mixed")

    @property
    def native_value(self) -> date | None:
        """Return the date of the next mixed collection."""
        collection = self.tracker.next_mixed()
        return collection.day if collection else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of that collection."""
        return _details(self.tracker, self.tracker.next_mixed())


class DaysUntilSensor(WasteEntity, SensorEntity):
    """Countdown: days until the next collection, 0 on the day itself."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the sensor."""
        super().__init__(tracker, "days_until")

    @property
    def native_value(self) -> int | None:
        """Return how many days are left."""
        collection = self.tracker.next_collection()
        return (collection.day - self.tracker.today()).days if collection else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the countdown to the next mixed collection too."""
        mixed = self.tracker.next_mixed()
        return {
            "days_until_mixed": (mixed.day - self.tracker.today()).days if mixed else None,
        }


class PutOutSensor(WasteEntity, SensorEntity):
    """What has to be put out for the next collection."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [PUT_OUT_ALL, PUT_OUT_SELECTIVE]

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the sensor."""
        super().__init__(tracker, "put_out")

    @property
    def native_value(self) -> str | None:
        """Return the kind of the next collection."""
        collection = self.tracker.next_collection()
        if collection is None:
            return None
        return PUT_OUT_ALL if collection.has_mixed else PUT_OUT_SELECTIVE

    @property
    def icon(self) -> str:
        """Show a full bin when mixed waste goes too."""
        return "mdi:delete-variant" if self.native_value == PUT_OUT_ALL else "mdi:recycle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the next collection."""
        return _details(self.tracker, self.tracker.next_collection())

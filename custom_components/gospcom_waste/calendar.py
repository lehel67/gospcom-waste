"""Calendar of the collections and the drop-off days."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import WasteEntity
from .schedule import Collection, DropOffDay
from .texts import day_text, texts, types_text
from .tracker import WasteConfigEntry, WasteTracker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WasteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar."""
    async_add_entities([WasteCalendar(entry.runtime_data)])


class WasteCalendar(WasteEntity, CalendarEntity):
    """Collections as all-day events, drop-off days as timed events."""

    _attr_icon = "mdi:calendar-blank-multiple"

    def __init__(self, tracker: WasteTracker) -> None:
        """Initialize the calendar."""
        super().__init__(tracker, "collections")

    def _collection_event(self, collection: Collection) -> CalendarEvent:
        language = self.tracker.language
        text = texts(language)
        description = []
        if collection.has_mixed:
            description.append(text["mixed_note"])
        if collection.moved:
            description.append(
                text["moved"].format(planned=day_text(collection.planned, language))
            )
        return CalendarEvent(
            start=collection.day,
            end=collection.day + timedelta(days=1),
            summary=text["calendar"].format(types=types_text(collection, language)),
            description="\n".join(description) or None,
            uid=f"{self.tracker.street.key}-{collection.day.isoformat()}",
        )

    def _drop_off_event(self, drop: DropOffDay) -> CalendarEvent:
        start_text, _, end_text = (drop.hours or "09:00-17:00").partition("-")
        tz = dt_util.get_default_time_zone()
        return CalendarEvent(
            start=datetime.combine(drop.day, time.fromisoformat(start_text.strip()), tz),
            end=datetime.combine(drop.day, time.fromisoformat(end_text.strip()), tz),
            summary=texts(self.tracker.language)["drop_off"],
            location="; ".join(drop.places) or None,
            uid=f"drop-off-{drop.day.isoformat()}",
        )

    def _events(self, start: date, end: date) -> list[CalendarEvent]:
        events = [
            self._collection_event(c)
            for c in self.tracker.schedule.collections(self.tracker.street, start, end)
        ]
        events += [
            self._drop_off_event(d) for d in self.tracker.schedule.drop_off_days(start, end)
        ]
        return sorted(events, key=lambda event: event.start_datetime_local)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next collection (today included)."""
        collection = self.tracker.next_collection()
        return self._collection_event(collection) if collection else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events between the two moments."""
        start = dt_util.as_local(start_date).date() - timedelta(days=1)
        end = dt_util.as_local(end_date).date()
        events = self._events(start, end)
        return [
            event
            for event in events
            if event.start_datetime_local < end_date and event.end_datetime_local > start_date
        ]

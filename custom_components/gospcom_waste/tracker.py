"""Keeps the entities of one street up to date and sends the evening reminder."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOTIFY_SERVICE,
    CONF_REMINDER_TIME,
    CONF_STREET,
    DEFAULT_REMINDER_TIME,
    DOMAIN,
    EVENT_REMINDER,
)
from .schedule import Collection, Schedule, Street
from .texts import reminder_message, texts, types_text

_LOGGER = logging.getLogger(__name__)

type WasteConfigEntry = ConfigEntry[WasteTracker]


class WasteTracker:
    """The schedule of one street, with change listeners and the reminder timer."""

    def __init__(self, hass: HomeAssistant, entry: WasteConfigEntry, schedule: Schedule) -> None:
        """Initialize the tracker."""
        self.hass = hass
        self.entry = entry
        self.schedule = schedule
        self.street: Street = schedule.streets[entry.data[CONF_STREET]]
        self.reminder_time: time = time.fromisoformat(
            entry.options.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME)
        )
        self.notify_service: str = (entry.options.get(CONF_NOTIFY_SERVICE) or "").strip()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def language(self) -> str:
        """Return the Home Assistant language."""
        return self.hass.config.language

    def today(self) -> date:
        """Return the local date."""
        return dt_util.now().date()

    def upcoming(self, count: int = 10) -> list[Collection]:
        """Return the next collections, today included."""
        return self.schedule.next_collections(self.street, self.today(), count)

    def next_collection(self) -> Collection | None:
        """Return the next collection, today included."""
        upcoming = self.upcoming(1)
        return upcoming[0] if upcoming else None

    def next_mixed(self) -> Collection | None:
        """Return the next collection that takes mixed waste too."""
        return next((c for c in self.upcoming(4) if c.has_mixed), None)

    def tomorrow(self) -> Collection | None:
        """Return tomorrow's collection, if there is one."""
        tomorrow = self.today() + timedelta(days=1)
        return next((c for c in self.upcoming(2) if c.day == tomorrow), None)

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Call update whenever the day changes or the reminder time passes."""
        self._listeners.append(update)

        @callback
        def remove() -> None:
            self._listeners.remove(update)

        return remove

    @callback
    def _update_listeners(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def async_start(self) -> None:
        """Start the midnight refresh and the reminder timer."""

        @callback
        def _midnight(now: datetime) -> None:
            self._update_listeners()

        @callback
        def _reminder(now: datetime) -> None:
            self.hass.async_create_task(self.async_send_reminder())
            self._update_listeners()

        self._unsubs.append(
            async_track_time_change(self.hass, _midnight, hour=0, minute=0, second=1)
        )
        when = self.reminder_time
        self._unsubs.append(
            async_track_time_change(
                self.hass, _reminder, hour=when.hour, minute=when.minute, second=when.second
            )
        )

    @callback
    def async_stop(self) -> None:
        """Stop the timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def async_send_reminder(self) -> None:
        """Fire the reminder event and notify, if there is a collection tomorrow."""
        collection = self.tomorrow()
        if collection is None:
            return
        title = texts(self.language)["title"]
        message = reminder_message(collection, self.language)
        self.hass.bus.async_fire(
            EVENT_REMINDER,
            {
                "street": self.street.hu,
                "street_ro": self.street.ro,
                "date": collection.day.isoformat(),
                "types": list(collection.types),
                "types_text": types_text(collection, self.language),
                "mixed": collection.has_mixed,
                "moved": collection.moved,
                "title": title,
                "message": message,
            },
        )
        if not self.notify_service:
            return
        domain, _, service = self.notify_service.partition(".")
        if not service:
            domain, service = "notify", domain
        try:
            await self.hass.services.async_call(
                domain, service, {"title": title, "message": message}, blocking=True
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning(
                "%s: could not send the reminder with %s: %s",
                DOMAIN,
                self.notify_service,
                err,
            )

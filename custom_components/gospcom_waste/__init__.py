"""Gosp-Com waste collection: when to put out which waste in Kézdivásárhely."""

from __future__ import annotations

from pathlib import Path

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store

from .bills import STORAGE_VERSION, BillsCoordinator, has_account
from .const import CONF_STREET, DOMAIN, USER_DATA_FOLDER
from .schedule import Schedule, load_schedule
from .tracker import WasteConfigEntry, WasteTracker

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]


async def async_get_schedule(hass: HomeAssistant) -> Schedule:
    """Load the shipped schedule once and share it between entries."""
    if (schedule := hass.data.get(DOMAIN)) is None:
        schedule = hass.data[DOMAIN] = await hass.async_add_executor_job(
            load_schedule, Path(hass.config.path(USER_DATA_FOLDER))
        )
    return schedule


async def async_setup_entry(hass: HomeAssistant, entry: WasteConfigEntry) -> bool:
    """Set up one street."""
    schedule = await async_get_schedule(hass)
    if entry.data[CONF_STREET] not in schedule.streets:
        raise ConfigEntryError(f"Unknown street: {entry.data[CONF_STREET]}")
    tracker = WasteTracker(hass, entry, schedule)
    entry.runtime_data = tracker
    if has_account(entry):
        bills = tracker.bills = BillsCoordinator(hass, entry)
        # A refused password starts the re-authentication. When the site is down the
        # calendar still loads, and the bill entities come once a refresh works.
        await bills.async_refresh()
        if bills.data is None:

            @callback
            def _first_data() -> None:
                if bills.data is not None:
                    hass.config_entries.async_schedule_reload(entry.entry_id)

            entry.async_on_unload(bills.async_add_listener(_first_data))
    tracker.async_start()
    entry.async_on_unload(tracker.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: WasteConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WasteConfigEntry) -> bool:
    """Unload a street."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: WasteConfigEntry) -> None:
    """Forget the remembered bill numbers."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.bills").async_remove()

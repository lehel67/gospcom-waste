"""Tests for the entities and the reminder."""

from __future__ import annotations

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.gospcom_waste.const import EVENT_REMINDER


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(
        tzinfo=dt_util.get_time_zone("Europe/Bucharest")
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    await hass.config.async_set_time_zone("Europe/Bucharest")
    hass.config.language = "hu"
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = hass.states.async_entity_ids()
    found = {key: next(i for i in ids if i.endswith(key)) for key in (
        "kovetkezo_szallitas", "kovetkezo_vegyes_szallitas", "napok_a_szallitasig",
        "mit_kell_kitenni", "holnap_szemetszallitas",
    )}
    found["szemetszallitas"] = next(i for i in ids if i.startswith("calendar."))
    return found


async def test_entities_and_reminder(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Monday: selective tomorrow, mixed the week after; reminder at 19:00."""
    freezer.move_to(_at("2026-11-09 12:00"))
    calls = async_mock_service(hass, "notify", "test_phone")
    events = async_capture_events(hass, EVENT_REMINDER)
    ids = await _setup(hass, entry)

    assert hass.states.get(ids["kovetkezo_szallitas"]).state == "2026-11-10"
    assert hass.states.get(ids["kovetkezo_vegyes_szallitas"]).state == "2026-11-17"
    assert hass.states.get(ids["napok_a_szallitasig"]).state == "1"
    assert hass.states.get(ids["napok_a_szallitasig"]).attributes["days_until_mixed"] == 8
    assert hass.states.get(ids["mit_kell_kitenni"]).state == "selective_biodegradable"
    tomorrow = hass.states.get(ids["holnap_szemetszallitas"])
    assert tomorrow.state == "on"
    assert tomorrow.attributes["types_text"] == "szelektív és lebomló (zöld)"

    freezer.move_to(_at("2026-11-09 19:00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["date"] == "2026-11-10"
    assert events[0].data["message"] == (
        "Holnap (kedd, nov. 10.) viszik: szelektív és lebomló (zöld) hulladék. "
        "Ne felejtsd el kitenni!"
    )
    assert len(calls) == 1
    assert calls[0].data["title"] == "🗑️ Holnap szemétszállítás"

    # After midnight on the collection day the countdown is 0, tomorrow is off.
    freezer.move_to(_at("2026-11-10 00:00:01"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ids["napok_a_szallitasig"]).state == "0"
    assert hass.states.get(ids["holnap_szemetszallitas"]).state == "off"

    # Monday the 16th: mixed goes too, the reminder says so.
    freezer.move_to(_at("2026-11-16 19:00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ids["mit_kell_kitenni"]).state == "mixed_selective_biodegradable"
    assert events[-1].data["mixed"] is True
    assert "vegyes háztartási hulladékot is viszik" in events[-1].data["message"]


async def test_holiday_reminder(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """No reminder on 30 November evening; it comes on the 1st for the 2nd."""
    freezer.move_to(_at("2026-11-30 12:00"))
    async_mock_service(hass, "notify", "test_phone")
    events = async_capture_events(hass, EVENT_REMINDER)
    ids = await _setup(hass, entry)
    assert hass.states.get(ids["kovetkezo_szallitas"]).state == "2026-12-02"
    assert hass.states.get(ids["holnap_szemetszallitas"]).state == "off"

    freezer.move_to(_at("2026-11-30 19:00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert events == []

    freezer.move_to(_at("2026-12-01 19:00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert events[0].data["moved"] is True
    assert "Ünnep miatt kedd, dec. 1. helyett." in events[0].data["message"]


async def test_calendar(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Collections and the drop-off day show up in the calendar."""
    freezer.move_to(_at("2026-11-07 12:00"))
    ids = await _setup(hass, entry)
    cal = ids["szemetszallitas"]
    assert cal.startswith("calendar.")
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {"start_date_time": "2026-11-09 00:00:00", "end_date_time": "2026-11-23 00:00:00"},
        target={"entity_id": cal},
        blocking=True,
        return_response=True,
    )
    events = result[cal]["events"]
    assert [(e["start"], e["summary"]) for e in events] == [
        ("2026-11-10", "🗑️ Szemétszállítás: szelektív és lebomló (zöld)"),
        ("2026-11-13T09:00:00+02:00", "♻️ Szelektív és elektronikai hulladékgyűjtő nap"),
        ("2026-11-17", "🗑️ Szemétszállítás: vegyes háztartási, szelektív és lebomló (zöld)"),
    ]

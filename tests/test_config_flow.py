"""Tests for the config and options flows."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.gospcom_waste.const import DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    """A street is set up once, a missing notifier is refused."""
    async_mock_service(hass, "notify", "mobile_app_phone")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"street": "patak_utca", "reminder_time": "20:00:00", "notify_service": "notify.nope"},
    )
    assert result["errors"] == {"notify_service": "unknown_notify"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"street": "patak_utca", "reminder_time": "20:00:00", "notify_service": "mobile_app_phone"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Patak utca"
    assert result["options"] == {"reminder_time": "20:00:00", "notify_service": "mobile_app_phone"}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"street": "patak_utca", "reminder_time": "19:00:00"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """The reminder time can be changed."""
    async_mock_service(hass, "notify", "test_phone")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"reminder_time": "18:30:00"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {"reminder_time": "18:30:00", "notify_service": ""}
    assert entry.runtime_data.reminder_time.hour == 18

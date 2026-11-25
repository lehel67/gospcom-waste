"""Tests for the optional customer account (bills)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.gospcom_waste.account import AuthError, ClientAccount, Invoice
from custom_components.gospcom_waste.const import (
    CONF_EMAIL,
    CONF_NOTIFY_SERVICE,
    CONF_PASSWORD,
    CONF_REMINDER_TIME,
    CONF_STREET,
    DOMAIN,
    EVENT_NEW_BILL,
)

FETCH = "custom_components.gospcom_waste.account.GospcomAccountClient.async_fetch"

OLD = Invoice("3837439", date(2026, 9, 30), 94.84, 94.31, "https://example/1")
NEW = Invoice("3839559", date(2026, 10, 26), 10.0, 0.0, "https://example/2")


def _accounts(*invoices: Invoice) -> dict[str, ClientAccount]:
    return {"111": ClientAccount("111", sorted(invoices, key=lambda i: i.issued, reverse=True))}


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Gábor Áron tér",
        unique_id="gábor_áron_tér",
        data={CONF_STREET: "gábor_áron_tér", CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"},
        options={CONF_REMINDER_TIME: "19:00:00", CONF_NOTIFY_SERVICE: ""},
    )


async def test_bill_entities_and_new_bill_event(hass: HomeAssistant) -> None:
    """The bill entities appear; a later invoice fires the event, the first run does not."""
    hass.config.language = "hu"
    events = async_capture_events(hass, EVENT_NEW_BILL)
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FETCH, return_value=_accounts(OLD)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    ids = hass.states.async_entity_ids()
    due = next(i for i in ids if i.endswith("fizetendo_osszeg"))
    unpaid = next(i for i in ids if i.endswith("kifizetetlen_szamla"))
    state = hass.states.get(due)
    assert state.state == "0.53"
    assert state.attributes["gospcom_client_code"] == "111"
    assert state.attributes["invoices"][0]["rest"] == 0.53
    assert hass.states.get(unpaid).state == "on"
    assert events == []

    coordinator = entry.runtime_data.bills
    with patch(FETCH, return_value=_accounts(OLD, NEW)):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get(due).state == "10.53"
    assert len(events) == 1
    assert events[0].data["invoice_number"] == "3839559"
    assert events[0].data["total_due"] == 10.53


async def test_refused_password_starts_reauth(hass: HomeAssistant) -> None:
    """A refused password keeps the calendar and asks for the password again."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FETCH, side_effect=AuthError("no")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_options_flow_checks_the_account(hass: HomeAssistant) -> None:
    """Wrong credentials are refused; right ones are stored in the entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gábor Áron tér",
        unique_id="gábor_áron_tér",
        data={CONF_STREET: "gábor_áron_tér"},
        options={CONF_REMINDER_TIME: "19:00:00", CONF_NOTIFY_SERVICE: ""},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    user_input = {CONF_REMINDER_TIME: "19:00:00", CONF_EMAIL: "a@b.c", CONF_PASSWORD: "bad"}
    with patch(FETCH, side_effect=AuthError("no")):
        result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(FETCH, return_value=_accounts(OLD)):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**user_input, CONF_PASSWORD: "good"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_EMAIL] == "a@b.c"
    assert entry.data[CONF_PASSWORD] == "good"

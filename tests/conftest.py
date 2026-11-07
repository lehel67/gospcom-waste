"""Shared fixtures."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gospcom_waste.const import (
    CONF_NOTIFY_SERVICE,
    CONF_REMINDER_TIME,
    CONF_STREET,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def entry() -> MockConfigEntry:
    """Return an entry for Gábor Áron tér (Tuesday)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Gábor Áron tér",
        unique_id="gábor_áron_tér",
        data={CONF_STREET: "gábor_áron_tér"},
        options={CONF_REMINDER_TIME: "19:00:00", CONF_NOTIFY_SERVICE: "notify.test_phone"},
    )

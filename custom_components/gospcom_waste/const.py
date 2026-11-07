"""Constants for the Gosp-Com waste collection integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "gospcom_waste"

CONF_STREET: Final = "street"
CONF_REMINDER_TIME: Final = "reminder_time"
CONF_NOTIFY_SERVICE: Final = "notify_service"

DEFAULT_REMINDER_TIME: Final = "19:00:00"

EVENT_REMINDER: Final = "gospcom_waste_reminder"

# What to put out, as the state of the enum sensor.
PUT_OUT_ALL: Final = "mixed_selective_biodegradable"
PUT_OUT_SELECTIVE: Final = "selective_biodegradable"

# Yearly data files (2027.json, ...) put here override the shipped ones.
USER_DATA_FOLDER: Final = "gospcom_waste"

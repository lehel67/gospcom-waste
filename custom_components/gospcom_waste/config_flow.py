"""Config and options flows: pick the street, the reminder time and a notifier."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from . import async_get_schedule
from .const import (
    CONF_NOTIFY_SERVICE,
    CONF_REMINDER_TIME,
    CONF_STREET,
    DEFAULT_REMINDER_TIME,
    DOMAIN,
)
from .tracker import WasteConfigEntry


def _street_selector(hass: HomeAssistant, schedule) -> SelectSelector:
    romanian_first = hass.config.language.startswith("ro")
    options = [
        SelectOptionDict(
            value=street.key,
            label=(
                f"{street.ro} ({street.hu})" if romanian_first else f"{street.hu} ({street.ro})"
            )
            if street.ro != street.hu
            else street.hu,
        )
        for street in schedule.streets.values()
    ]
    options.sort(key=lambda option: option["label"].casefold())
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


def _notify_error(hass: HomeAssistant, value: str) -> str | None:
    """Return an error key if the notify service does not exist."""
    value = value.strip()
    if not value:
        return None
    domain, _, service = value.partition(".")
    if not service:
        domain, service = "notify", domain
    return None if hass.services.has_service(domain, service) else "unknown_notify"


def _options_schema(defaults: dict[str, Any]) -> dict:
    return {
        vol.Required(
            CONF_REMINDER_TIME,
            default=defaults.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME),
        ): TimeSelector(),
        vol.Optional(
            CONF_NOTIFY_SERVICE,
            description={"suggested_value": defaults.get(CONF_NOTIFY_SERVICE, "")},
        ): TextSelector(),
    }


class WasteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the street."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: WasteConfigEntry) -> WasteOptionsFlow:
        """Return the options flow."""
        return WasteOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the street and the reminder."""
        schedule = await async_get_schedule(self.hass)
        errors: dict[str, str] = {}
        if user_input is not None:
            notify = (user_input.get(CONF_NOTIFY_SERVICE) or "").strip()
            if error := _notify_error(self.hass, notify):
                errors[CONF_NOTIFY_SERVICE] = error
            else:
                street = schedule.streets[user_input[CONF_STREET]]
                await self.async_set_unique_id(street.key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=street.hu,
                    data={CONF_STREET: street.key},
                    options={
                        CONF_REMINDER_TIME: user_input[CONF_REMINDER_TIME],
                        CONF_NOTIFY_SERVICE: notify,
                    },
                )

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_STREET, default=defaults.get(CONF_STREET, vol.UNDEFINED)): (
                    _street_selector(self.hass, schedule)
                ),
                **_options_schema(defaults),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class WasteOptionsFlow(OptionsFlow):
    """Change the reminder time and the notifier."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the current settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            notify = (user_input.get(CONF_NOTIFY_SERVICE) or "").strip()
            if error := _notify_error(self.hass, notify):
                errors[CONF_NOTIFY_SERVICE] = error
            else:
                return self.async_create_entry(
                    data={
                        CONF_REMINDER_TIME: user_input[CONF_REMINDER_TIME],
                        CONF_NOTIFY_SERVICE: notify,
                    }
                )
        defaults = user_input or dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_options_schema(defaults)), errors=errors
        )

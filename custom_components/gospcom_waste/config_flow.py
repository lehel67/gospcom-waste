"""Config and options flows: pick the street, the reminder time and a notifier."""

from __future__ import annotations

from collections.abc import Mapping
import logging
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
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from . import async_get_schedule
from .account import AccountError, AuthError
from .bills import new_client
from .const import (
    CONF_EMAIL,
    CONF_NOTIFY_SERVICE,
    CONF_PASSWORD,
    CONF_REMINDER_TIME,
    CONF_STREET,
    DEFAULT_REMINDER_TIME,
    DOMAIN,
)
from .tracker import WasteConfigEntry

_LOGGER = logging.getLogger(__name__)

EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)


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


async def _check_account(hass: HomeAssistant, email: str, password: str) -> str | None:
    """Sign in once; return an error key or None."""
    try:
        await new_client(hass, email, password).async_fetch()
    except AuthError:
        return "invalid_auth"
    except AccountError as err:
        _LOGGER.warning("Gosp-Com account check failed: %s", err)
        return "cannot_connect"
    return None


async def _account_data(
    hass: HomeAssistant, user_input: dict[str, Any], current: Mapping[str, Any], errors: dict[str, str]
) -> dict[str, str] | None:
    """The credentials to store: {} for none, None if they are wrong (errors filled in).

    An empty password keeps the stored one, so the options form need not show it."""
    email = (user_input.get(CONF_EMAIL) or "").strip()
    password = user_input.get(CONF_PASSWORD) or ""
    if not email:
        return {}
    if not password and email == current.get(CONF_EMAIL):
        password = current.get(CONF_PASSWORD, "")
    if not password:
        errors[CONF_PASSWORD] = "password_required"
        return None
    if error := await _check_account(hass, email, password):
        errors["base"] = error
        return None
    return {CONF_EMAIL: email, CONF_PASSWORD: password}


def _account_schema(defaults: Mapping[str, Any]) -> dict:
    return {
        vol.Optional(
            CONF_EMAIL, description={"suggested_value": defaults.get(CONF_EMAIL, "")}
        ): EMAIL_SELECTOR,
        vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
    }


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
            account = await _account_data(self.hass, user_input, {}, errors)
            if not errors and account is not None:
                street = schedule.streets[user_input[CONF_STREET]]
                await self.async_set_unique_id(street.key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=street.hu,
                    data={CONF_STREET: street.key, **account},
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
                **_account_schema(defaults),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The account password was refused."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the e-mail address and the password again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            email = (user_input.get(CONF_EMAIL) or "").strip()
            if not email or not user_input.get(CONF_PASSWORD):
                errors["base"] = "invalid_auth"
            elif error := await _check_account(self.hass, email, user_input[CONF_PASSWORD]):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EMAIL, default=(user_input or entry.data).get(CONF_EMAIL, "")
                ): EMAIL_SELECTOR,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
            }
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)


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
            entry = self.config_entry
            account = await _account_data(self.hass, user_input, entry.data, errors)
            if not errors and account is not None:
                data = {k: v for k, v in entry.data.items() if k not in (CONF_EMAIL, CONF_PASSWORD)}
                self.hass.config_entries.async_update_entry(entry, data={**data, **account})
                return self.async_create_entry(
                    data={
                        CONF_REMINDER_TIME: user_input[CONF_REMINDER_TIME],
                        CONF_NOTIFY_SERVICE: notify,
                    }
                )
        defaults = user_input or {
            **self.config_entry.options,
            CONF_EMAIL: self.config_entry.data.get(CONF_EMAIL, ""),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({**_options_schema(defaults), **_account_schema(defaults)}),
            errors=errors,
        )

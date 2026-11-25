"""Polls the Gosp-Com customer account and announces new bills."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .account import AccountError, AuthError, ClientAccount, GospcomAccountClient
from .const import BILLS_UPDATE_HOURS, CONF_EMAIL, CONF_PASSWORD, DOMAIN, EVENT_NEW_BILL
from .texts import day_text, texts

if TYPE_CHECKING:
    from .tracker import WasteConfigEntry

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def new_client(hass: HomeAssistant, email: str, password: str) -> GospcomAccountClient:
    """A client with its own cookie jar, so the sign-in cookie stays with this account."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    return GospcomAccountClient(session, email, password)


def money(amount: float) -> str:
    """94.84 → '94,84'."""
    return f"{amount:.2f}".replace(".", ",")


class BillsCoordinator(DataUpdateCoordinator[dict[str, ClientAccount]]):
    """The bills of every customer code on the signed-in account."""

    def __init__(self, hass: HomeAssistant, entry: WasteConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} bills",
            update_interval=timedelta(hours=BILLS_UPDATE_HOURS),
        )
        self.client = new_client(hass, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        self._store: Store[dict[str, list[str]]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.bills"
        )
        self._known: dict[str, set[str]] | None = None
        self._loaded = False

    async def _async_update_data(self) -> dict[str, ClientAccount]:
        try:
            accounts = await self.client.async_fetch()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AccountError as err:
            raise UpdateFailed(str(err)) from err
        await self._async_announce(accounts)
        return accounts

    async def _async_announce(self, accounts: dict[str, ClientAccount]) -> None:
        """Fire an event (and notify) for invoices not seen before.

        On the very first run every invoice is only remembered, so an account with years
        of history does not send a message for each of them."""
        if not self._loaded:
            stored = await self._store.async_load()
            if stored is not None:
                self._known = {code: set(numbers) for code, numbers in stored.items()}
            self._loaded = True
        first_run = self._known is None
        known = self._known or {}
        changed = False
        for code, account in accounts.items():
            seen = known.setdefault(code, set())
            fresh = [inv for inv in account.invoices if inv.number not in seen]
            if not fresh:
                continue
            changed = True
            seen.update(inv.number for inv in fresh)
            if first_run:
                continue
            for invoice in reversed(fresh):  # oldest first
                await self._async_send(code, account, invoice)
        self._known = known
        if changed or first_run:
            await self._store.async_save({c: sorted(n) for c, n in known.items()})

    async def _async_send(self, code, account, invoice) -> None:
        language = self.hass.config.language
        text = texts(language)
        message = text["bill"].format(
            amount=money(invoice.amount),
            day=day_text(invoice.issued, language),
            number=invoice.number,
            due=money(account.total_due),
        )
        self.hass.bus.async_fire(
            EVENT_NEW_BILL,
            {
                "client_code": code,
                **invoice.as_dict(),
                "total_due": account.total_due,
                "title": text["bill_title"],
                "message": message,
            },
        )
        tracker = self.config_entry.runtime_data
        if not tracker.notify_service:
            return
        domain, _, service = tracker.notify_service.partition(".")
        if not service:
            domain, service = "notify", domain
        try:
            await self.hass.services.async_call(
                domain, service, {"title": text["bill_title"], "message": message}, blocking=True
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("%s: could not send the bill message with %s: %s", DOMAIN, tracker.notify_service, err)


def has_account(entry: WasteConfigEntry) -> bool:
    """Whether the entry signs in to the customer account."""
    return bool(entry.data.get(CONF_EMAIL) and entry.data.get(CONF_PASSWORD))

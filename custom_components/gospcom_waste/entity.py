"""Shared base of the waste collection entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .tracker import WasteTracker

SOURCE_URL = (
    "https://www.gosp-com.ro/hu/hulladekelszallitas-kezdivasarhelyen-nyujtodon-"
    "szaszfaluban-es-sarfalvan"
)


class WasteEntity(Entity):
    """Base for the entities of one street; refreshed by the tracker."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_attribution = "Gosp-Com SRL"

    def __init__(self, tracker: WasteTracker, key: str) -> None:
        """Initialize the entity."""
        self.tracker = tracker
        entry = tracker.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Gosp-Com {tracker.street.hu}",
            manufacturer="Gosp-Com SRL",
            model=tracker.street.ro,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=SOURCE_URL,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the day changes."""
        self.async_on_remove(self.tracker.async_add_listener(self.async_write_ha_state))


class BillEntity(WasteEntity):
    """Base for the bill entities of one customer code; refreshed by the bills coordinator."""

    _attr_attribution = "Gosp-Com SRL – www.gosp-com.ro/account"

    def __init__(self, tracker: WasteTracker, key: str, code: str) -> None:
        """Initialize the entity."""
        super().__init__(tracker, key)
        self.code = code
        self.coordinator = tracker.bills
        self._attr_unique_id = f"{tracker.entry.entry_id}_{key}_{code}"
        several = len(self.coordinator.data or {}) > 1
        self._attr_translation_placeholders = {"code": f" ({code})" if several else ""}

    @property
    def account(self):
        """This customer code's bills, or None if the last refresh did not have it."""
        return (self.coordinator.data or {}).get(self.code)

    @property
    def available(self) -> bool:
        """Available while the last refresh worked and listed this customer code."""
        return self.coordinator.last_update_success and self.account is not None

    async def async_added_to_hass(self) -> None:
        """Follow the bill refreshes (not the day changes)."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

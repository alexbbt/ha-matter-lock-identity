"""Refresh button."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import hub_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button that re-reads lock user tables."""
    async_add_entities([RefreshUsersButton(entry.runtime_data)])


class RefreshUsersButton(ButtonEntity):
    """Re-read people from the locks."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_unique_id = "refresh"

    def __init__(self, runtime: Any) -> None:
        """Create the button."""
        self._runtime = runtime
        self._attr_device_info = hub_device_info()

    async def async_press(self) -> None:
        """Read the locks again."""
        await self._runtime.async_refresh()

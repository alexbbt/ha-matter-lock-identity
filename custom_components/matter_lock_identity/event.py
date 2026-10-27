"""Unlock events.

The event entity fires again when the same person unlocks again. A sensor
that only stored the last name would not. The entity lives on the Matter
lock device next to the Operator sensor.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import lock_entity_key


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an unlock event for each door lock."""
    entry.runtime_data.bind_events(async_add_entities)


class LockUnlockEvent(EventEntity):
    """An unlock on one Matter lock."""

    _attr_event_types = ["unlocked"]
    _attr_has_entity_name = True
    _attr_translation_key = "unlock"

    def __init__(self, node_id: int, device_info: DeviceInfo) -> None:
        """Create the event entity for one lock."""
        self.node_id = node_id
        self._attr_device_info = device_info
        self._attr_unique_id = lock_entity_key(node_id)

    def set_device_info(self, device_info: DeviceInfo) -> None:
        """Attach to the Matter device when it becomes known."""
        self._attr_device_info = device_info

    def publish(self, attributes: dict[str, Any]) -> None:
        """Record one unlock. The timestamp changes even when the person does not."""
        self._trigger_event("unlocked", attributes)
        self.async_write_ha_state()

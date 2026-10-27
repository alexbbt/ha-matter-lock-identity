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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
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

    def __init__(
        self,
        node_id: int,
        *,
        device_entry: DeviceEntry | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Create the event entity for one lock."""
        self.node_id = node_id
        self._attr_unique_id = lock_entity_key(node_id)
        self.set_device_link(device_entry, device_info)

    def set_device_link(
        self,
        device_entry: DeviceEntry | None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Attach to the Matter device, or a local fallback device."""
        self.device_entry = device_entry
        self._attr_device_info = None if device_entry is not None else device_info
        if self.hass is None or self.registry_entry is None:
            return
        device_id = device_entry.id if device_entry is not None else None
        if device_id is None and device_info is not None:
            return
        if self.registry_entry.device_id == device_id:
            return
        er.async_get(self.hass).async_update_entity(self.entity_id, device_id=device_id)

    def publish(self, attributes: dict[str, Any]) -> None:
        """Record one unlock. The timestamp changes even when the person does not."""
        self._trigger_event("unlocked", attributes)
        self.async_write_ha_state()

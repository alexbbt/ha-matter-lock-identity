"""Person entities.

One entity exists per Matter user unique id. Renaming it in Home Assistant
is how a person gets a name. The unique id stays the same, so the rename
survives restarts and lock slot changes.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import user_entity_key
from .device import hub_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a sensor for each discovered person."""
    entry.runtime_data.bind_sensors(async_add_entities)


class LockUserSensor(SensorEntity):
    """A person who can be renamed."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = False
    _attr_icon = "mdi:account-key"
    _attr_options = ["present", "absent"]
    _attr_should_poll = False
    _attr_translation_key = "user"

    def __init__(self, user_unique_id: int, name: str) -> None:
        """Create the person entity."""
        self.user_unique_id = user_unique_id
        self._attr_device_info = hub_device_info()
        self._attr_name = name
        self._attr_native_value = "absent"
        self._attr_unique_id = user_entity_key(user_unique_id)
        self._slots: list[tuple[int, int]] = []
        self._attr_extra_state_attributes = self._attributes()

    @property
    def fallback_name(self) -> str:
        """Return the name given before a person is renamed."""
        return self._attr_name or f"Lock user {self.user_unique_id}"

    def set_membership(self, slots: list[tuple[int, int]]) -> None:
        """Update the locks this person is on."""
        value = "present" if slots else "absent"
        if slots == self._slots and self._attr_native_value == value:
            return
        self._slots = list(slots)
        self._attr_native_value = value
        self._attr_extra_state_attributes = self._attributes()
        if self.hass is not None:
            self.async_write_ha_state()

    def _attributes(self) -> dict[str, object]:
        return {
            "user_unique_id": self.user_unique_id,
            "locks": [
                {"node_id": node_id, "user_index": slot}
                for node_id, slot in self._slots
            ],
        }

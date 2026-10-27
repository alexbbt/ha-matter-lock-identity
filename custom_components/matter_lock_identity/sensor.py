"""Person and operator entities.

One person sensor exists per Matter user unique id. Renaming it in Home
Assistant is how a person gets a name. The unique id stays the same, so the
rename survives restarts and lock slot changes.

Each lock also has an operator sensor. The state is the person who last
unlocked, or Unknown when the unlock had no person. That state is what History
shows as a series of names.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import UNKNOWN_OPERATOR, operator_entity_key, user_entity_key
from .device import hub_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up person sensors and lock operator sensors."""
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


class LockOperatorSensor(RestoreSensor):
    """The person who last unlocked one Matter lock."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-lock-open"
    _attr_should_poll = False
    _attr_translation_key = "operator"

    def __init__(self, node_id: int, device_info: DeviceInfo) -> None:
        """Create the operator sensor for one lock."""
        self.node_id = node_id
        self._attr_device_info = device_info
        self._attr_native_value = UNKNOWN_OPERATOR
        self._attr_unique_id = operator_entity_key(node_id)
        self._attr_extra_state_attributes = self._attributes({})

    async def async_added_to_hass(self) -> None:
        """Restore the last person after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        last_sensor = await self.async_get_last_sensor_data()
        if (
            last_state is None
            or last_sensor is None
            or last_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            return
        if last_sensor.native_value is not None:
            self._attr_native_value = last_sensor.native_value
        attrs = last_state.attributes
        self._attr_extra_state_attributes = {
            "identified": attrs.get("identified"),
            "user_unique_id": attrs.get("user_unique_id"),
            "user_index": attrs.get("user_index"),
            "method": attrs.get("method"),
            "credential_type": attrs.get("credential_type"),
            "credential_index": attrs.get("credential_index"),
        }

    def set_device_info(self, device_info: DeviceInfo) -> None:
        """Attach to the Matter device when it becomes known."""
        self._attr_device_info = device_info

    def publish(self, payload: dict[str, Any]) -> None:
        """Record who unlocked, or Unknown when there is no person."""
        if payload.get("identified") and payload.get("user_name"):
            value = str(payload["user_name"])
        else:
            value = UNKNOWN_OPERATOR
        attributes = self._attributes(payload)
        if (
            self._attr_native_value == value
            and self._attr_extra_state_attributes == attributes
        ):
            return
        self._attr_native_value = value
        self._attr_extra_state_attributes = attributes
        if self.hass is not None:
            self.async_write_ha_state()

    def _attributes(self, payload: dict[str, Any]) -> dict[str, object]:
        return {
            "identified": payload.get("identified"),
            "user_unique_id": payload.get("user_unique_id"),
            "user_index": payload.get("user_index"),
            "method": payload.get("method"),
            "credential_type": payload.get("credential_type"),
            "credential_index": payload.get("credential_index"),
        }

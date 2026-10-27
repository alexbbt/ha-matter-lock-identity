"""Device registry helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo

from .const import DOMAIN, DOOR_LOCK_CLUSTER_ID, HUB_ID, HUB_NAME, default_lock_name


def hub_device_info() -> DeviceInfo:
    """Return the device that owns the people and the refresh button."""
    return DeviceInfo(
        identifiers={(DOMAIN, HUB_ID)},
        name=HUB_NAME,
    )


def fallback_lock_device_info(node_id: int) -> DeviceInfo:
    """Return a local lock device when the Matter device is not known yet."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"node-{node_id}")},
        name=default_lock_name(node_id),
        via_device=(DOMAIN, HUB_ID),
    )


def matter_lock_device(
    hass: HomeAssistant, client: Any, node_id: int
) -> DeviceEntry | None:
    """Return the Matter integration's lock device for this node.

    Home Assistant 2026.8+ keeps one device per config entry. Reusing Matter
    identifiers in DeviceInfo would fork a second empty device, so entities
    must link with device_entry instead.
    """
    identifier = matter_lock_identifier(client, node_id)
    if identifier is None:
        return None

    registry = dr.async_get(hass)
    matches = registry.async_get_devices(identifiers={identifier})
    if not matches:
        return None

    from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN

    for device in matches:
        entry = hass.config_entries.async_get_entry(device.config_entry_id or "")
        if entry is not None and entry.domain == MATTER_DOMAIN:
            return device
    return matches[0]


def matter_lock_identifier(client: Any, node_id: int) -> tuple[str, str] | None:
    """Return the Matter device identifier for a lock node, if known."""
    from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN
    from homeassistant.components.matter.const import ID_TYPE_DEVICE_ID
    from homeassistant.components.matter.helpers import (
        get_device_id,
        get_node_device_identifier,
    )

    server_info = getattr(client, "server_info", None)
    if server_info is None:
        return None

    node = _node_for_id(client, node_id)
    if node is not None:
        for endpoint in node.endpoints.values():
            if not endpoint.has_cluster(DOOR_LOCK_CLUSTER_ID):
                continue
            device_id = get_device_id(server_info, endpoint)
            return (MATTER_DOMAIN, f"{ID_TYPE_DEVICE_ID}_{device_id}")

    return get_node_device_identifier(server_info, node_id)


def _node_for_id(client: Any, node_id: int) -> Any | None:
    get_node = getattr(client, "get_node", None)
    if callable(get_node):
        try:
            return get_node(node_id)
        except Exception:
            pass
    for node in list(client.get_nodes()):
        if getattr(node, "node_id", None) == node_id:
            return node
    return None

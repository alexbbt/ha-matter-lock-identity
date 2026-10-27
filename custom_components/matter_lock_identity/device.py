"""Device registry helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DOOR_LOCK_CLUSTER_ID, HUB_ID, HUB_NAME, default_lock_name


def hub_device_info() -> DeviceInfo:
    """Return the device that owns the people and the refresh button."""
    return DeviceInfo(
        identifiers={(DOMAIN, HUB_ID)},
        name=HUB_NAME,
    )


def lock_device_info(client: Any, node_id: int) -> DeviceInfo:
    """Return the Matter lock device, so unlock and operator share that device.

    Prefer the same identifier the Matter integration uses. Fall back to a local
    identifier only when Matter has not published the device yet.
    """
    from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN
    from homeassistant.components.matter.const import ID_TYPE_DEVICE_ID
    from homeassistant.components.matter.helpers import (
        get_device_id,
        get_node_device_identifier,
    )

    server_info = getattr(client, "server_info", None)
    if server_info is not None:
        node = _node_for_id(client, node_id)
        if node is not None:
            for endpoint in node.endpoints.values():
                if not endpoint.has_cluster(DOOR_LOCK_CLUSTER_ID):
                    continue
                device_id = get_device_id(server_info, endpoint)
                return DeviceInfo(
                    identifiers={(MATTER_DOMAIN, f"{ID_TYPE_DEVICE_ID}_{device_id}")}
                )
        return DeviceInfo(
            identifiers={get_node_device_identifier(server_info, node_id)}
        )

    return DeviceInfo(
        identifiers={(DOMAIN, f"node-{node_id}")},
        name=default_lock_name(node_id),
    )


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

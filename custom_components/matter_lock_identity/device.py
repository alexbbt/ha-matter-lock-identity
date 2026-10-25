"""Device registry helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, HUB_ID, HUB_NAME


def hub_device_info() -> DeviceInfo:
    """Return the device that owns the people and the refresh button."""
    return DeviceInfo(
        identifiers={(DOMAIN, HUB_ID)},
        name=HUB_NAME,
    )


def lock_device_info(node_id: int, name: str) -> DeviceInfo:
    """Return the device that owns one lock's unlock event."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"node-{node_id}")},
        name=name,
        via_device=(DOMAIN, HUB_ID),
    )

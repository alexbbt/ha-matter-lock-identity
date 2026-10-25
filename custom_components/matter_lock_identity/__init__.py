"""Matter Lock Identity for Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import __version__ as __version__

__all__ = ["__version__"]

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant


def _platforms() -> list[Platform]:
    from homeassistant.const import Platform

    return [Platform.BUTTON, Platform.EVENT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one entry that listens to the Matter integration."""
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN, HUB_ID, HUB_NAME
    from .runtime import IdentityRuntime

    platforms = _platforms()
    runtime = IdentityRuntime(hass)
    entry.runtime_data = runtime
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, HUB_ID)},
        name=HUB_NAME,
    )
    try:
        await runtime.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    except Exception:
        await runtime.async_stop()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop listening and unload entities."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, _platforms())

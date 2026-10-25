"""Config flow for Matter Lock Identity."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, HUB_NAME


class MatterLockIdentityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the one config entry for this integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create the entry after the Matter integration is already configured."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not self.hass.config_entries.async_entries("matter"):
            return self.async_abort(reason="matter_required")
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=HUB_NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

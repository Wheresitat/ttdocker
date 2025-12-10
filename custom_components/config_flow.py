from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_BASE_URL


class TTLockHelperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TTLock Helper."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Only one instance
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="TTLock Helper",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

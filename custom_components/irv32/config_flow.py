"""Config flow for the iRV32 integration.

v0.1.0: manual MAC entry only. Bluetooth auto-discovery is deferred until
the device's BLE advertisement local-name is observed and a stable match
filter can be added to manifest.json.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

# Pattern matches the canonical 6-octet MAC: AA:BB:CC:DD:EE:FF (with
# colons or hyphens). Looser than format_mac so we can give a useful
# error before normalising.
_MAC_PATTERN = vol.Match(
    r"^[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5}$"
)


class IRV32ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iRV32."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user-driven setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _MAC_PATTERN(user_input[CONF_ADDRESS])
            except vol.Invalid:
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                # format_mac normalises to lowercase with colons; we want
                # uppercase for HA consistency with bluetooth.* APIs.
                address = format_mac(user_input[CONF_ADDRESS]).upper()
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"iRV32 ({address})",
                    data={CONF_ADDRESS: address},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): str},
            ),
            errors=errors,
            description_placeholders={
                "example_mac": "DE:D4:34:53:37:B5",
            },
        )

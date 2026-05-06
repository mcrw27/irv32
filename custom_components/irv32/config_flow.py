"""Config flow for the iRV32 integration.

Two entry paths:

- async_step_bluetooth: Home Assistant's bluetooth integration calls this
  when an advertisement matching the manifest's `bluetooth` block is seen
  (`local_name` starts with "iRV 32"). The user gets a discovery tile in
  Settings -> Devices & Services and just clicks Confirm.

- async_step_user: manual MAC entry as a fallback for cases where auto-
  discovery is not available (e.g., the user's HA bluetooth integration
  has not seen the device yet, or the user wants to pin a specific MAC
  for some reason).
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
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


def _normalise(address: str) -> str:
    """Format a MAC address consistently across both flow paths."""
    return format_mac(address).upper()


class IRV32ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iRV32."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_address: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow triggered by Bluetooth discovery."""
        address = _normalise(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._discovered_address = address
        # title_placeholders is rendered in the discovery card title.
        self.context["title_placeholders"] = {
            "name": discovery_info.name or address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device."""
        assert self._discovery_info is not None
        assert self._discovered_address is not None

        if user_input is not None:
            return self.async_create_entry(
                title=f"iRV32 ({self._discovered_address})",
                data={CONF_ADDRESS: self._discovered_address},
            )

        # Empty form: just a Submit button. The form's title and body come
        # from translations under config.step.bluetooth_confirm.
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovered_address,
                "address": self._discovered_address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the manual setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _MAC_PATTERN(user_input[CONF_ADDRESS])
            except vol.Invalid:
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                address = _normalise(user_input[CONF_ADDRESS])
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

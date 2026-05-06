"""Button platform for iRV32.

One ButtonEntity per ATKEY. Each press dispatches through the coordinator,
which connects on demand, sends, and schedules an idle disconnect.

Availability tracks BLE advertisement presence (via the coordinator's
bluetooth subscriptions), NOT whether we currently hold a GATT connection.
The user can press a button any time the device is in range; the
coordinator handles the connect-then-send transparently.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IRV32ConfigEntry
from .const import ATKEY_BUTTONS
from .coordinator import IRV32Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IRV32ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iRV32 ATKEY buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        IRV32Button(coordinator, key, friendly_name, atkey, icon)
        for key, friendly_name, atkey, icon in ATKEY_BUTTONS
    )


class IRV32Button(ButtonEntity):
    """A single ATKEY-button entity for the iRV32 stereo."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: IRV32Coordinator,
        key: str,
        friendly_name: str,
        atkey: int,
        icon: str,
    ) -> None:
        """Initialise the button."""
        self.coordinator = coordinator
        self._atkey = atkey
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_name = friendly_name
        self._attr_icon = icon
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Reflect coordinator's advertisement-presence based availability."""
        return self.coordinator.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator state changes for availability updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.add_listener(self.async_write_ha_state)
        )

    async def async_press(self) -> None:
        """Send the ATKEY associated with this button."""
        await self.coordinator.async_send_atkey(self._atkey)

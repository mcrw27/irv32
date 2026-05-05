"""Button platform for iRV32.

One ButtonEntity per ATKEY in const.ATKEY_BUTTONS. Each press dispatches
through the coordinator, which serialises GATT access against the
heartbeat poll.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


class IRV32Button(CoordinatorEntity[IRV32Coordinator], ButtonEntity):
    """A single ATKEY-button entity for the iRV32 stereo."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IRV32Coordinator,
        key: str,
        friendly_name: str,
        atkey: int,
        icon: str,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator)
        self._atkey = atkey
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_name = friendly_name
        self._attr_icon = icon
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Send the ATKEY associated with this button."""
        await self.coordinator.async_send_atkey(self._atkey)

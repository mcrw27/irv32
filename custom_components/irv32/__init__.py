"""The iRV32 Stereo integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import IRV32Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SELECT]

# Modern HA pattern: store coordinator on entry.runtime_data instead of
# hass.data[DOMAIN]. Cleaner for unload and avoids domain-keyed dict
# bookkeeping.
type IRV32ConfigEntry = ConfigEntry[IRV32Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IRV32ConfigEntry) -> bool:
    """Set up the iRV32 integration from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    coordinator = IRV32Coordinator(hass, entry, address)

    # First refresh establishes the BLE connection. If the device isn't
    # reachable on setup we still want the entry to load (so the user
    # can fix things and the coordinator will reconnect on its own
    # schedule), so we don't propagate the UpdateFailed here.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IRV32ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unload_ok

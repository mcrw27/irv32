"""DataUpdateCoordinator for the iRV32 integration.

Owns the persistent BLE connection. The heartbeat poll on a041 doubles as
a connection-liveness probe: if the read raises, we mark the update as
failed and the coordinator's standard backoff handles reconnection.

A single asyncio.Lock serialises access to the BleakClient so that a
button-press write never races with a heartbeat read.
"""
from __future__ import annotations

import asyncio
import logging

from bleak import BleakError

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, HEARTBEAT_INTERVAL, MANUFACTURER, MODEL
from .protocol import IRV32Client

_LOGGER = logging.getLogger(__name__)


class IRV32Coordinator(DataUpdateCoordinator[bytes]):
    """Manages the iRV32V2's BLE connection and serialises GATT access."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=HEARTBEAT_INTERVAL,
        )
        self.entry = entry
        self.address = address
        self.client = IRV32Client()
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> bytes:
        """Heartbeat poll. Reconnects if needed; raises UpdateFailed on error."""
        async with self._lock:
            await self._async_ensure_connected()
            try:
                return await self.client.read_heartbeat()
            except (BleakError, asyncio.TimeoutError) as err:
                # The connection's gone or wedged. Drop the client so the
                # next update forces a fresh reconnect, and let the
                # coordinator's backoff space out retries.
                await self.client.disconnect()
                raise UpdateFailed(f"Heartbeat failed: {err}") from err

    async def async_send_atkey(self, key: int) -> None:
        """Send an ATKEY command. Raises HomeAssistantError on failure."""
        async with self._lock:
            try:
                await self._async_ensure_connected()
                await self.client.send_atkey(key)
            except (BleakError, asyncio.TimeoutError) as err:
                # Drop the connection so the next heartbeat reconnects.
                # Don't try to recover inline: a button press happens in a
                # service call context and shouldn't block waiting for a
                # multi-second reconnect.
                await self.client.disconnect()
                raise HomeAssistantError(
                    f"Failed to send ATKEY 0x{key:02X}: {err}"
                ) from err

    async def async_shutdown(self) -> None:
        """Tear down the connection. Called on config entry unload."""
        async with self._lock:
            await self.client.disconnect()
        await super().async_shutdown()

    async def _async_ensure_connected(self) -> None:
        """Connect if not already connected. Caller must hold self._lock."""
        if self.client.is_connected:
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"iRV32 {self.address} is not in range of any "
                "connectable Bluetooth scanner"
            )

        try:
            await self.client.connect(ble_device)
        except (BleakError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Connect to {self.address} failed: {err}") from err

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo shared by all entities tied to this coordinator."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"iRV32 ({self.address})",
        )

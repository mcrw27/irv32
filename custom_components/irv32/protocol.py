"""Low-level BLE protocol client for the iRV32V2 stereo.

Wraps a `BleakClientWithServiceCache` and exposes only the operations the
rest of the integration needs: connect, disconnect, send_atkey, and
read_heartbeat. No knowledge of Home Assistant lives here so this module
can be unit-tested with a mock BleakClient.
"""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .const import (
    ATKEY_PREFIX,
    ATKEY_SUFFIX,
    HEARTBEAT_CHAR_UUID,
    WRITE_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)


class IRV32Client:
    """BLE client for the iRV32V2 stereo."""

    def __init__(self) -> None:
        self._client: BleakClientWithServiceCache | None = None

    @property
    def is_connected(self) -> bool:
        """Whether the underlying BleakClient currently reports connected."""
        return self._client is not None and self._client.is_connected

    async def connect(self, ble_device: BLEDevice) -> None:
        """Establish a connection. Uses bleak_retry_connector for robustness.

        Raises BleakError or asyncio.TimeoutError on failure (caller decides
        how to surface those).
        """
        # Drop any stale client before re-establishing. establish_connection
        # is happy to be called again but we want the disconnect callback
        # cleared first.
        if self._client is not None:
            await self.disconnect()

        name = ble_device.name or ble_device.address
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name,
            disconnected_callback=self._on_disconnected,
            max_attempts=3,
        )
        _LOGGER.debug("Connected to %s", name)

    async def disconnect(self) -> None:
        """Disconnect and clear the client. Safe to call when not connected."""
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            await client.disconnect()
        except BleakError as err:
            # Already gone, or the underlying transport is in a weird state.
            # Either way the client is no longer ours; log and move on.
            _LOGGER.debug("Disconnect raised, ignoring: %s", err)

    async def send_atkey(self, key: int) -> None:
        """Send a single ATKEY command.

        Wire format: ASCII "ATKEY" + payload byte + CR LF, written to a040
        with response. The 'with response' is important: write-without-
        response on this device drops the bottom-of-queue commands during
        bursts (observed in the original ESPHome decode).
        """
        if self._client is None:
            raise BleakError("Not connected")
        if not 0 <= key <= 0xFF:
            raise ValueError(f"ATKEY byte out of range: 0x{key:02X}")
        payload = ATKEY_PREFIX + bytes([key]) + ATKEY_SUFFIX
        await self._client.write_gatt_char(WRITE_CHAR_UUID, payload, response=True)
        _LOGGER.debug("Sent ATKEY 0x%02X", key)

    async def read_heartbeat(self) -> bytes:
        """Read the a041 heartbeat characteristic.

        The device returns a fixed pattern (55 AA 01 FF FF FF 02). The bytes
        themselves are not interesting; the read either succeeds (link is
        alive) or raises (link is dead).
        """
        if self._client is None:
            raise BleakError("Not connected")
        return bytes(await self._client.read_gatt_char(HEARTBEAT_CHAR_UUID))

    @staticmethod
    def _on_disconnected(client: Any) -> None:
        """Called by bleak when the underlying connection drops.

        Logged at debug only. Recovery is driven by the coordinator's
        next heartbeat poll, which catches the dropped state and
        triggers a reconnect.
        """
        _LOGGER.debug("BLE link dropped (callback)")

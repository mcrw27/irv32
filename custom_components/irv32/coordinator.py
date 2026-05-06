"""Connection coordinator for the iRV32 integration.

Architecture (v0.2.0+):

The iRV32V2 stereo's BLE firmware aggressively drops idle connections.
Any client that maintains a persistent connection (or polls heartbeats
to verify one) will trigger continuous reconnects, and that connect-
storm eventually wedges the BT controller on whatever proxy is talking
to it - clearing only on a hardware power cycle.

This coordinator therefore:

1. Does NOT keep a persistent connection.
2. Does NOT poll the device.
3. Connects on demand for each button press.
4. After each press, holds the connection open for IDLE_DISCONNECT_SECONDS
   so rapid MODE cycling (source switching) stays instant. After that
   window the connection is cleanly torn down. First press after idle
   pays a ~1-3s reconnect cost.
5. Drops by the peer mid-idle are silent: the connection state is
   re-evaluated on the next button press.
6. Entity availability tracks BLE advertisement presence (via HA's
   bluetooth integration), NOT GATT connection state. The user can
   "see" the device when it's broadcasting in range; pressing a button
   then either succeeds quickly or surfaces a clear error.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from bleak import BleakError

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, IDLE_DISCONNECT_SECONDS, MANUFACTURER, MODEL
from .protocol import IRV32Client

_LOGGER = logging.getLogger(__name__)


class IRV32Coordinator:
    """Owns the iRV32 BLE client; mediates GATT writes and tracks reachability."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
    ) -> None:
        """Initialise the coordinator."""
        self.hass = hass
        self.entry = entry
        self.address = address
        self.client = IRV32Client()

        # Lock serialises writes and the idle-disconnect against each other.
        self._lock = asyncio.Lock()
        # Handle for the in-flight idle-disconnect timer, if any.
        self._idle_handle: asyncio.TimerHandle | None = None
        # Advertisement-presence based availability. Updated by callbacks
        # registered against the bluetooth integration.
        self._available: bool = False
        # Entity update callbacks (one per entity), called after any state
        # change that should trigger an HA UI refresh.
        self._listeners: set[Callable[[], None]] = set()
        # Cancel callables for the bluetooth subscriptions; called on shutdown.
        self._unsubs: list[Callable[[], None]] = []

    async def async_setup(self) -> None:
        """Wire up bluetooth callbacks. Call once during config-entry setup."""
        self._available = bluetooth.async_address_present(
            self.hass, self.address, connectable=True
        )

        self._unsubs.append(
            bluetooth.async_register_callback(
                self.hass,
                self._async_handle_advertisement,
                {"address": self.address, "connectable": True},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )
        self._unsubs.append(
            bluetooth.async_track_unavailable(
                self.hass,
                self._async_handle_unavailable,
                self.address,
                connectable=True,
            )
        )

    async def async_shutdown(self) -> None:
        """Tear down. Called on config-entry unload."""
        self._cancel_idle_disconnect()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        async with self._lock:
            await self.client.disconnect()

    # ------------------------------------------------------------------
    # Availability surface for entities
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether the iRV32V2 is currently reachable via any scanner."""
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo shared by all entities tied to this coordinator."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"iRV32 ({self.address})",
        )

    def add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register an entity for state-change notifications. Returns unsub."""
        self._listeners.add(update_callback)

        def _remove() -> None:
            self._listeners.discard(update_callback)

        return _remove

    @callback
    def _notify_listeners(self) -> None:
        for cb in self._listeners:
            cb()

    # ------------------------------------------------------------------
    # Bluetooth event handlers (sync callbacks invoked by the BT stack)
    # ------------------------------------------------------------------

    @callback
    def _async_handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Fired on every iRV32 advertisement. Marks the device available."""
        if not self._available:
            self._available = True
            _LOGGER.debug("iRV32 %s now available", self.address)
            self._notify_listeners()

    @callback
    def _async_handle_unavailable(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Fired when the bluetooth integration declares the device unseen."""
        if self._available:
            self._available = False
            _LOGGER.debug("iRV32 %s now unavailable", self.address)
            self._notify_listeners()

    # ------------------------------------------------------------------
    # GATT write API exposed to entities
    # ------------------------------------------------------------------

    async def async_send_atkey(self, key: int) -> None:
        """Send a single ATKEY. Connects on demand; raises on failure."""
        async with self._lock:
            self._cancel_idle_disconnect()
            try:
                await self._async_ensure_connected_locked()
                await self.client.send_atkey(key)
            except (BleakError, asyncio.TimeoutError) as err:
                # Drop the connection so the next press starts fresh,
                # rather than retrying against a half-broken link and
                # poking the storm-prone reconnect path.
                await self.client.disconnect()
                raise HomeAssistantError(
                    f"Failed to send ATKEY 0x{key:02X}: {err}"
                ) from err
            self._schedule_idle_disconnect_locked()

    async def _async_ensure_connected_locked(self) -> None:
        """Connect if needed. Caller must hold self._lock."""
        if self.client.is_connected:
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise HomeAssistantError(
                f"iRV32 {self.address} is not in range of any "
                "connectable Bluetooth scanner"
            )

        await self.client.connect(ble_device)

    # ------------------------------------------------------------------
    # Idle-disconnect timer
    # ------------------------------------------------------------------

    def _schedule_idle_disconnect_locked(self) -> None:
        """Arm the idle-disconnect timer. Caller must hold self._lock."""
        # _cancel_idle_disconnect() at the start of async_send_atkey already
        # cleared any prior handle; this just schedules a fresh one.
        self._idle_handle = self.hass.loop.call_later(
            IDLE_DISCONNECT_SECONDS, self._on_idle_timeout
        )

    def _cancel_idle_disconnect(self) -> None:
        """Cancel any pending idle-disconnect timer."""
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None

    @callback
    def _on_idle_timeout(self) -> None:
        """Idle window elapsed. Schedule a clean disconnect on the loop."""
        self._idle_handle = None
        self.hass.async_create_task(self._async_idle_disconnect())

    async def _async_idle_disconnect(self) -> None:
        """Acquire lock and disconnect, unless newer activity raced ahead."""
        async with self._lock:
            # If a button press fired between _on_idle_timeout setting
            # _idle_handle = None and us acquiring the lock, that press
            # will have re-armed the timer (see _schedule_idle_disconnect_
            # locked at the end of async_send_atkey). In that case
            # _idle_handle is non-None and we should NOT disconnect.
            if self._idle_handle is not None:
                _LOGGER.debug("Idle disconnect superseded by newer activity")
                return
            if self.client.is_connected:
                _LOGGER.debug(
                    "iRV32 %s idle for %ds, disconnecting",
                    self.address,
                    IDLE_DISCONNECT_SECONDS,
                )
                await self.client.disconnect()

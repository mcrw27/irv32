"""Select platform for iRV32 source switching.

The iRV32V2 exposes no telemetry of its currently selected source. This
entity therefore implements an idempotent BT-anchor + N x MODE cycle:
every selection first re-anchors to BT (ATKEY 0x17), then walks MODE
(ATKEY 0x15) the right number of times to land on the target source.
This is robust against front-panel/IR-remote drift between selections.

Last selected option is restored across Home Assistant restarts via
RestoreEntity. While a cycle is in flight current_option is cleared so
a partial run never lies about the device's true state.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IRV32ConfigEntry
from .const import (
    ATKEY_MODE,
    ATKEY_SOURCE_BT,
    SOURCE_CYCLE_DELAY_MS,
    SOURCES,
)
from .coordinator import IRV32Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IRV32ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iRV32 source select entity from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([IRV32SourceSelect(coordinator)])


class IRV32SourceSelect(
    CoordinatorEntity[IRV32Coordinator], SelectEntity, RestoreEntity
):
    """Source selector for the iRV32V2 stereo."""

    _attr_has_entity_name = True
    _attr_name = "Source"
    _attr_icon = "mdi:audio-input-rca"
    _attr_options = list(SOURCES)

    def __init__(self, coordinator: IRV32Coordinator) -> None:
        """Initialise the select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_source"
        self._attr_device_info = coordinator.device_info
        self._attr_current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last-known selected source from previous HA run."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in SOURCES:
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        """Switch source by walking the BT-anchor + N x MODE cycle."""
        if option not in SOURCES:
            raise ValueError(f"Unknown source: {option}")

        target_index = SOURCES.index(option)
        delay = SOURCE_CYCLE_DELAY_MS / 1000.0

        # Mark indeterminate while the multi-step cycle is in flight, so
        # a partial run is reflected as 'unknown' rather than the previous
        # value.
        self._attr_current_option = None
        self.async_write_ha_state()

        # Step 1: anchor to BT (always, regardless of target).
        await self.coordinator.async_send_atkey(ATKEY_SOURCE_BT)

        # Step 2: walk MODE the right number of times. target_index = 0
        # (BT itself) skips this loop entirely.
        for _ in range(target_index):
            await asyncio.sleep(delay)
            await self.coordinator.async_send_atkey(ATKEY_MODE)

        self._attr_current_option = option
        self.async_write_ha_state()

"""Constants for the iRV32 integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "irv32"
MANUFACTURER: Final = "iRV"
MODEL: Final = "iRV32V2"

# GATT layout. The iRV32V2 hides its proprietary control protocol behind
# what advertises as a standard Battery Service.
SERVICE_UUID: Final = "0000180f-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID: Final = "0000a040-0000-1000-8000-00805f9b34fb"
HEARTBEAT_CHAR_UUID: Final = "0000a041-0000-1000-8000-00805f9b34fb"

# Heartbeat poll cadence. The a041 read is purely a connection-liveness
# probe; the device returns the same fixed bytes every time.
HEARTBEAT_INTERVAL: Final = timedelta(seconds=30)

# Wire format prefix and suffix for ATKEY commands.
ATKEY_PREFIX: Final = b"ATKEY"
ATKEY_SUFFIX: Final = b"\r\n"

# Single ATKEY bytes that the source-select logic reaches for directly.
ATKEY_MODE: Final = 0x15
ATKEY_SOURCE_BT: Final = 0x17

# ATKEY commands exposed as button entities. Each tuple:
#   (key, friendly_name, atkey_byte, mdi_icon)
# `key` is used for entity unique_id and translation lookup; it is stable
# across renames of friendly_name.
#
# `next_0x11` is preserved as an undocumented command from the original
# protocol decode. Front-panel function unknown.
ATKEY_BUTTONS: Final = [
    ("zone_1",       "Zone 1",       0x01, "mdi:numeric-1-circle"),
    ("zone_2",       "Zone 2",       0x02, "mdi:numeric-2-circle"),
    ("zone_3",       "Zone 3",       0x03, "mdi:numeric-3-circle"),
    ("zone_z3",      "Zone Z3",      0x23, "mdi:numeric-3-box"),
    ("preset_1",     "Preset 1",     0x05, "mdi:numeric-1-box-outline"),
    ("preset_2",     "Preset 2",     0x06, "mdi:numeric-2-box-outline"),
    ("preset_3",     "Preset 3",     0x07, "mdi:numeric-3-box-outline"),
    ("preset_4",     "Preset 4",     0x08, "mdi:numeric-4-box-outline"),
    ("preset_5",     "Preset 5",     0x09, "mdi:numeric-5-box-outline"),
    ("preset_6",     "Preset 6",     0x0A, "mdi:numeric-6-box-outline"),
    ("fast_forward", "Fast Forward", 0x0F, "mdi:fast-forward"),
    ("skip_back",    "Skip Back",    0x10, "mdi:skip-backward"),
    ("next_0x11",    "Next 0x11",    0x11, "mdi:help-box"),
    ("skip_prev",    "Skip Prev",    0x12, "mdi:skip-previous"),
    ("play_pause",   "Play/Pause",   0x13, "mdi:play-pause"),
    ("stop",         "Stop",         0x14, "mdi:stop"),
    ("mode",         "Mode",         0x15, "mdi:swap-horizontal"),
    ("source_bt",    "Source BT",    0x17, "mdi:bluetooth"),
    ("mute",         "Mute",         0x18, "mdi:volume-mute"),
    ("volume_up",    "Volume Up",    0x1C, "mdi:volume-plus"),
    ("source_am_fm", "Source AM/FM", 0x1D, "mdi:radio"),
    ("volume_down",  "Volume Down",  0x20, "mdi:volume-minus"),
    ("source_dvd",   "Source DVD",   0x21, "mdi:disc"),
]

# Source select cycle. Index = number of MODE presses required AFTER the
# BT anchor to reach that source. Must match the iRV32V2's hardware MODE-
# button cycle order; the device gives no telemetry of current source so
# this list is the source of truth.
SOURCES: Final = [
    "BT",
    "TV Audio",
    "FR Audio",
    "F-HDMI",
    "TV Audio 2",
    "FM",
]

# Inter-press delay during BT-anchor + N x MODE source-select cycle.
# 300 ms matches what the previous ESPHome script used and what the
# device firmware appears to require.
SOURCE_CYCLE_DELAY_MS: Final = 300

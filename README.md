# iRV32 Stereo

Home Assistant integration for iRV32V2 RV stereos over Bluetooth Low Energy.

The iRV32V2 is a head-unit RV stereo that exposes a proprietary BLE GATT
control protocol behind a fake `Battery Service` (UUID `0x180F`). This
integration sends ATKEY commands over GATT to control source, zone,
playback, presets, and volume.

The integration is designed to run via the Home Assistant Bluetooth
integration, including remote ESP32 Bluetooth Proxies. No firmware-side
control logic on the proxy is required — the proxy is used as a pure
proxy.

## Features

- 22 button entities, one per ATKEY command (zones, presets, volume,
  transport, sources, mute, mode)
- Source selector with idempotent BT-anchor + N x MODE cycling
  (the device exposes no source-state feedback, so every selection
  re-anchors to BT and walks forward)
- Persistent BLE connection with retry-on-drop via `bleak_retry_connector`
- Heartbeat poll on characteristic `a041` for connection liveness

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations**, click the three-dots menu, then
   **Custom repositories**.
2. Add `https://github.com/mcrw27/irv32` with category **Integration**.
3. Install the **iRV32 Stereo** integration.
4. Restart Home Assistant.
5. Settings -> Devices & Services -> Add Integration -> iRV32 Stereo.
6. Enter the BLE MAC address of your stereo.

### Manual

1. Copy `custom_components/irv32` into your Home Assistant `config/custom_components/`.
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> iRV32 Stereo.

## Configuration

The integration is configured via the UI. Required input:

- **MAC address** of the iRV32V2 stereo (e.g. `DE:D4:34:53:37:B5`)

The stereo must be in BLE range of either the Home Assistant host's local
Bluetooth adapter or an ESP32 Bluetooth Proxy.

## Source cycling

The iRV32V2 has six sources. Pressing MODE on the front panel walks through
them in this fixed order:

```
0. BT
1. TV Audio
2. FR Audio
3. F-HDMI
4. TV Audio 2
5. FM
```

The stereo provides no telemetry of which source is currently selected.
The `select.irv32_source` entity therefore always anchors to BT (ATKEY
`0x17`) on every selection, then sends MODE (ATKEY `0x15`) the right
number of times to land on the requested source. This is idempotent:
selecting any source from any prior state always lands at the same place.

## ATKEY reference

The wire format for every command is:

```
ASCII "ATKEY" + payload byte + 0x0D 0x0A   (CR LF)
```

Written to characteristic `0000A040-0000-1000-8000-00805F9B34FB` of
service `0000180F-0000-1000-8000-00805F9B34FB`.

| Payload | Function     | Payload | Function       |
|--------:|--------------|--------:|----------------|
| `0x01`  | Zone 1       | `0x14`  | Stop           |
| `0x02`  | Zone 2       | `0x15`  | Mode           |
| `0x03`  | Zone 3       | `0x17`  | Source BT      |
| `0x05`  | Preset 1     | `0x18`  | Mute           |
| `0x06`  | Preset 2     | `0x1C`  | Volume Up      |
| `0x07`  | Preset 3     | `0x1D`  | Source AM/FM   |
| `0x08`  | Preset 4     | `0x20`  | Volume Down    |
| `0x09`  | Preset 5     | `0x21`  | Source DVD     |
| `0x0A`  | Preset 6     | `0x23`  | Zone Z3        |
| `0x0F`  | Fast Forward |         |                |
| `0x10`  | Skip Back    |         |                |
| `0x11`  | Next (0x11)  |         |                |
| `0x12`  | Skip Prev    |         |                |
| `0x13`  | Play/Pause   |         |                |

`0x11` ("Next 0x11") is preserved as an undocumented command. Function
unknown.

## Development status

- v0.1.0: manual MAC entry only. Bluetooth auto-discovery deferred until
  the device's BLE advertisement local-name is confirmed.
- The integration domain is not yet listed in `home-assistant/brands`.
  This is required before HACS will show the integration with proper
  branding and is filed as a follow-up.

## Why this exists

A previous implementation ran the BLE control client on an ESPHome
ESP32 Bluetooth Proxy, with ~30 template buttons writing ATKEYs locally.
That arrangement caused a rapid disconnect/reconnect storm against the
iRV32V2 and eventually wedged the ESP32 BT controller silicon for that
specific peer until a hardware power cycle. Moving control to a Home
Assistant integration that uses the proxy via `bleak_retry_connector`
gets connection management onto a stack that handles supervision and
retries correctly.

## License

MIT. See [LICENSE](LICENSE).

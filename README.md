# BLE LED Controller (TG201A / MeRGBw)

Python CLI and library to control a BLE RGB LED strip based on the
**TG201A** controller (MeRGBw app), using the [bleak](https://github.com/hbldh/bleak)
BLE library.

## Files

- `ble_led.py` - main script: BLE protocol, controller class, CLI
- `scenes.py` - catalog of 109 light scenes and 6 music (mic) scenes

## Requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install bleak
```


Tested on Linux (BlueZ via D-Bus). The `is_bluetooth_enabled()` check
uses `bluetoothctl show` and falls back to "enabled" if `bluetoothctl`
is not available, so the actual connection attempt remains the final
source of truth.

## Device info

| Campo                 | Valore                       |
|-----------------------|------------------------------|
| BLE name              | LED Lights                   |
| MAC                   | `41:42:81:AB:60:BB`          |
| Model                 | TG201A                       |
| Service BLE           | `0000fff0`                   |
| WRITE characteristic  | `0000fff3` (handle `0x0009`) |
| NOTIFY characteristic | `0000fff4` (handle `0x000b`) |

MAC address: `41:42:81:AB:60:BB` (edit `MAC_ADDRESS` in `ble_led.py` if needed)

## Usage

```bash
python ble_led.py <command> [args]
```

### Basic commands

| Command 							| Description 											|
|-----------------------|-----------------------------------|
| `scan` 								| Search for nearby BLE devices 		|
| `demo` 								| Run a full demo sequence 					|
| `on` / `off` 					| Power on / off 										|
| `color <R> <G> <B>` 	| Set RGB color, 0-255 per channel 	|
| `brightness <1-100>` 	| Set brightness in % 							|
| `sens <0-100>` 				| Set microphone sensitivity in % 	|
| `query` 							| Read and print the current status |

Quick colors: `red`, `green`, `blue`, `white`, `yellow`, `cyan`, `magenta`, `warm`

### Example:

```bash
source .venv/bin/activate

python ble_led.py on
python ble_led.py off
python ble_led.py color 255 0 0
python ble_led.py green
python ble_led.py red
python ble_led.py brightness 70
python ble_led.py scene "flowing water"
python ble_led.py scene "chase" 80
python ble_led.py scene id 23
python ble_led.py scenes
python ble_led.py scenes corsa
```

### Light scenes

```bash
python ble_led.py scene <name> [speed]
python ble_led.py scene id <N> [speed]
python ble_led.py scenes [filter]
```

- `<name>` is case-insensitive and can be multi-word (quote it if it
  contains spaces), e.g. `scene "Green-blue flowing water"`
- `[speed]` is optional, range 0-100 (if omitted, the scene's default
  speed is used)
- `scenes` with no argument lists all 109 scenes; with a text/number
  argument it filters by name substring or exact scene ID

109 scenes are available, grouped by category: Cycle, gradients,
accumulation, chase, drift, spread, melody close, opening/closing,
light-to-dark transitions, flowing water, flow, run, and run-with-dot
variants. 
See `scenes.py` for the full list with scene IDs.

Gruppi principali:

| Category                | ID range					      |
|-------------------------|-------------------------|
| Cycle / multi-color     | 1-10                    |
| Alternating gradient    | 11-15                   |
| Accumulation            | 16-22                   |
| Chase				            | 23-25                   |
| Drift / Spread		      | 26-31                   |
| Melody close     				| 32-34                   |
| Opening and closing     | 35-44                   |
| transition              | 45-54                   |
| Flowing water           | 55-63                   |
| Flow	                  | 64-75                   |
| Run	                    | 84-95                   |
| Run with dot	          | 96-117                  |

### Music scenes (microphone mode)

```bash
python ble_led.py music [name]
python ble_led.py music id <N>
python ble_led.py music
```

6 scenes available: `Spectrum1`, `Spectrum2`, `Spectrum3`, `Flowing`,
`Rolling`, `Rhythm` (IDs 1-6). These do not use a speed parameter.

### Schedule

```bash
python ble_led.py schedule on  <HH:MM> <days>
python ble_led.py schedule on  enable|disable
python ble_led.py schedule off <HH:MM> <days>
python ble_led.py schedule off enable|disable
python ble_led.py schedule both <ON_HH:MM> <OFF_HH:MM> <days>
python ble_led.py schedule clear
```

`<days>` is a comma-separated list of `mon tue wed thu fri sat sun`,
or `all`. 
Examples: `all`, `mon,wed,fri`, `sat,sun`.

## Using as a library

```python
import asyncio
from ble_led import LEDController, MAC_ADDRESS

async def main():
    led = LEDController(MAC_ADDRESS)
    await led.connect()
    await led.power_on()
    await led.set_color(255, 0, 0)
    await led.set_scene_by_name("Aurora", speed=80)
    await led.disconnect()

asyncio.run(main())
```

## Protocol notes

The full BLE packet protocol (CMD bytes, payload structure, checksum,
NOTIFY format) is documented in the module docstring at the top of
`ble_led.py`. It was reverse-engineered from BLE HCI captures of the
official MeRGBw app.

BLE LED device controller
MAC: 41:42:81:AB:60:BB
WRITE  -> FFF3 (handle 0x0009)
NOTIFY <- FFF4 (handle 0x000b)

### *FFF3 packet protocol (WRITE)*:
<HEADER>  <CMD>  <SEQ>  <LEN_TOT>  [payload...]  <CHK>

  0x55  HEADER
  0xFF  SEQ

Main CMD commands:
  0x00  QUERY STATUS  (empty payload)
  0x01  POWER ON/OFF  (payload: 0x01=on  0x00=off)
  0x03  COLOR         (payload: HUE_HI HUE_LO BRI_HI BRI_LO)
                       HUE  0-360 uint16 big-endian (0=red, 120=green, 240=blue)
                       BRI  0-1000 uint16 big-endian
  0x05  BRIGHTNESS    (payload: BRI_HI BRI_LO)
                       BRI  0-1000 uint16 big-endian
  0x08  MIC SENSITIVITY (payload: 0x3c-0x64 (60-100) - (0%-100%)
  0x0A  SCHEDULE      (8-byte payload, see cmd_set_schedule)
  0x0E  HANDSHAKE     (fixed token, sent once at startup)

  <CHK> checksum:     sum (all packet bytes) = 0xFF

### *FFF4 packet protocol (NOTIFY, 19 bytes)*:
  [0]  0x56        fixed header
  [1]  0x00        cmd echo
  [2]  0xFF        fixed
  [3]  0x14        length
  [4]  pwr         0x00=off  0x01=on
  [5]  lum_hi      brightness high byte
  [6]  lum_lo      brightness low byte  (range 0x0032=50 min ... 0x03E8=1000 max)
  [7]  on_sched    0x01=power-on schedule active  0x00=disabled
  [8]  on_hh       scheduled power-on hour (dec)
  [9]  on_mm       scheduled power-on minute (dec)
  [10] on_days     power-on days bitmask (bit6=sun ... bit0=mon)  0x7F=all
  [11] off_sched   0x01=power-off schedule active  0x00=disabled
  [12] off_hh      scheduled power-off hour (dec)
  [13] off_mm      scheduled power-off minute (dec)
  [14] off_days    power-off days bitmask (bit6=sun ... bit0=mon)  0x7F=all
  [15] 0x00        fixed
  [16] n_led       number of LEDs in the strip (dec)
  [17] mic_sens    mic sensitivity: 0x3C=0% 0x4C=40% 0x5C=80% 0x64=100%
  [18] chk         checksum


## Reference

- [bleak](https://github.com/hbldh/bleak) — BLE Python cross-platform library
- [VerTox/rgw_hex_bt](https://github.com/VerTox/rgw_hex_bt) 
- App: **MeRGBw** by Kangtaixin Neon LED (Android)
- [Smart LED Neon Light](https://www.amazon.it/MeRGBW-Home-Striscia-Controllo-Intelligente-Cambiamento/dp/B0D91TQ3D7) - Amazon link


<img src="img/led_0.jpg" width="300"/>
<img src="img/led_1.jpg" width="300"/>

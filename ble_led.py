#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
BLE LED device controller
MAC: 41:42:81:AB:60:BB
WRITE  -> FFF3 (handle 0x0009)
NOTIFY <- FFF4 (handle 0x000b)


*FFF3 packet protocol (WRITE)*:
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
  0x0C  SET TIME      (payload: YEAR_HI YEAR_LO MONTH DAY HOUR MIN SEC WEEKDAY)
                       taken automatically from the PC clock, no arguments needed
  0x0E  HANDSHAKE     (fixed token, sent once at startup)

  <CHK> checksum:     sum (all packet bytes) = 0xFF

*FFF4 packet protocol (NOTIFY, 19 bytes)*:
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
"""

import asyncio
import datetime
import logging
from dataclasses import dataclass
from typing import Optional
from bleak import BleakClient, BleakScanner

# --- Configuration ----------------------------------------------------------------

MAC_ADDRESS = "41:42:81:AB:60:BB"
UUID_WRITE  = "0000fff3-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "0000fff4-0000-1000-8000-00805f9b34fb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("LED-BLE")


# --- Packet construction --------------------------------------------------------------

HEADER = 0x55
SEQ = 0xFF

CMD_QUERY = 0x00
CMD_POWER = 0x01
CMD_SET_COLOR = 0x03
CMD_SET_BRIGHTNESS = 0x05
CMD_SCHEDULE=0x0A
CMD_SET_TIME = 0x0C
CMD_BIND = 0x0E
CMD_SET_SENS_MIC = 0x08
CMD_SET_SCENE = 0x06
CMD_SET_SCENE_SPEED = 0x0F
CMD_SET_SCENE_MIC = 0x07


def checksum(frame: list[int]) -> int:
    """sum(all packet bytes including chk) == 0xFF"""
    s = sum(frame) & 0xFF
    return (0xFF - s) & 0xFF


def remap(value: int, min_input: int, max_input: int, min_output: int, max_output: int) -> int:
    # Compute the value's percentage within the input range
    percentage = (value - min_input) / (max_input - min_input)
    # Compute the corresponding value within the output range
    return int(min_output + (percentage * (max_output - min_output)))


# --- FFF3 WRITE commands ----------------------------------------------------------------

def cmd_handshake() -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 0E FF 0B PAYLOAD CHK]
    """Init token, sent once upon connection."""
    payload = bytes([0xA0, 0x2A, 0x48, 0x63, 0x53, 0x97])
    frame = [HEADER, CMD_BIND, SEQ, 0x0B, *payload]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_query_status() -> bytes:
    # [0x HEAD CMD SEQ LEN CHK]
    # [0x 55 00 FF 05 CHK]
    """Request full status; the response arrives on NOTIFY FFF4."""
    frame = [HEADER, CMD_QUERY, SEQ, 0x05]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_power(on: bool) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 01 FF 06 bool CHK]
    """Turn the LED strip on / off."""
    frame = [HEADER, CMD_POWER, SEQ, 0x06, 0x01 if on else 0x00]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_set_brightness(value: int) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 05 FF 07 HI LO CHK]
    """
    Set brightness.
    value: integer between 0 and 100%
    real value scale: range 50 (minimum) ... 1000 (maximum).
    payload = 2 bytes, uint16 big-endian.
    [hi, lo] (2 bytes big-endian)
    """
    value  = max(50, min(1000, value))
    hi     = (value >> 8) & 0xFF
    lo     = value & 0xFF
    frame = [HEADER, CMD_SET_BRIGHTNESS, SEQ, 0x07, hi, lo]
    frame.append(checksum(frame))
    return bytes(frame)

def cmd_set_sens_mic(value: int) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 08 FF 06 SENS CHK]
    """
    PAYLOAD_min = 0x3c	0% 	60  dec
    PAYLOAD_max = 0x64	100%	100 dec
    """
    value  = max(60, min(100,value))
    sens = value & 0xFF
    frame = [HEADER, CMD_SET_SENS_MIC, SEQ, 0x06, sens]
    frame.append(checksum(frame))
    return bytes(frame)

def cmd_set_color(r: int, g: int, b: int, brightness: int = 1000) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 03 FF 09 HUE_HI HUE_LO BRI_HI BRI_LO CHK]
    """
    Set RGB color (0-255 per channel).

    The device accepts color as HUE (0-360 deg) + brightness (0-1000),
    both uint16 big-endian on CMD 0x03.

    Real packet structure (from btsnoop):
      55 03 FF 09  [HUE_HI] [HUE_LO]  [BRI_HI] [BRI_LO]  [CHK]

    The RGB->HUE conversion uses colorsys (HSV): the HSV V channel is
    multiplied by 1000 and used as the device brightness,
    unless an explicit value is passed.

    Note: low-saturation colors (white, gray) are not represented
    well via HUE alone; use set_brightness() to adjust intensity.
    """
    import colorsys
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue_deg = round(h * 360)               # 0-360
    if brightness == 1000:
        # use the HSV Value as the color's natural brightness
        bri = round(v * 1000)
        bri = max(50, bri)                 # hardware minimum 50
    else:
        bri = max(50, min(1000, brightness))

    hue_hi = (hue_deg >> 8) & 0xFF
    hue_lo = hue_deg & 0xFF                 # [0x 55 01 FF LEN PAYLOAD CHK]

    bri_hi = (bri >> 8) & 0xFF
    bri_lo = bri & 0xFF

    frame = [HEADER, CMD_SET_COLOR, SEQ, 0x09, hue_hi, hue_lo, bri_hi, bri_lo]
    frame.append(checksum(frame))
    return bytes(frame)



# --- Classic scenes ----------------------------------------------------------------
#
# Protocol (verified on btsnoop_hci_scene_classico.cfa):
#   CMD 0x06 SET_SCENE : 55 06 FF 07 00 [scene_id] [chk]
#   CMD 0x0F SET_SPEED : 55 0F FF 06 [speed]       [chk]
#
#   scene_id : byte 0-255 identifying the scene in the firmware.
#   speed    : byte 0-100 (0=stopped, 100=maximum), sent right after SET_SCENE.
#   LEN field: 0x07 for SET_SCENE (7 total bytes), 0x06 for SET_SPEED (6 total bytes).
#
#   Scene names in English in the scenes.py file.

# Scene catalog imported from scenes.py (109 scenes, single list).
from scenes import (
    Scene, ALL_SCENES,
    get_scene, get_scene_by_id,
    MusicScene, ALL_MUSIC_SCENES,
    get_music_scene, get_music_scene_by_id,
)


def cmd_set_scene(scene_id: int) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 06 FF 07 00 [scene_id] [CHK]
    """
    Select a classic scene by ID.

    Packet: 55 06 FF 07 00 [scene_id] [chk]   (7 total bytes)
      Byte [4]=0x00 fixed (always 0x00 in the capture).

    Always send cmd_set_speed() immediately afterwards.
    """
    scene_id = max(0, min(255, scene_id))
    frame = [HEADER, CMD_SET_SCENE, SEQ, 0x07, 0x00, scene_id]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_set_speed(speed: int) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 0F FF 06 SPEED [CHK]
    """
    Set the speed of the current effect.

    Packet: 55 0F FF 06 [raw_speed] [chk]   (6 total bytes)
      speed: 0=slow, 100=fast.
      The firmware uses an inverted scale (0=maximum, 100=stopped),
      so raw_speed = 100 - speed.

    Always send right after cmd_set_scene().
    """
    speed = max(0, min(100, speed))
    raw_speed = 100 - speed          # inversion: 100 = max speed
    frame = [HEADER, CMD_SET_SCENE_SPEED, SEQ, 0x06, raw_speed]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_set_music_scene(scene_id: int) -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 07 FF 06 [scene_id] [CHK]
    """
    Select a music scene (microphone mode) by ID.

    Packet: 55 07 FF 06 [scene_id] [chk]   (6 total bytes)
      scene_id: 1-6 (see ALL_MUSIC_SCENES in scenes.py).

    Must not be paired with cmd_set_speed(): microphone mode
    does not use the speed parameter (verified from the HCI capture).
    """
    scene_id = max(1, min(6, scene_id))
    frame = [HEADER, CMD_SET_SCENE_MIC, SEQ, 0x06, scene_id]
    frame.append(checksum(frame))
    return bytes(frame)


def days_mask(*days: str) -> int:
    """
    Build the days bitmask from readable names.
    Accepts: "mon" "tue" "wed" "thu" "fri" "sat" "sun"  or "all".
    Example: days_mask("mon","wed","fri","sun") -> 0x55
             days_mask("all")                  -> 0x7F
    """
    _MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6}
    if "all" in days:
        return 0x7F
    mask = 0
    for d in days:
        if d not in _MAP:
            raise ValueError(f"Invalid day: {d!r}  (valid: mon tue wed thu fri sat sun all)")
        mask |= (1 << _MAP[d])
    return mask


def cmd_set_schedule(
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 0A FF 0D (8-byte payload, see below) CHK]
    on_active:  bool, on_hh:  int, on_mm:  int, on_days:  int,
    off_active: bool, off_hh: int, off_mm: int, off_days: int,
    ) -> bytes:
    """
    Set the weekly power-on / power-off schedule.

    Real packet structure (from btsnoop, cmd 0x0A, 8-byte payload):
      55 0A FF 0D
        [ON_FLAG]  [ON_HH]  [ON_MM]  [ON_DAYS]
        [OFF_FLAG] [OFF_HH] [OFF_MM] [OFF_DAYS]
      [CHK]

    Parameters:
      on_active  : True = power-on schedule enabled
      on_hh      : power-on hour 0-23
      on_mm      : power-on minute 0-59
      on_days    : days bitmask (bit0=mon ... bit6=sun); use days_mask()
      off_active : True = power-off schedule enabled
      off_hh     : power-off hour 0-23
      off_mm     : power-off minute 0-59
      off_days   : days bitmask; use days_mask()

    Flag logic (both flags use the same encoding):
      ON_FLAG  : 0x01=active  0x00=inactive
      OFF_FLAG : 0x01=active  0x00=inactive

    Payload structure:
      55 0A FF 0D [ON_FLAG][ON_HH][ON_MM][ON_DAYS] [OFF_FLAG][OFF_HH][OFF_MM][OFF_DAYS] [CHK]
      Flag: 0x01=active  0x00=inactive  (same logic for both)

    Days bitmask: bit0=mon bit1=tue bit2=wed bit3=thu bit4=fri bit5=sat bit6=sun
      0x7F = all days
      0x1F = mon-fri (weekdays)
      0x60 = sat+sun (weekend)
    """
    payload = bytes([
        0x01 if on_active  else 0x00,          # ON_FLAG:  0x01=active  0x00=inactive
        on_hh  & 0xFF, on_mm  & 0xFF, on_days  & 0x7F,
        0x01 if off_active else 0x00,          # OFF_FLAG: 0x01=active  0x00=inactive
        off_hh & 0xFF, off_mm & 0xFF, off_days & 0x7F,
    ])
    frame = [HEADER, CMD_SCHEDULE, SEQ, 0x0D, *payload]
    frame.append(checksum(frame))
    return bytes(frame)


def cmd_set_time() -> bytes:
    # [0x HEAD CMD SEQ LEN PAYLOAD CHK]
    # [0x 55 0C FF 0D YEAR_HI YEAR_LO MONTH DAY HOUR MIN SEC WEEKDAY CHK]
    """
    Set the device's date/time, read automatically from the PC clock
    (no arguments: uses datetime.now()).

    Real packet structure (from btsnoop, cmd 0x0C, 13 total bytes):
      55 0C FF 0D [YEAR_HI][YEAR_LO][MONTH][DAY][HOUR][MIN][SEC][WEEKDAY] [CHK]

      YEAR    : uint16 big-endian          (e.g. 2026 -> 0x07 0xEA)
      MONTH   : 1-12
      DAY     : 1-31
      HOUR    : 0-23
      MIN     : 0-59
      SEC     : 0-59
      WEEKDAY : ISO weekday, 1=Monday ... 7=Sunday
    """
    now = datetime.datetime.now()
    year_hi = (now.year >> 8) & 0xFF
    year_lo = now.year & 0xFF
    frame = [
        HEADER, CMD_SET_TIME, SEQ, 0x0D,
        year_hi, year_lo, now.month, now.day,
        now.hour, now.minute, now.second, now.isoweekday(),
    ]
    frame.append(checksum(frame))
    return bytes(frame)



# --- FFF4 notification parsing ----------------------------------------------------------

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def days_str(mask: int) -> str:
    return "+".join(DAYS[i] for i in range(7) if mask & (1 << i)) or "none"

def mic_raw_to_pct(raw: int) -> str:
    """Convert the mic_sens byte (60-100) to a readable percentage (0-100%)."""
    return f"{remap(raw, 60, 100, 0, 100)}%"

@dataclass
class DeviceState:
    power:      bool
    brightness: int          # 50-1000
    on_sched:   bool
    on_time:    str          # "HH:MM"
    on_days:    str
    off_sched:  bool
    off_time:   str
    off_days:   str
    n_led:      int
    mic_sens:   str
    raw:        bytes

    def __str__(self) -> str:
        pwr = "ON" if self.power else "OFF"
        bri_pct = round((self.brightness - 50) / (1000 - 50) * 100)
        on  = f"{'OK' if self.on_sched  else '--'} {self.on_time}  [{self.on_days}]"
        off = f"{'OK' if self.off_sched else '--'} {self.off_time} [{self.off_days}]"
        return (
            f"power={pwr}  brightness={self.brightness}/1000 ({bri_pct}%)\n"
            f"  power-on sched. : {on}\n"
            f"  power-off sched.: {off}\n"
            f"  LED={self.n_led}  mic={self.mic_sens}"
        )


def parse_notification(data: bytes) -> str:
    """Decode the NOTIFY FFF4 response."""
    if len(data) < 4 or data[0] != 0x56:
        return f"[unrecognized raw] {data.hex().upper()}"

    chk_ok = (sum(data) & 0xFF) == 0xFF
    chk_tag = "" if chk_ok else " WARN CHK_ERR"

    if len(data) == 19:
        # FFF4 notification: data[7..10]=power-on, data[11..14]=power-off
        # flag: 0x01=active  0x00=inactive
        state = DeviceState(
            power      = (data[4] == 0x01),
            brightness = (data[5] << 8) | data[6],
            on_sched   = (data[7]  == 0x01),
            on_time    = f"{data[8]:02d}:{data[9]:02d}",
            on_days    = days_str(data[10]),
            off_sched  = (data[11] == 0x01),
            off_time   = f"{data[12]:02d}:{data[13]:02d}",
            off_days   = days_str(data[14]),
            n_led      = data[16],
            mic_sens   = mic_raw_to_pct(data[17]),
            raw        = data,
        )
        return f"STATUS{chk_tag}\n{state}"

    # short ACK (6 bytes)
    if len(data) == 6:
        cmd_echo = data[1]
        name = {0x01:"POWER", 0x03:"COLOR", 0x05:"BRIGHTNESS",
                0x0E:"HANDSHAKE"}.get(cmd_echo, f"CMD_0x{cmd_echo:02X}")
        return f"ACK {name}{chk_tag}"

    return f"[notification] cmd=0x{data[1]:02X} raw={data.hex().upper()}{chk_tag}"


# --- Bluetooth helper ---------------------------------------------------------------

def is_bluetooth_enabled() -> bool:
    """
    Check whether the host's Bluetooth adapter is powered on.

    Uses BlueZ via D-Bus on Linux (org.bluez, Powered property of the
    default adapter hci0). Returns True if it cannot be determined
    (fail-open), so the connection attempt is the final source of truth.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["bluetoothctl", "show"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return True
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("powered:"):
                return line.split(":", 1)[1].strip().lower() == "yes"
        return True
    except Exception:
        # bluetoothctl not available or failed: do not block the connection
        return True



# --- Controller ---------------------------------------------------------------------

class LEDController:
    def __init__(self, mac: str):
        self.mac    = mac
        self.client = BleakClient(mac, timeout=15.0)
        self._last_state: Optional[DeviceState] = None

    async def connect(self) -> bool:
        if not is_bluetooth_enabled():
            print("Turn on bluetooth")
            return False
        log.info(f"Connecting to {self.mac} ...")
        await self.client.connect()
        if not self.client.is_connected:
            log.error("Connection failed.")
            return False
        log.info("Connected. Enabling notifications...")
        await self.client.start_notify(UUID_NOTIFY, self._on_notify)
        await asyncio.sleep(0.3)
        # mandatory handshake
        await self._send(cmd_handshake())
        await asyncio.sleep(0.4)
        return True

    async def disconnect(self) -> None:
        if self.client.is_connected:
            try:
                await self.client.stop_notify(UUID_NOTIFY)
            except Exception:
                pass
            await self.client.disconnect()
            log.info("Disconnected.")

    async def _send(self, packet: bytes) -> None:
        log.debug(f"-> WRITE {packet.hex().upper()}")
        # response=None -> bleak 3.x auto-detects the characteristic property
        await self.client.write_gatt_char(UUID_WRITE, packet, response=None)

    def _on_notify(self, _handle, data: bytes) -> None:
        # Save the last full state (used by set_schedule to keep values)
        if len(data) == 19 and data[0] == 0x56:
            self._last_state = DeviceState(
                power      = (data[4] == 0x01),
                brightness = (data[5] << 8) | data[6],
                on_sched   = (data[7]  == 0x01),
                on_time    = f"{data[8]:02d}:{data[9]:02d}",
                on_days    = days_str(data[10]),
                off_sched  = (data[11] == 0x01),
                off_time   = f"{data[12]:02d}:{data[13]:02d}",
                off_days   = days_str(data[14]),
                n_led      = data[16],
                mic_sens   = mic_raw_to_pct(data[17]),
                raw        = data,
            )
        msg = parse_notification(data)
        log.info(f"<- {msg}")

    # -- Public API ------------------------------------------------------------------

    async def query(self) -> None:
        """Read the current state from the device."""
        log.info("Requesting status...")
        await self._send(cmd_query_status())
        await asyncio.sleep(0.4)

    async def power_on(self) -> None:
        log.info("Powering on...")
        await self._send(cmd_power(True))
        await asyncio.sleep(0.3)

    async def power_off(self) -> None:
        log.info("Powering off...")
        await self._send(cmd_power(False))
        await asyncio.sleep(0.3)

    async def set_color(self, r: int, g: int, b: int) -> None:
        """Set RGB color via HUE+brightness (CMD 0x03)."""
        log.info(f"RGB color ({r},{g},{b}) #{r:02X}{g:02X}{b:02X}")
        await self._send(cmd_set_color(r, g, b))
        await asyncio.sleep(0.2)

    async def set_brightness(self, value: int) -> None:
        """Set brightness
        input  1 ... 100%
        output 50 (min) ... 1000 (max)."""
        val=remap(value,1,100,50,1000)
        log.info(f"Brightness: {val}={value}%")
        await self._send(cmd_set_brightness(val))
        await asyncio.sleep(0.2)

    async def set_sens_mic(self, value: int) -> None:
        """Set microphone sensitivity:
        input  0 ... 100%
        output 60 (min) ... 100 (max)."""
        val=remap(value,0,100,60,100)
        log.info(f"Mic sensitivity: {val}={value}%")
        await self._send(cmd_set_sens_mic(val))
        await asyncio.sleep(0.2)

    async def set_scene(self, scene_id: int, speed: int | None = None) -> None:
        """
        Activate a scene by numeric ID (0-255, see scenes.py for the catalog).
        speed: 0-100; if None, uses the scene's default, otherwise 50.

        Example:
          await led.set_scene(2)            # Symphony, default speed 50
          await led.set_scene(84, speed=80)  # Red run, speed 80
        """
        known = get_scene_by_id(scene_id)
        default_speed = known.speed if known else 50
        spd = speed if speed is not None else default_speed
        log.info(f"Scene ID={scene_id}  speed={spd}")
        await self._send(cmd_set_scene(scene_id))
        await asyncio.sleep(0.1)
        await self._send(cmd_set_speed(spd))
        await asyncio.sleep(0.2)

    async def set_scene_by_name(self, name: str, speed: int | None = None) -> None:
        """
        Activate a scene by name (case-insensitive).
        109 scenes available: classic, festival, other (see scenes.py or CLI 'scenes').

        Example:
          await led.set_scene_by_name("Aurora")
          await led.set_scene_by_name("Blue run", speed=80)
          await led.set_scene_by_name("Cycle")
        """
        scene = get_scene(name)
        if scene is None:
            log.error(f"Scene not found: {name!r}. Use 'python ble_led.py scenes' for the list.")
            return
        spd = speed if speed is not None else scene.speed
        log.info(f"Scene '{scene.name}' (ID={scene.scene_id})  speed={spd}")
        await self._send(cmd_set_scene(scene.scene_id))
        await asyncio.sleep(0.1)
        await self._send(cmd_set_speed(spd))
        await asyncio.sleep(0.2)

    async def set_music_scene(self, scene_id: int) -> None:
        """
        Activate a music scene by numeric ID (1-6, see scenes.py).
        Does not use speed: microphone mode does not support CMD 0x0F.

        Example:
          await led.set_music_scene(1)   # Spectrum1
          await led.set_music_scene(6)   # Rhythm
        """
        known = get_music_scene_by_id(scene_id)
        name_label = known.name if known else f"ID={scene_id}"
        log.info(f"Music scene '{name_label}' (ID={scene_id})")
        await self._send(cmd_set_music_scene(scene_id))
        await asyncio.sleep(0.2)

    async def set_music_scene_by_name(self, name: str) -> None:
        """
        Activate a music scene by name (case-insensitive).
        Available scenes: Spectrum1, Spectrum2, Spectrum3, Flowing, Rolling, Rhythm.

        Example:
          await led.set_music_scene_by_name("Spectrum2")
          await led.set_music_scene_by_name("Rhythm")
        """
        scene = get_music_scene(name)
        if scene is None:
            log.error(f"Music scene not found: {name!r}. Use 'python ble_led.py music' for the list.")
            return
        log.info(f"Music scene '{scene.name}' (ID={scene.scene_id})")
        await self._send(cmd_set_music_scene(scene.scene_id))
        await asyncio.sleep(0.2)

    async def set_schedule(
        self,
        on_active:  bool, on_hh:  int, on_mm:  int, on_days:  int,
        off_active: bool, off_hh: int, off_mm: int, off_days: int,
    ) -> None:
        """
        Set the weekly schedule.

        Example - power on every day at 19:00, power off at 23:30:
          await led.set_schedule(
              on_active=True,  on_hh=19, on_mm=0,  on_days=days_mask("all"),
              off_active=True, off_hh=23, off_mm=30, off_days=days_mask("all"),
          )

        To disable only one of the two sides, pass active=False
        (time and days are still stored by the device).
        """
        on_label  = f"{'ENABLE' if on_active  else 'DISABLE'} {on_hh:02d}:{on_mm:02d}  [{days_str(on_days)}]"
        off_label = f"{'ENABLE' if off_active else 'DISABLE'} {off_hh:02d}:{off_mm:02d} [{days_str(off_days)}]"
        log.info("New schedule")
        log.info(f"Power-on schedule : {on_label}")
        log.info(f"Power-off schedule: {off_label}")
        await self._send(cmd_set_schedule(
            on_active,  on_hh,  on_mm,  on_days,
            off_active, off_hh, off_mm, off_days,
        ))
        await asyncio.sleep(0.3)

    async def set_time(self) -> None:
        """
        Sync the device's date/time with the PC's system clock.
        No arguments: the time is read automatically via datetime.now().

        Always called before any 'schedule' sub-command, so the weekly
        on/off schedule is evaluated by the device against the correct
        current day and time.
        """
        now = datetime.datetime.now()
        log.info(f"Setting device time: {now:%Y-%m-%d %H:%M:%S} ({now:%A})")
        await self._send(cmd_set_time())
        await asyncio.sleep(0.2)

    # -- Color shortcuts ----------------------------------------------------------------

    async def red(self)     -> None: await self.set_color(255,   0,   0)
    async def green(self)   -> None: await self.set_color(  0, 255,   0)
    async def blue(self)    -> None: await self.set_color(  0,   0, 255)
    async def white(self)   -> None: await self.set_color(255, 255, 255)
    async def yellow(self)  -> None: await self.set_color(255, 160,   0)
    async def magenta(self) -> None: await self.set_color(255,   0, 255)
    async def cyan(self)    -> None: await self.set_color(  0, 255, 255)
    async def warm(self)    -> None: await self.set_color(255, 140,  20)

    # -- Demo --------------------------------------------------------------------------

    async def demo(self) -> None:
        log.info("====== DEMO START ======")

        await self.query()
        await self.power_on()
        await asyncio.sleep(0.5)

        # Static colors
        for name, (r, g, b) in [
            ("Red",     (255,  0,    0)),
            ("Green",   (  0, 255,   0)),
            ("Blue",    (  0,   0, 255)),
            ("White",   (255, 255, 255)),
            ("Yellow",  (255, 160,   0)),
            ("Cyan",    (  0, 255, 255)),
            ("Magenta", (255,   0, 255)),
        ]:
            log.info(f"  -> {name}")
            await self.set_color(r, g, b)
            await asyncio.sleep(1.5)

        # Brightness
        log.info("  -> Brightness fade")
        for v in [100, 75, 50, 25, 10, 25, 50, 75, 100]:
            await self.set_brightness(v)
            await asyncio.sleep(0.4)

        # Classic scenes
        log.info("  -> Classic scenes")
        for name in ["Green-blue flowing water", "Seven-color drift", "Seven-color flowing water", "Seven-color chase", "Run with red dot on blue background"]:
            log.info(f"     {name}")
            await self.set_scene_by_name(name)
            await asyncio.sleep(3)

        await self.white()
        await asyncio.sleep(1)
        await self.power_off()
        log.info("====== DEMO END ======")


# --- Scanning ------------------------------------------------------------------------

async def scan(timeout: float = 10.0) -> None:
    log.info(f"BLE scan ({timeout:.0f}s) ...")
    # bleak 3.x: rssi is in AdvertisementData, not in BLEDevice
    scanner = BleakScanner()
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    devices = scanner.discovered_devices_and_advertisement_data
    if not devices:
        log.info("No devices found.")
        return

    # sort by descending RSSI
    items = sorted(
        devices.values(),
        key=lambda pair: pair[1].rssi if pair[1].rssi is not None else -999,
        reverse=True,
    )
    log.info(f"Found {len(items)} devices:")
    for dev, adv in items:
        rssi = f"{adv.rssi:+d}dBm" if adv.rssi is not None else "?dBm"
        name = dev.name or adv.local_name or "?"
        log.info(f"  {dev.address}  {rssi:>8s}  {name}")


# --- Entry point ----------------------------------------------------------------------

HELP = """
Usage:  python ble_led.py <command> [args]

Basic commands:
  scan                         Search for nearby BLE devices
  demo                         Full demo sequence
  on                           Power on
  off                          Power off
  color <R> <G> <B>            Set RGB color 0-255  (e.g. color 255 0 0)
  brightness <1-100>           Brightness in % (1=min 100=max)
  sens <0-100>                 Mic sensitivity in % (0=min 100=max)
  query                        Read current status
  time                         Sync device date/time with the PC clock (no args)

Scenes:
  scene <name> [speed]         Activate scene by name (speed 0-100, optional)
  scene id <N> [speed]         Activate scene by numeric ID 0-255
  scenes                       List all 109 scenes
  scenes <text>                Filter by name or ID  (e.g. scenes run | scenes 23)

  109 scenes: Cycle, Fantastic color, seven-color Energy/Jump/Flash/Gradient,
  Accumulation, Chase, Drift, Spread, Opening and closing,
  Light-to-dark transition, Flowing water, Flow, Run, Run with dot...

  Examples:
    scene "Green-blue flowing water"
    scene "Seven-color chase" 80
    scene id 23 20
    scenes run

Music scenes (microphone mode):
  music <name>                 Activate music scene by name
  music id <N>                 Activate music scene by numeric ID 1-6
  music                        List the 6 music scenes

  Scenes: Spectrum1 (1)  Spectrum2 (2)  Spectrum3 (3)
          Flowing (4)    Rolling (5)   Rhythm (6)

  Examples:
    music Spectrum2
    music id 4
    music id 6

Schedule:
  schedule on  <HH:MM> <days>               Enable power-on schedule
  schedule on  enable|disable               Enable/disable power-on (keeps saved time)
  schedule off <HH:MM> <days>               Enable power-off schedule
  schedule off enable|disable               Enable/disable power-off (keeps saved time)
  schedule both <HH:MM> <HH:MM> <days>      Set power-on and power-off together
  schedule clear                            Disable both schedules

  Note: every 'schedule' sub-command automatically syncs the device
        time first (calls set_time() with no arguments).

  <days>: comma-separated list or "all"
          values: mon tue wed thu fri sat sun
          examples: all   mon,wed,fri   mon,tue,wed,thu,fri

Quick colors: red  green  blue  white  yellow  cyan  magenta  warm
  Examples:
    python ble_led.py red
    python ble_led.py yellow
"""

async def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print(HELP)
        return

    cmd_str = sys.argv[1].lower()

    if cmd_str in ("h", "help"):
        print(HELP)
        return

    if cmd_str == "scan":
        await scan()
        return

    led = LEDController(MAC_ADDRESS)
    try:
        if not await led.connect():
            return

        if   cmd_str == "demo":       await led.demo()
        elif cmd_str == "on":         await led.power_on()
        elif cmd_str == "off":        await led.power_off()
        elif cmd_str == "query":      await led.query()
        elif cmd_str == "time":	      await led.set_time()
        elif cmd_str == "red":        await led.red()
        elif cmd_str == "green":      await led.green()
        elif cmd_str == "blue":       await led.blue()
        elif cmd_str == "white":      await led.white()
        elif cmd_str == "yellow":     await led.yellow()
        elif cmd_str == "cyan":       await led.cyan()
        elif cmd_str == "magenta":    await led.magenta()
        elif cmd_str == "warm":       await led.warm()

        elif cmd_str == "color":
            if len(sys.argv) < 5:
                print("Usage: color <R> <G> <B>")
            else:
                await led.set_color(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))

        elif cmd_str == "brightness":
            if len(sys.argv) < 3:
                print("Usage: brightness <1-100>")
            else:
                val = int(sys.argv[2])
                if not ( 1 <= val <= 100 ):
                    print("Usage: brightness <1-100>")
                else:
                    await led.set_brightness(val)

        elif cmd_str == "sens":
            if len(sys.argv) < 3:
                print("Usage: sens <0-100>")
            else:
                val = int(sys.argv[2])
                if not ( 0 <= val <= 100 ):
                    print("Usage: sens <0-100>")
                else:
                    await led.set_sens_mic(val)

        elif cmd_str == "scene":
            if len(sys.argv) < 3:
                print("Usage: scene <name> [speed]  or  scene id <N> [speed]")
            elif sys.argv[2].lower() == "id":
                if len(sys.argv) < 4:
                    print("Usage: scene id <N> [speed]")
                else:
                    sid   = int(sys.argv[3])
                    speed = int(sys.argv[4]) if len(sys.argv) >= 5 else None
                    if speed is not None and not (0 <= speed <= 100):
                        print("Usage: scene id <N> [speed 0-100]")
                    else:
                        await led.set_scene(sid, speed)
            else:
                # name with optional speed (can be multi-word: "Space Time")
                # Strategy: try the full name first, then drop the last token if it's a number
                args_rest = sys.argv[2:]
                speed = None
                if args_rest and args_rest[-1].isdigit():
                    speed = int(args_rest[-1])
                    args_rest = args_rest[:-1]
                name = " ".join(args_rest)
                if speed is not None and not (0 <= speed <= 100):
                    print("Usage: scene <name> [speed 0-100]")
                else:
                    await led.set_scene_by_name(name, speed)

        elif cmd_str == "scenes":
            query = sys.argv[2].lower() if len(sys.argv) > 2 else None
            matches = [
                s for s in ALL_SCENES
                if query is None or query in s.name.lower() or query == str(s.scene_id)
            ]
            print(f"\n  {'ID':>4}  {'Speed':>5}  Name")
            print(f"  {'-'*4}  {'-'*5}  {'-'*40}")
            for s in matches:
                print(f"  {s.scene_id:>4}  {s.speed:>5}  {s.name}")
            suffix = f"  (filter: {query!r})" if query else ""
            print(f"\n  {len(matches)} scenes{suffix}  |  Total: {len(ALL_SCENES)}")

        elif cmd_str == "music":
            # music                    -> list music scenes
            # music id <N>             -> by ID
            # music <name>             -> by name
            if len(sys.argv) < 3:
                # List music scenes
                print(f"\n  {'ID':>4}  Name")
                print(f"  {'-'*4}  {'-'*20}")
                for s in ALL_MUSIC_SCENES:
                    print(f"  {s.scene_id:>4}  {s.name}")
                print(f"\n  {len(ALL_MUSIC_SCENES)} music scenes  |  CMD 0x07 (SET_SCENE_MIC)")
            elif sys.argv[2].lower() == "id":
                if len(sys.argv) < 4:
                    print("Usage: music id <N>")
                else:
                    sid = int(sys.argv[3])
                    await led.set_music_scene(sid)
            else:
                name = sys.argv[2]
                await led.set_music_scene_by_name(name)

        elif cmd_str == "schedule":
            # -- Parsing helpers ---------------------------------------------
            def parse_time(s: str):
                """'HH:MM' -> (hh, mm)  with range check [00..23] and [00..59]."""
                parts = s.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Invalid time format {s!r}: expected HH:MM")
                try:
                    hh, mm = int(parts[0]), int(parts[1])
                except ValueError:
                    raise ValueError(f"Invalid time {s!r}: hours and minutes must be integers")
                if not (0 <= hh <= 23):
                    raise ValueError(f"Invalid hour {hh}: must be in range 0-23")
                if not (0 <= mm <= 59):
                    raise ValueError(f"Invalid minute {mm}: must be in range 0-59")
                return hh, mm

            def parse_days(s: str) -> int:
                """'mon,wed,fri' or 'all' -> bitmask"""
                return days_mask(*[g.strip() for g in s.split(",")])

            sub = sys.argv[2].lower() if len(sys.argv) > 2 else ""

            # -- Sync device time (always done before any schedule sub-command) --
            await led.set_time()

            # -- Read current state (needed for all sub-commands) -------------
            log.info("Reading current schedule state")
            await led.query()
            await asyncio.sleep(0.6)
            state = led._last_state

            # Fallback values if the device does not respond
            if state:
                cur_on_active      = state.on_sched
                cur_on_hh, cur_on_mm   = map(int, state.on_time.split(":"))
                cur_off_active     = state.off_sched
                cur_off_hh, cur_off_mm = map(int, state.off_time.split(":"))
            else:
                cur_on_active  = False
                cur_on_hh, cur_on_mm   = 0, 0
                cur_off_active = False
                cur_off_hh, cur_off_mm = 0, 0

            # days: not exposed by the state, always use 0x7F (all)
            cur_on_days  = 0x7F
            cur_off_days = 0x7F

            try:
                if sub == "on":
                    third = sys.argv[3].lower() if len(sys.argv) > 3 else ""
                    if third in ("enable", "disable"):
                        # Change only the flag; on time and days unchanged
                        await led.set_schedule(
                            (third == "enable"), cur_on_hh,  cur_on_mm,  cur_on_days,
                            cur_off_active,      cur_off_hh, cur_off_mm, cur_off_days,
                        )
                    elif len(sys.argv) < 5:
                        print("Usage: schedule on <HH:MM> <days>")
                        print("     e.g.: schedule on 19:00 all")
                        print("     or: schedule on enable|disable")
                    else:
                        # New power-on time, enable; off side unchanged
                        on_hh, on_mm = parse_time(sys.argv[3])
                        on_days      = parse_days(sys.argv[4])
                        await led.set_schedule(
                            True,          on_hh,       on_mm,       on_days,
                            cur_off_active, cur_off_hh, cur_off_mm, cur_off_days,
                        )

                elif sub == "off":
                    third = sys.argv[3].lower() if len(sys.argv) > 3 else ""
                    if third in ("enable", "disable"):
                        # Change only the flag; off time and days unchanged
                        await led.set_schedule(
                            cur_on_active,      cur_on_hh,  cur_on_mm,  cur_on_days,
                            (third == "enable"), cur_off_hh, cur_off_mm, cur_off_days,
                        )
                    elif len(sys.argv) < 5:
                        print("Usage: schedule off <HH:MM> <days>")
                        print("     e.g.: schedule off 23:30 mon,tue,wed,thu,fri")
                        print("     or: schedule off enable|disable")
                    else:
                        # New power-off time, enable; on side unchanged
                        off_hh, off_mm = parse_time(sys.argv[3])
                        off_days       = parse_days(sys.argv[4])
                        await led.set_schedule(
                            cur_on_active, cur_on_hh, cur_on_mm, cur_on_days,
                            True,          off_hh,    off_mm,    off_days,
                        )

                elif sub == "both":
                    # schedule both HH:MM HH:MM days  -> set both and enable
                    if len(sys.argv) < 6:
                        print("Usage: schedule both <ON_HH:MM> <OFF_HH:MM> <days>")
                        print("     e.g.: schedule both 08:00 22:00 sat,sun")
                    else:
                        on_hh,  on_mm  = parse_time(sys.argv[3])
                        off_hh, off_mm = parse_time(sys.argv[4])
                        days           = parse_days(sys.argv[5])
                        await led.set_schedule(
                            True, on_hh,  on_mm,  days,
                            True, off_hh, off_mm, days,
                        )

                elif sub == "clear":
                    # Disable both flags; times and days unchanged
                    await led.set_schedule(
                        False, cur_on_hh,  cur_on_mm,  cur_on_days,
                        False, cur_off_hh, cur_off_mm, cur_off_days,
                    )
                    log.info("Schedules disabled.")

                else:
                    print(f"Unrecognized schedule sub-command: {sub!r}")
                    print("Valid: on  off  both  clear")

            except ValueError as e:
                print(f"Error: {e}")

        else:
            print(f"Unrecognized command: {cmd_str}")
            print(HELP)

        await asyncio.sleep(0.3)

    except Exception as e:
        log.error(f"Error: {e}")
        raise
    finally:
        await led.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

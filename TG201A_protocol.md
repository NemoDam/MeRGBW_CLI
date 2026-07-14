# TG201A PROTOCOL

## Protocol notes

The full BLE packet protocol (CMD bytes, payload structure, checksum,
NOTIFY format) is documented in the module docstring at the top of
`ble_led.py`.  
It was reverse-engineered from BLE HCI captures of the official MeRGBw app.


## Device info

| Campo                 | Valore                       |
|-----------------------|------------------------------|
| BLE name              | LED Lights                   |
| MAC Address           | `41:42:81:AB:60:BB`          |
| Model                 | TG201A                       |
| Service BLE           | `0000fff0`                   |
| WRITE characteristic  | `0000fff3` (handle `0x0009`) |
| NOTIFY characteristic | `0000fff4` (handle `0x000b`) |


| Tipo            | UUID / Nome                                       | Handle   |
| --------------- | ------------------------------------------------- | -------- |
| WRITE (comandi) | -> FFF3 "0000fff3-0000-1000-8000-00805f9b34fb"    | `0x0009` |
| NOTIFY (stato)  | <- FFF4 "0000fff4-0000-1000-8000-00805f9b34fb"    | `0x000b` |

-----------------------------------------------------------------------------------------

<br>

## **FFF3 packet protocol (WRITE)**:

### Packet structure:  
[0x HEAD CMD SEQ LEN PAYLOAD CHK]
| Field   | Description                        |
| ------- | ---------------------------------- |
| HEADER  | `0x55` Fixed start byte            |
| CMD     | * Command identifier               |
| SEQ     | `0xFF` Sequence byte               |
| LEN_TOT | Total packet length                |
| PAYLOAD | Variable data depending on command |
| CHK     | Checksum                           |

<br>

### CMD commands identifier:
| CMD    | Name            | Payload                       | Description                |
| ------ | --------------- | ----------------------------- | -------------------------- |
| `0x00` | QUERY STATUS    | none                          | Request device status      |
| `0x01` | POWER ON/OFF    | 1-byte payload                | Toggle power state         |
| `0x03` | COLOR           | 4-byte payload                | Set color and brightness   |
| `0x05` | BRIGHTNESS      | 2-byte payload                | Set brightness only        |
| `0x06` | SCENE           | 2-byte payload                | Set scene                  |
| `0x07` | SCENE MIC       | 1-byte payload                | Set scene mic/musica       |
| `0x08` | MIC SENSITIVITY | 1-byte payload                | Set microphone sensitivity |
| `0x0A` | SCHEDULE        | 8-byte payload                | Configure scheduling       |
| `0x0C` | SET TIME        | 8-byte payload                | Set the device's date/time |
| `0x0E` | HANDSHAKE       | 6-byte fixed token            | Device initialization      |
| `0x0F` | SCENE SPEED     | 1-byte payload                | Set scene speed            |

#### QUERY STATUS (CMD `0x00`) no payload:  
0x 55 00 FF 05 CHK 

#### POWER ON/OFF (CMD `0x01`) and payload:  
0x 55 01 FF 06 PAYLOAD CHK  
payload = [ 0x01 ]  # ON  
or  
payload = [ 0x00 ]  # OFF

#### COLOR (CMD `0x03`) and payload:  
0x 55 03 FF 09 PAYLOAD CHK  
payload = [ HUE_HI, HUE_LO, BRI_HI, BRI_LO ]  

#### BRIGHTNESS (CMD `0x05`) and payload:  
0x 55 05 FF 07 PAYLOAD CHK  
payload = [ BRI_HI, BRI_LO ]  # 16-bit brightness value  
min, max = [ 0x0032, 0x03E8 ]  # 50–1000

#### SCENE (CMD `0x06`) and payload:  
0x 55 06 FF 07 PAYLOAD CHK  
payload = [ 0x00, SCENE_ID ]  # 0 - 255 scene ID

#### SCENE MIC (CMD `0x07`) and payload:  
0x 55 07 FF 06 PAYLOAD CHK  
payload = [ SCENE_ID ]  # Scene ID for microphone mode [1..6]  

#### MIC SENSITIVITY (CMD `0x08`) and payload:  
0x 55 08 FF 06 PAYLOAD CHK  
payload = [ SENS ]  # 8-bit sensitivity value  
min, max = [ 0x3C, 0x64 ]  # 60–100

#### SCHEDULE (CMD `0x0A`) and payload:  
0x 55 0A FF 0D PAYLOAD CHK  
payload = [ ON_FLAG, ON_HH, ON_MM, ON_DAYS, OFF_FLAG, OFF_HH, OFF_MM, OFF_DAYS ]  
ON_FLAG and OFF_FLAG: 0x01=active  0x00=inactive  (same logic for both)  
ON_HH, ON_MM, OFF_HH, OFF_MM: 0-23 hours, 0-59 minutes  
ON_DAYS and OFF_DAYS  
Weekday bitmask:  
| Bit  | Day       |  
| ---- | --------- |  
| bit0 | Monday    |  
| bit1 | Tuesday   |  
| bit2 | Wednesday |  
| bit3 | Thursday  |  
| bit4 | Friday    |  
| bit5 | Saturday  |  
| bit6 | Sunday    |  

#### SET TIME (CMD `0X0C`) and payload:
0x 55 0C FF 0D PAYLOAD CHK  
payload = [ YEAR_HI YEAR_LO MONTH DAY HOUR MIN SEC WEEKDAY ]  
YEAR    : uint16 big-endian          (e.g. 2026 -> 0x07 0xEA)  
MONTH   : 1-12  
DAY     : 1-31  
HOUR    : 0-23  
MIN     : 0-59  
SEC     : 0-59  
WEEKDAY : ISO weekday, 1=Monday ... 7=Sunday  

#### HANDSHAKE (CMD `0x0E`) and payload:  
0x 55 0E FF 0B PAYLOAD CHK  
payload = [ 0xA0, 0x2A, 0x48, 0x63, 0x53, 0x97 ]

#### SCENE SPEED (CMD `0x0F`) and payload:  
0x 55 0F FF 06 PAYLOAD CHK  
payload = [ SPEED ]  # 0 - 255 speed value  
min, max = [ 0x64, 0x00 ]  # 0x64 = slowest, 0x00 = fastest  

-----------------------------------------------------------------------------------------

<br>

## **FFF4 packet protocol (NOTIFY, 19 bytes)**:

### Packet structure:  

| Index | Field     | Description                             |
| ----- | --------- | --------------------------------------- |
| 0     | HEADER    | `0x56`                                  |
| 1     | CMD echo  | Returned command                        |
| 2     | FIXED     | `0xFF`                                  |
| 3     | LENGTH    | `0x14`                                  |
| 4     | power     | `0x00` OFF / `0x01` ON                  |
| 5     | lum_hi    | Brightness high byte                    |
| 6     | lum_lo    | Brightness low byte                     |
| 7     | on_sched  | Power-on schedule enabled               |
| 8     | on_hh     | Power-on hour                           |
| 9     | on_mm     | Power-on minute                         |
| 10    | on_days   | Weekday bitmask (bit6=Sun ... bit0=Mon) |
| 11    | off_sched | Power-off schedule enabled              |
| 12    | off_hh    | Power-off hour                          |
| 13    | off_mm    | Power-off minute                        |
| 14    | off_days  | Weekday bitmask                         |
| 15    | FIXED     | `0x00`                                  |
| 16    | n_led     | Number of LEDs in strip                 |
| 17    | mic_sens  | Microphone sensitivity                  |
| 18    | chk       | Checksum                                |

### Weekday bitmask
| Bit  | Day       |
| ---- | --------- |
| bit0 | Monday    |
| bit1 | Tuesday   |
| bit2 | Wednesday |
| bit3 | Thursday  |
| bit4 | Friday    |
| bit5 | Saturday  |
| bit6 | Sunday    |

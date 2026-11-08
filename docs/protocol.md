# UART protocol: v0.6

## Transport and framing

HardwareSerial runs at 9600 baud with its default 8N1 configuration.

```text
Byte 0: STX       0x02
Byte 1: CMD       command identifier
Byte 2: DATA      one byte
Byte 3: CHECKSUM  CMD XOR DATA
Byte 4: ETX       0x03
```

Frames are always five bytes. There is no LEN byte, variable-length payload,
sequence number, or acknowledgement.

## Commands

| Command | Identifier | DATA interpretation | Effect |
| --- | --- | --- | --- |
| SET_MODE | 0x01 | 0..4 | Assigns the corresponding state |
| SET_SPEED | 0x02 | Unused | No command handler |
| GET_STATUS | 0x03 | Ignored | Sends JSON telemetry |
| RESET | 0xFF | Ignored | AUTO; alarm false; buzzer low; servo 0 |

State values are IDLE=0, AUTO=1, MANUAL=2, ALARM=3, FAULT=4.
Invalid mode values are ignored. Unknown commands have no effect.
RESET does not reset the MCU, parser, sensor history, or scheduling timestamps.
Subsequent state-machine execution can re-enter ALARM.

Example GET_STATUS frame, in hexadecimal:

```text
02 03 00 03 03
```

## MCU-to-host output

A startup banner precedes normal telemetry:

```text
ArduCore v0.6 READY
```

JSON lines end with CRLF and are sent approximately every 500 ms and on
GET_STATUS. Only these fields exist:

```json
{"state":1,"dist":34.0,"temp":26.4,"alarm":false}
```

dist is stored distance in cm, temp is the computed temperature in C,
and alarm is the software flag. Initial values can be zero and values can be
stale. There are no ldr or speed fields and no validity or age fields.

## Parser limitations

The parser processes a command immediately after a matching checksum,
before reading ETX. A valid checksum can therefore cause side effects even
when ETX is missing or invalid.

After checksum handling, the parser waits indefinitely for ETX. It has no
frame timeout, explicit reset on a malformed terminator, or STX-based
resynchronization in that stage. The 64-byte software ring has 63 usable
slots and silently discards incoming bytes when full. It is filled from
the main loop through HardwareSerial, not directly by a custom USART ISR.

Malformed frames, interrupted frames, checksum errors, overflow, recovery,
and command ordering need tests before parser changes.

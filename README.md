# ArduCore

ArduCore is an embedded systems learning platform based on Arduino Uno R3
(ATmega328P, 16 MHz) and the Arduino AVR Core. It communicates with a host
computer through a binary UART command protocol and JSON telemetry.

## Engineering objectives

Develop register-level drivers, reliable communication, sensor validation,
fault recovery, and a hardware-independent application core, with a future
STM32 migration. These are development goals, not production-readiness claims.

## Current implementation: v0.6

The reviewed source is the supplied `arducore.ino`. It implements HC-SR04
measurement using a pin-change ISR, LM35 sampling, buzzer and Servo control,
a state machine, UART parsing, and periodic telemetry.

The firmware combines interrupts and millis-based scheduling with synchronous
Arduino APIs. It is not fully interrupt-driven or fully non-blocking:
ADC reads, short microsecond delays, and serial output can block.

This documentation initialization does not add or modify firmware. The supplied
sketch has not yet been imported into this repository. Compilation and physical
hardware behavior have not been verified in this environment. In particular,
integrated servo operation remains unverified. Native unit tests and CI are not
yet configured.

## Architecture

```text
Host computer <--- UART ---> Arduino Uno
                              |-- HC-SR04
                              |-- LM35
                              |-- Active buzzer
                              +-- SG90 servo
```

The current implementation is a single sketch. See
[architecture](docs/architecture.md) for current execution and planned modules.

## State machine

| Value | State | Current behavior |
| --- | --- | --- |
| 0 | IDLE | Buzzer low; servo commanded to 0 degrees |
| 1 | AUTO | Boot state; evaluates distance and temperature thresholds |
| 2 | MANUAL | Empty handler; planned |
| 3 | ALARM | Buzzer high; servo commanded to 180 degrees |
| 4 | FAULT | Empty handler; planned |

AUTO enters ALARM for a valid stored distance below 20 cm or temperature above
35 C. ALARM exits when stored distance exceeds 20 cm, regardless of temperature.
Transitions and hysteresis require validation. IDLE does not clear the alarm
flag; MANUAL and FAULT do not define safe output behavior.

## UART protocol

9600 baud using Arduino HardwareSerial (default 8N1).

```text
[STX 0x02][CMD][DATA][CHECKSUM][ETX 0x03]
CHECKSUM = CMD XOR DATA
```

There is no LEN field. Every command has one DATA byte.

| Command | Value | Current behavior |
| --- | --- | --- |
| SET_MODE | 0x01 | Accepts state values 0 through 4 |
| SET_SPEED | 0x02 | Identifier defined; no handler |
| GET_STATUS | 0x03 | Sends telemetry |
| RESET | 0xFF | Returns to AUTO; clears alarm; buzzer low; servo 0 |

Telemetry is sent approximately every 500 ms and on GET_STATUS:

```json
{"state":1,"dist":34.0,"temp":26.4,"alarm":false}
```

Startup also emits the plain-text line `ArduCore v0.6 READY`.
See [protocol](docs/protocol.md) for parser limitations.

## Hardware pin mapping

| Component | Arduino pin | Current use |
| --- | --- | --- |
| HC-SR04 TRIG | D4 | GPIO output |
| HC-SR04 ECHO | D6 | Pin-change interrupt |
| Active buzzer | D7 | Digital output |
| SG90 servo | D9 | Servo library signal |
| LM35 | A0 | Synchronous ADC input |

Additional devices are future candidates, not integrated features.
See [hardware](docs/hardware.md) for timer ownership and mapping caveats.

## Firmware build instructions

After importing the authoritative sketch unchanged at
`firmware/arducore/arducore.ino`, build for Arduino Uno using Arduino CLI:

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli lib install "Servo@1.2.2"
arduino-cli compile --fqbn arduino:avr:uno firmware/arducore
```

Servo 1.2.2 is a proposed explicit dependency pin; compatibility has not yet
been tested here. The commands cannot build this documentation-only checkout
until the sketch is imported. A successful cross-build would not establish
hardware correctness.

## Known limitations

Sensor disconnect handling, atomic ISR data access, ultrasonic timeout and
stale-data handling, alarm transitions, parser recovery, and buffer overflow
reporting need work. HardwareSerial owns USART interrupts; Servo owns Timer1.
MANUAL, FAULT, motor speed control, and watchdog recovery are incomplete or
absent. See [architecture](docs/architecture.md).

## Roadmap and STM32 migration

See the [versioned roadmap](docs/roadmap.md). Preserve the UART protocol while
introducing AVR drivers incrementally. Separate portable state and protocol
logic from MCU-specific peripherals before migrating to STM32; peripheral
assignments depend on the eventual board.

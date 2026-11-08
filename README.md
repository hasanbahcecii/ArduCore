# ArduCore

Arduino Uno R3 / ATmega328P, 16 MHz embedded learning platform. HC-SR04 and
LM35 readings drive an active buzzer and SG90 servo. A host sends binary UART
commands and receives JSON lines. Future STM32 migration is a learning goal.

## v0.8 isolated testing and peripheral drivers

This release repairs parsing, alarm transitions, sensor freshness, output
consistency and communication overload handling. It retains the portable
application core and watchdog, adds isolated build profiles and a Python host console, and
replaces Servo/analogRead with register-level Timer1/ADC drivers. Hardware
behavior has not been verified; this is not a production-readiness claim.

- UART: register-level USART0 RX/TX interrupts, 9600 baud, 8N1.
- Distance: pin-change ISR, atomic consumption, 30 ms echo deadline and 300 ms
  reading lifetime. Late/unmatched edges are ignored.
- Temperature: four interrupt-completed ADC readings per 200 ms request;
  fractional average preserved; nominal 5 V reference, application range (0,150] C, 750 ms lifetime.
- Telemetry: every 500 ms or on request; bounded whole-message TX queueing.
- Control: alarm thresholds with hysteresis; latched FAULT and explicit recovery.
- Watchdog: early disable, then two-second reset mode; fed after each full loop.

See [architecture](docs/architecture.md), [protocol](docs/protocol.md),
[hardware](docs/hardware.md) and [validation](docs/validation.md).

## Modes and outputs

| Value | Mode | Buzzer | Servo command |
| --- | --- | --- | --- |
| 0 | IDLE | Off | 0 degrees |
| 1 | AUTO | Off | 0 degrees |
| 2 | MANUAL | Off | 0 degrees; manual actuator control is not implemented |
| 3 | ALARM | On | 180 degrees |
| 4 | FAULT | On | 0 degrees |

Boot requests AUTO unless the application can observe the watchdog reset flag.
An automatic alarm enters below 20 cm or above 35 C, and clears only with both
valid readings, distance >=25 cm and temperature <=33 C. A host-requested ALARM
stays active until another accepted mode or RESET command.

After a one-second startup grace, missing/invalid sensor data latches FAULT in
active modes. IDLE permits missing sensors until another active mode is selected.
FAULT remains latched even after readings recover. RESET or SET_MODE AUTO can
release it only after 500 ms of continuously valid readings. Other mode requests
cannot bypass a latched fault. Output choices are application policy, not
hardware-verified safety positions.

## Wiring

| Component | Uno pin |
| --- | --- |
| HC-SR04 TRIG / ECHO | D4 / D6 |
| Active buzzer | D7 |
| SG90 signal | D9 |
| LM35 output | A0 |

Timer0 remains Arduino timekeeping. The custom driver owns Timer1 and drives
D9/OC1A at nominal 50 Hz. ADC is asynchronous. Short ultrasonic trigger delays
and formatting still run synchronously.

## Host protocol

```text
[02][CMD][DATA][CMD XOR DATA][03]
```

SET_MODE=01 (DATA 0..4), GET_STATUS=03, RESET=FF. SET_SPEED=02 is unsupported
and counted as rejected; no speed-controlled motor exists in this baseline.
RESET is a logical recovery request, not an MCU reset. All frames are five bytes.

```json
{"state":1,"dist":34.3,"temp":25.4,"alarm":false,"profile":0,"rx_errors":0,"tx_dropped":0,"rejected":0,"reset_flags":0}
```

Unavailable distance or temperature is -1.0. Original field names and binary
framing remain; hosts must allow the added diagnostic fields. Startup emits
`ArduCore v0.8 READY`. See the protocol document for recovery and overload rules.

## Build and test

Pinned build dependencies: Arduino CLI 1.5.1 and AVR Core 1.8.6. No Servo library.

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr@1.8.6
tools/build_firmware.sh full
tests/native/run.sh
python3 -m pip install -r tools/host/requirements.txt
python3 -m unittest discover -s tests/host -v
python3 tools/host/arducore_host.py --demo
```

Native tests require a C++11 g++ compiler and include undefined-behavior checks.
They test protocol framing, state/fault behavior, sensor expiry, timer wrap,
queue behavior, and firmware/UART integration using simulated peripherals.
GitHub Actions runs native tests and the pinned Uno build. A local pass does
not establish remote CI status or electrical behavior.

## Remaining boundaries

A floating LM35 input may produce plausible readings; software cannot reliably
prove that it is disconnected. AVcc, analog accuracy, noise and servo pulse
calibration require measurement. Bootloaders can clear MCUSR before the sketch,
so reset_flags is best-effort and zero does not prove a clean reset. A watchdog
reset will not always be identifiable for FAULT entry through such bootloaders.

Timer1 PWM uses configurable 1000..2000 us defaults, replacing the library's
544..2400 us default range. Logical angles are not calibrated physical angles.
STM32 and additional devices remain future work. See the [roadmap](docs/roadmap.md).
No license has been selected.

## Work with limited cables

The default full build requires both sensors. Separate profiles allow one
component at a time: `uart`, `distance`, `temperature`, `buzzer`, `servo`.
Run `tools/build_firmware.sh <profile>` to compile without uploading. Every JSON
line reports profile=0..5. Disabled sensors remain -1.0 and only the selected
profile's sensors participate in fault/alarm decisions. Full's checks remain.

See [staged hardware testing](docs/bench-testing.md) for wiring and expected
observations, and the [host tool guide](docs/host-tool.md) for commands and logs.
All hardware steps are deferred; the supplied software tests use fake peripherals
and an in-process serial loopback only.

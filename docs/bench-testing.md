# Staged hardware test guide (not executed)

The v0.8 software work does not require a connected board. All steps below are
for a later hardware session. Compilation alone never uploads firmware.

## Profiles for limited wiring

| ID | Build name | Connect for its later test | Expected inputs | Enabled outputs |
| --- | --- | --- | --- | --- |
| 0 | full | All baseline components | Distance and temperature | D7 buzzer, D9 servo |
| 1 | uart | USB only | None | None |
| 2 | distance | USB + HC-SR04 | Distance only | None |
| 3 | temperature | USB + LM35 | Temperature only | None |
| 4 | buzzer | USB + active buzzer | None | D7 only |
| 5 | servo | USB + servo | None | D9/OC1A only |

Inactive sensors stay unavailable (-1.0), not simulated healthy values. The
state machine checks only the sensors required by the compiled profile. Full
is the default and always requires both sensors. There is no UART command to
turn sensor checks off. profile in every telemetry line identifies the image.
Disabled components are not configured or driven by application code; normal
Arduino startup/bootloader behavior still applies.

## Software-only preparation

From the repository root:

```sh
arduino-cli core install arduino:avr@1.8.6
tools/build_firmware.sh full
tools/build_firmware.sh uart
tools/build_firmware.sh distance
tools/build_firmware.sh temperature
tools/build_firmware.sh buzzer
tools/build_firmware.sh servo
python3 tools/host/arducore_host.py --demo
```

Builds accept extra Arduino CLI options after the profile, such as
`--config-file /path/to/arduino-cli.yaml` or `--build-path /tmp/arducore-uart`.
No Servo library is needed. Direct CLI builds without profile flags are full.
All translation units must use the same ARDUCORE_PROFILE flag; use the helper.

## Later upload and connection

Disconnect power before rearranging connections. Verify each module's actual
pin labels/pinout and power requirements; LM35 package orientation must not be
inferred from the software. Maintain a common ground for powered components.

Uploading is a separate, deliberate later operation. For example, after
identifying the actual serial device and choosing the uart profile:

```sh
tools/build_firmware.sh uart --build-path /tmp/arducore-uart
arduino-cli upload --fqbn arduino:avr:uno --port /dev/ttyACM0 --input-dir /tmp/arducore-uart
```

The port above is an example, not an auto-selected device. Rebuild/upload the
chosen profile for each subsequent component. Reuse the same cables between
tests instead of connecting all sensors at once.

Start one persistent console to avoid reopening the port for every command:

```sh
python3 tools/host/arducore_host.py --port /dev/ttyACM0 --log session.jsonl console
```

Then enter `status`, `mode alarm`, `mode idle`, `mode auto`, `reset`, or `quit`.
Opening a Uno serial port may cause a hardware reset through DTR; the host waits
two seconds by default. Keeping one console connection avoids repeated opens.
`reset` itself is a logical recovery command. A sent event is not a device ACK;
observe subsequent telemetry to check the resulting state.

## Test sequence and expected observations

1. UART only: no external signal wiring. Confirm profile=1, state=AUTO, both
   readings=-1.0, periodic JSON, and mode commands without sensor FAULT. No
   buzzer/servo output is enabled. Log traffic and malformed input separately.
2. Distance only: connect HC-SR04 VCC, GND, TRIG=D4, ECHO=D6 using four signal/
   power connections. Confirm profile=2 and plausible cm readings. A target below
   20 cm should enter ALARM; >=25 cm clears it. No physical actuator is driven.
   An unavailable echo after startup should latch FAULT. Restore readings, wait
   at least 500 ms of continuous validity, then request reset/auto.
3. Temperature only: connect LM35 supply, ground and OUT=A0 using its verified
   pinout. Confirm profile=3 and compare temperature against a reference. Above
   35 C enters ALARM; <=33 C clears it. No actuator output is driven. A zero or
   implausible input faults, but an unplugged floating input may look plausible.
   Do not use the absence of FAULT as proof of a healthy electrical connection.
4. Buzzer only: connect the existing active buzzer circuit on D7 with its ground
   and any required module supply. Confirm profile=4. `mode alarm` enables D7;
   `mode idle` disables it. No distance/temperature inputs are required.
5. Servo only: connect servo signal D9, suitable supply and common ground.
   Confirm profile=5. The default command range is 1000..2000 us at nominal
   50 Hz. Logical 0/180 are pulse endpoints, not measured mechanical angles.
   Start with mechanical load detached; verify pulse waveform and usable travel
   before testing endpoint motion. `mode alarm` selects the upper endpoint;
   `mode idle` selects the lower endpoint. Power/current and mechanics remain
   part of this later test, not proven by a successful build.
6. Full system last: upload full and confirm profile=0. Both inputs are required.
   Test distance and heat alarms, output movement, sensor loss, fault recovery,
   simultaneous UART traffic and watchdog expiry. Shared power/noise behavior
   cannot be established by the individual component tests.

Individual tests allow progress with limited cables. A complete integrated
hardware validation remains pending until all required connections are possible.

## Servo calibration build

Default bounds are intentionally narrower than the old Servo library's
544..2400 us range. They are not a calibration of the actual SG90. Build-time
bounds may be adjusted after measurements:

```sh
ARDUCORE_SERVO_MIN_US=1100 ARDUCORE_SERVO_MAX_US=1900 tools/build_firmware.sh servo
```

The compiler enforces ordered limits within 500..2500 us; that accepted software
range is not a claim that every such pulse is suitable for the real mechanism.
No automatic sweep or actuator command runs on the host without user action.

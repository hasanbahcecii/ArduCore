# v0.7 software validation

Date: 2026-11-08. No physical hardware test or firmware upload was performed.
Historical v0.6 evidence is retained separately in baseline-validation.md.

## Local Uno builds

| Toolchain | Flash | Static SRAM | Result |
| --- | --- | --- | --- |
| CLI 1.5.1, AVR Core 1.8.6, Servo 1.2.2 | 8498 / 32256 bytes | 796 / 2048 bytes | Passed |
| CLI 1.5.1, AVR Core 1.8.8, Servo 1.3.0 | 8498 / 32256 bytes | 796 / 2048 bytes | Passed |

The first row matches the workflow's pinned dependencies. Those packages were
downloaded to an isolated workspace and checked against SHA-256 values from the
Arduino package/library indices. The user's installed toolchain was unchanged.
Builds use arduino:avr:uno and --warnings all. Four unused-parameter warnings
originate in Arduino core new.cpp on a clean core build; application code emits
no warnings. Static SRAM leaves 1252 bytes for stack/runtime use, but no measured
stack bound or interrupt timing guarantee is claimed.

ELF inspection confirms separate echo, Servo, Timer0, USART RX and USART UDRE
vectors, no linked HardwareSerial implementation, and the watchdog .init3 hook
before data/BSS initialization. This checks generated structure, not hardware
watchdog expiry or bootloader behavior.

## Native tests

Run `tests/native/run.sh` with g++. Each suite is built with C++11, Wall, Wextra,
Werror, pedantic and undefined-behavior sanitization with immediate failure.
All five suites passed:

1. Frame parser: all 65536 CMD/DATA combinations, delimiter payloads, malformed
   frames, ETX/checksum gating, recovery, timeout and millisecond counter wrap.
2. Echo/distance: ordered and duplicate edges, missing and late edges, one-time
   consumption, completion age, delayed-result rejection, invalid pulse values,
   reading expiry, recovery, microsecond and millisecond counter wrap.
3. Core/temperature: startup grace, hot/cold alarm transitions, distance and
   temperature hysteresis, forced alarm, neutral modes, fault latching, continuous
   recovery interval, rejected modes, wrap, fractional average and validity bounds.
4. Queue: 200000 deterministic push/pop/clear operations compared with std::deque,
   plus exact capacity/overflow behavior for the non-power-of-two TX queue size.
5. Firmware/UART integration: compile the actual sketch and UART driver against
   fake peripherals; exercise startup, sensing, outputs, alarm, fault recovery,
   RX timestamps, queue overflow, USART error recovery, RESET queue discard,
   all-or-nothing TX, telemetry sentinels, maximum diagnostics and saturation.

Fake peripherals do not model interrupt preemption, ADC conversion timing,
physical UART baud or servo pulses. Watchdog instructions are checked by the
AVR build/ELF, not executed in the native fixture. Native tests are not a
substitute for electrical and board tests.

## CI and repository checks

The workflow runs the native runner before installing pinned dependencies and
cross-compiling Uno. Remote CI has not been triggered or verified for these
unpublished changes. Repository whitespace checks and ASCII text checks pass.
No generated firmware, downloaded dependency, credentials or simulator output
is included in the source tree. No push was performed.

## Remaining validation boundaries

- Real sensor accuracy, false echoes, disconnection detection and AVcc calibration.
- Servo endpoints, power integrity, startup transients and actuator mechanics.
- Real-time interrupt stress, queue loss recovery and watchdog expiry on a board.
- MCUSR visibility through the actual bootloader. The bundled Optiboot source
  clears MCUSR before application entry; reset_flags may therefore be zero and
  watchdog-based FAULT entry may be unavailable. Reset recovery is not certified.
- Stack high-water use under simultaneous formatting and interrupts.

Register-level servo PWM and asynchronous ADC are explicitly future driver work,
not implemented parts of this reliability release. Protocol XOR cannot prevent
accidental valid frames or authenticate commands.

# v0.8 software validation

Date: 2026-11-08. No physical serial device was opened. No hardware test or
firmware upload was performed. v0.7 and v0.6 evidence is preserved separately
in v0.7-validation.md and baseline-validation.md; those are historical records.

## Uno builds: all six profiles

CLI 1.5.1, AVR Core 1.8.6, arduino:avr:uno, --warnings all. No Servo library.

| Profile | ID | Flash / 32256 bytes | Static SRAM / 2048 bytes |
| --- | --- | --- | --- |
| full | 0 | 8004 | 782 |
| uart | 1 | 5792 | 759 |
| distance | 2 | 7258 | 763 |
| temperature | 3 | 6402 | 776 |
| buzzer | 4 | 6110 | 759 |
| servo | 5 | 6074 | 761 |

All builds passed. Clean core builds emit four unused-parameter warnings in
Arduino core new.cpp; application code emits no warnings. Full leaves 1266
bytes for runtime/stack, which is not a measured stack bound. Full v0.7 used
8498 bytes flash and 796 bytes static RAM with the same pinned AVR core.

ELF symbols confirm no HardwareSerial, analogRead or Servo implementation.
USART RX/UDRE remain owned by the custom driver. ADC_vect is present only in
full/temperature and PCINT2 only in full/distance. No Timer1 compare ISR is
linked; the output is hardware PWM. The previous watchdog initialization
structure is retained. ELF inspection does not prove electrical behavior.

## Native firmware tests

Run `tests/native/run.sh`. C++11 with Wall/Wextra/Werror/pedantic and undefined
behavior sanitizer (immediate failure) passes six suites plus five extra
profile integration builds:

- Existing parser tests, including all 65536 CMD/DATA combinations.
- Existing queue reference model (200000 operations), echo/freshness/wrap tests,
  and system/fault/temperature tests.
- ADC driver: configuration, first-result discard, four-sample sums, no early
  publication, no overwrite of unread results, completion timestamps, full-scale
  sums and single-consumption behavior, using simulated registers.
- Timer1 driver: mode/prescaler/TOP, startup output, all 256 byte-valued angle
  requests, clamping, ordered pulse endpoints and register writes.
- The real sketch, ADC, PWM and UART driver code runs with fake peripherals in
  full and each of the five isolated profiles. Tests check correct required
  inputs, output masks, profile telemetry, unavailable disabled inputs, full
  fault recovery and existing UART loss/reset behavior.

A separate calibrated native build with 1100..1900 us endpoints also passes.
Compile-only negative checks reject profile=6, pulses below 500 or above 2500
us, and reversed pulse limits.
The fake environment does not simulate PWM edges, ADC analog sampling, AVR
interrupt preemption or watchdog expiry. It deliberately provides no Servo
library or analogRead stub, preventing accidental dependency reintroduction.

## Python host tests

`python3 -m unittest discover -s tests/host -v` passes 11 tests with pyserial 3.5:

- All 65536 command/data frame encodings and invalid byte inputs.
- Fragmented/multiple lines, banner, malformed JSON/nonfinite readings, legacy
  telemetry, explicit profile validation and bounded oversized-line recovery.
- Demo mode and append-only timestamped logs.
- Argument validation, partial writes and disconnected serial transport errors.
- Finite receive deadlines and persistent-console command parsing/quit.
- CLI command encoding and explicit sent-without-acknowledgement reporting.
- pyserial loop:// round trips entirely in process; no physical device involved.

Hardware access, auto-port selection, upload and real actuator sweeps are not
part of these tests. The host demo generates clearly labeled synthetic data.

## CI and remaining boundaries

Workflow now runs native and Python tests plus a six-profile pinned Uno build
matrix. It no longer installs Servo. Remote CI for these unpublished changes
has not run. Repository text is ASCII and whitespace checks pass; generated
binaries, test caches and downloaded dependencies are not committed.

Later execute bench-testing.md: verify ADC reference/accuracy and sensor noise,
PWM timing/endpoints, serial DTR reset behavior, power/mechanics, actual UART
interrupt stress and watchdog/bootloader interactions. A floating LM35 can
still produce plausible data. The watchdog reset flag remains bootloader-
dependent. Individual tests with reused cables do not replace full integration.

## Additional headless instruction and host validation

The production v0.8 ELF (unchanged firmware) also passes six simavr 1.8 tests:
ADC/echo acquisition, malformed frame recovery, USART framing-error recovery,
UART mode changes with stable PWM pin measurements, sensor FAULT/recovery, and
watchdog reset after a simulator-only PC lockup. Simulator source is pinned to
f44723e8c42431136d5b4de81f789ded56d7e8fa. Tests load no Uno bootloader.

Measured stable servo pulses are within 2 us of nominal 1000/2000 us, and
periods within 2 us of 20000 us in simulated pin events. A targeted watchdog
probe reset approximately 2.048 simulated seconds after the injected lockup.
The bridge maintains monotonic elapsed time across simavr's reset-local cycle
counter and excludes cross-reset pin intervals from timing comparisons.
These are model results, not oscilloscope or board measurements.

One end-to-end test passes with the actual Python CLI, pyserial and a Linux
pseudo-terminal connected to the loaded ELF. It covers commands, telemetry,
refused/accepted recovery and JSONL persistence. A partially flushed startup
banner is allowed only before the first complete telemetry line; malformed
output after synchronization fails the test.

Six bundle-integrity tests pass: valid package, outer/payload tampering,
unmanifested/unsafe members, missing profiles/artifacts, and dirty-source rules.
Development package builds for all six profiles were verified against a complete
manifest and archive checksum. Final bundles identify their committed source.
See simulation.md and release.md for repeatable commands and limitations.

## Accelerated one-hour stress result

Completed 60 simulated minutes plus startup (3601.299973 simulated seconds)
in 632.514 wall-clock seconds, seed 42517. All 1620 checks passed and 7742
telemetry lines were decoded by the actual host parser. There was one initial
boot and no unexpected reset; paced UART RX errors remained zero.

The status flood deliberately skipped 2220 whole telemetry messages under TX
backpressure, with no partial JSON delivered. The 60 rejected recovery requests
were expected while the echo sensor was unavailable. Final state was AUTO with
valid readings. 180065 PWM pulses and 72025 ADC trigger events were captured.

The machine-readable result and input hashes are in
[evidence/soak-60m.json](evidence/soak-60m.json). This is an accelerated model test,
not a physical or one-hour wall-clock burn-in. No GPU or physical port was used.

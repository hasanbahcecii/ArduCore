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

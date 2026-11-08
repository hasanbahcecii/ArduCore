# Development roadmap

## v0.6 baseline: preserved history

The original single-sketch baseline and cross-build evidence are described in
baseline-validation.md. This historical evidence does not validate later code.

## v0.7 software reliability: implemented

- Validate complete frames, recover with a sliding window and RX timestamps.
- Register-level USART0 RX/TX interrupts, bounded queues and explicit loss policy.
- Atomic echo consumption, ordered edges, timeout and stale-data handling.
- Temperature plausibility/freshness, alarm hysteresis and deterministic outputs.
- Latched FAULT, health-gated recovery, logical reset semantics and watchdog.
- Portable core, native unit/integration tests, pinned Uno CI and updated docs.

Local validation is documented in validation.md. No hardware test was performed.
This does not certify sensor accuracy, actuator motion or watchdog/bootloader
interaction. A floating LM35 can still produce plausible values.

## v0.8 isolated bench preparation: implemented in software

- Six compile-time profiles with full-system checks retained by default.
- Python console, status/mode/reset commands, bounded telemetry decoder and JSONL logs.
- ADC0 asynchronous burst acquisition; no analogRead dependency.
- Timer1 OC1A hardware PWM; no Servo dependency, configurable pulse bounds.
- Driver/register tests, all-profile integration tests, host tests and CI matrix.
- Sequential hardware guide to reuse limited wiring, followed by full integration.

## Hardware-free validation infrastructure: implemented

- Production ELF instruction/peripheral tests under pinned headless simavr 1.8.
- Real host CLI via Linux virtual serial port to simulated firmware, with logs.
- Seeded accelerated stress scenarios and machine-readable summaries.
- All-profile source/firmware bundles with source commit and SHA-256 verification.
- CPU-only CI simulation and manual downloadable bundle workflow.

See simulation.md and release.md. These add verification around unchanged v0.8
firmware; the banner remains v0.8. Real hardware coverage remains separate.

## All-profile coverage and bench assistance: implemented

- Actual ELF scenarios across all six profiles with required-input/output checks.
- Instruction-boundary stack observation and unused-SRAM watermark, with a
  512-byte observed-gap CI budget (not an exhaustive upper-bound proof).
- Profile-aware bench helper, explicit output sequencing, JSON/JSONL reports.
- All-profile simulated helper tests and real pyserial through virtual ports.

See memory.md and bench-assistant.md. No physical device was accessed.

## Next: deferred hardware validation

Execute docs/bench-testing.md only in a later hardware session. Confirm PWM
waveform/endpoints, ADC reference/accuracy, sensor-loss behavior, integrated power
and watchdog/bootloader recovery. No connected device was accessed for v0.8.
Separate tests do not replace a final all-components system test.

## Future portability and extensions

Select an STM32 board before assigning pins/timers and implementing HAL adapters.
Retain portable state/protocol tests and document any wire compatibility change.
Joystick/IR manual commands, LCD, stepper, LDR and a host tool are optional future
features; no placeholder implementations or implied hardware support are added.

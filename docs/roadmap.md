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

## Optional driver development: separate scope

1. Replace Servo with Timer1 PWM after confirming pulse limits and actual servo
   endpoints. Preserve Timer0 and check timer ownership. Physical validation is
   needed before calling servo operation verified.
2. Replace synchronous analogRead with asynchronous ADC sampling. Define AVcc
   calibration and measurement/filtering policy. Determine whether disconnected
   LM35 detection needs additional hardware.
3. Validate watchdog expiry, startup outputs and reset cause reporting using the
   actual board/bootloader. Select a reliable reset-cause mechanism if required.

These are peripheral architecture changes, not completed features of v0.7.

## Future portability and extensions

Select an STM32 board before assigning pins/timers and implementing HAL adapters.
Retain portable state/protocol tests and document any wire compatibility change.
Joystick/IR manual commands, LCD, stepper, LDR and a host tool are optional future
features; no placeholder implementations or implied hardware support are added.

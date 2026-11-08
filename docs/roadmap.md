# Development roadmap

## v0.6 - Baseline

The supplied firmware is imported with ASCII-only comment normalization. Uno
cross-compilation passed using pinned dependencies, and a GitHub Actions build
is configured. See validation.md for evidence and limits. Hardware validation
and native unit tests remain pending.

The earlier component-by-component phase list is a set of ideas, not evidence
of implemented or verified features.

## v0.7 - Register-level USART

Replace HardwareSerial with register configuration, RX interrupt handling,
TX buffering, and interrupt-driven transmission. Define and test overflow
behavior while preserving the five-byte command protocol and existing output
format. Avoid duplicate USART ISR ownership.

## v0.8 - Timer1 servo PWM

Remove Servo, confirm the D9/OC1A mapping against the datasheet and board
schematic, and generate 50 Hz hardware PWM. Define safe and calibrated pulse
widths. Check timer ownership and physically validate the SG90.

## v0.9 - Interrupt-driven ADC

Configure ADC registers and asynchronous interrupt-driven sampling.
Validate measurements, reference assumptions, and disconnected or implausible
LM35 behavior. Define fault thresholds and hysteresis with testable rules.

## v1.0 - Watchdog and FAULT

Configure the AVR watchdog, inspect reset cause, define safe actuator states,
and implement meaningful FAULT entry and recovery. Validate alarm transitions,
ultrasonic timeout and stale-data behavior, and reset semantics.

## v1.1 - Portable core and native tests

Separate hardware-independent state and protocol logic from drivers.
Add native tests for framing, malformed-input recovery, overflow, scheduling,
and state transitions. Retain AVR cross-builds and separate hardware checks.

## Future - STM32 migration

Select a board before assigning peripherals. Port hardware interfaces to
STM32 timers, USART, ADC, and watchdog facilities. Consider DMA where justified.
Retain protocol compatibility and reusable state logic. No STM32 hardware
verification is currently possible.

## Optional extensions

Evaluate joystick/IR manual control, stepper motion, LDR input, LCD output,
and a Python host tool after the baseline is reproducible. Confirm the LCD
interface and all wiring before defining pin assignments. Do not claim these
extensions are current functionality.

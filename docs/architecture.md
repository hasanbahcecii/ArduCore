# Architecture

## Reviewed baseline

This document describes the uploaded v0.6 sketch now included under
firmware/arducore. Only comment decorations were converted to ASCII; executable
source is unchanged. No new driver architecture has been implemented.

setup() starts HardwareSerial at 9600 baud, configures GPIO, attaches Servo,
enables the echo pin-change interrupt, and emits a startup banner.
The initial state is AUTO.

loop() drains HardwareSerial into a software ring buffer, parses commands,
triggers the ultrasonic sensor every 100 ms, consumes completed echo
measurements, samples temperature every 200 ms, runs the state machine,
and emits telemetry every 500 ms. Scheduling uses unsigned millis differences.

The pin-change ISR timestamps echo edges with micros(). Main-loop code consumes
echoDuration and echoReady. Shared 32-bit values on this 8-bit MCU need atomic
access; volatile alone does not make a multi-byte read atomic.

Temperature conversion averages four synchronous analogRead() results using
integer division before voltage conversion. It assumes 5000 mV reference and
10 mV/C. The actual reference and sensor validity are not checked.

## Resource ownership

- Arduino core provides millis(), micros(), GPIO, ADC, and HardwareSerial.
- Arduino timekeeping conventionally uses Timer0 on this target.
- Servo uses Timer1 on this target.
- HardwareSerial manages USART interrupts.
- The sketch defines PCINT2_vect for ultrasonic echo edges.

These are framework-level ownership observations. Exact register and package
pin mappings require confirmation against the ATmega328P datasheet and selected
core/library versions before register-level changes.

## Technical debt

- A disconnected LM35 input can float and produce false temperature alarms.
- No sensor plausibility checks or calibrated reference handling are present.
- AUTO enters ALARM on distance or temperature, but ALARM exits on distance
  alone. No hysteresis exists.
- IDLE changes outputs without clearing alarmState.
- MANUAL and FAULT handlers are empty and can retain previous outputs.
- Echo values need atomic consumption and race analysis.
- There is no echo timeout or stale-distance invalidation.
- The ring buffer silently discards new bytes when full.
- The parser dispatches before ETX validation and lacks timeout recovery.
- Serial output and ADC sampling can block.
- Integrated servo operation has not been hardware-verified here.

## Planned organization

After preserving the baseline, extract portable application and state logic
into src/core, peripheral drivers into src/drivers, and framing into
src/protocol. Add meaningful native tests under tests/native when portable
logic exists. No placeholder source modules are needed.

Each extraction must preserve documented baseline behavior or explicitly
describe and test the intended change. Native tests cannot verify electrical
behavior, interrupt timing, or actuator operation.

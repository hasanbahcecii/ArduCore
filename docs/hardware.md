# Hardware

## Baseline wiring

| Component | Arduino pin | Use in uploaded sketch |
| --- | --- | --- |
| HC-SR04 TRIG | D4 | Output; short trigger pulse |
| HC-SR04 ECHO | D6 | Input; pin-change edge timing |
| Active buzzer | D7 | Digital on/off |
| SG90 servo | D9 | Servo library output |
| LM35 | A0 | ADC temperature input |

The sketch uses PIND/PD6, PCIE2, PCMSK2, and PCINT22 for the echo path.
The proposed register mapping D6 -> PD6/PCINT22 and future D9 -> PB1/OC1A
requires independent ATmega328P datasheet and Uno schematic confirmation.
No datasheet verification was performed during this documentation update.

D5 is not documented as a Timer1 input-capture input. Do not copy the earlier
draft's proposed D5 input-capture assignment into a hardware implementation
without checking the actual ICP1 pin mapping.

## Timers and interrupts

Servo currently owns Timer1. Future direct Timer1 PWM requires removing that
dependency and checking all timer users. HardwareSerial owns USART interrupt
handlers. Arduino timing APIs conventionally depend on Timer0.

The buzzer is active and driven digitally; no timer-driven tone or PWM is
implemented. D9 carries the servo signal, not a DC motor output.

## Additional hardware

DHT11, a ULN2003-driven stepper, joystick, potentiometer, LDR, IR receiver,
buttons, LEDs, and an LCD are available candidates. Their integration and
wiring are not verified. The LCD interface is unknown; do not assume I2C.
PIR and DC motor features from the earlier draft are not in the baseline.

## Validation status

No Arduino board is connected to this environment. Electrical connections,
power integrity, sensor accuracy, timing, and actuator movement have not been
tested here. Integrated servo behavior remains an explicit validation task.

# Hardware and peripheral ownership

Target: Arduino Uno R3, ATmega328P at 16 MHz. No attached hardware was accessed,
no firmware was uploaded, and no electrical or actuator tests were performed.

| Component | Uno pin | Current implementation |
| --- | --- | --- |
| HC-SR04 TRIG | D4 | Digital output, 2 us low + 10 us high trigger |
| HC-SR04 ECHO | D6 / PD6 / PCINT22 | PCINT2 edge timing |
| Active buzzer | D7 | Digital on/off; no tone timer |
| SG90 servo | D9 | Custom Timer1 OC1A PWM; logical 0/180 commands |
| LM35 | A0 | Interrupt-driven four-sample burst, nominal AVcc=5 V |

Ownership: Arduino Timer0 for timekeeping; custom Timer1 PWM; custom USART0 RX/UDRE
interrupts for UART; PCINT2 for echo; watchdog reset mode for loop supervision.
HardwareSerial must not be added alongside the custom UART driver.

D9 maps to PB1/OC1A on Uno. Timer1 is configured for mode 14, /8 and
TOP=39999 (nominal 50 Hz); no Servo library or Timer1 ISR is used. D5 must not be assumed to be the Timer1 input-capture pin. ADC0 uses AVcc, /128 (125 kHz) and ADC_vect; its first conversion is
discarded before a four-reading sum. Current register
identifiers are checked against the ATmega328/P datasheet and Arduino Uno pin
variant mapping; this does not verify physical wiring.

Sources:
- [ATmega328/P datasheet](https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf)
- [Arduino standard AVR pin variant](https://github.com/arduino/ArduinoCore-avr/blob/1.8.6/variants/standard/pins_arduino.h)
- [avr-libc watchdog initialization](https://avrdudes.github.io/avr-libc/avr-libc-user-manual/group__avr__watchdog.html)

FAULT commands buzzer on and servo 0 degrees. IDLE/MANUAL/AUTO command neutral
outputs; ALARM commands buzzer on and servo 180 degrees. Mechanical meaning,
servo endpoints, power supply, startup transients and SG90 integrated behavior
remain unverified. Servo commands are not proof of position feedback.

LM35 plausibility accepts a four-sample sum from 1 through 1227 (approximately
above 0 through 150 C). Grounded/zero and above-range values are invalid. Actual
0 C operation is outside this application policy. A disconnected analog input
can float into the accepted range; a dedicated detection circuit or biasing
and calibration policy may be necessary for reliable disconnect detection.

HC-SR04 absence/no echo becomes unavailable data. An absent echo may also be
caused by target geometry; FAULT indicates unavailable measurement, not a
proven electrical disconnection.

DHT11, stepper/ULN2003, joystick, potentiometer, LDR, IR, buttons, LEDs and LCD
are possible future extensions. Their wiring is not integrated or verified;
the LCD interface is unknown.

Default servo pulses are 1000..2000 us and can be changed at compile time within
500..2500 us; neither the defaults nor accepted bounds are physical calibration.
Changing from v0.7's Servo library endpoints is intentional. See bench-testing.md
for isolated profiles and the future measurement/connection sequence.

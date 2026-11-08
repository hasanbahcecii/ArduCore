#include "ServoPwmAvr.h"
#include "../../BuildConfig.h"
#if ARDUCORE_SERVO
#include <Arduino.h>
#include <util/atomic.h>
#if !defined(__AVR_ATmega328P__) || F_CPU != 16000000UL
#error Servo driver requires ATmega328P at 16 MHz
#endif
namespace servo_pwm {
void begin() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    TCCR1A = TCCR1B = 0;
    TIMSK1 = 0; // This driver exclusively owns Timer1; no Timer1 ISR.
    PORTB &= ~_BV(PB1);
    DDRB |= _BV(DDB1); // D9 = PB1/OC1A.
    TCNT1 = 0;
    ICR1 = TOP; // Fixed TOP; never changed while running.
    OCR1A = ticksForDegrees(0);
    TIFR1 = _BV(ICF1) | _BV(OCF1B) | _BV(OCF1A) | _BV(TOV1);
    TCCR1A = _BV(COM1A1) | _BV(WGM11); // Non-inverting OC1A.
    TCCR1B = _BV(WGM13) | _BV(WGM12) | _BV(CS11); // Fast PWM 14, /8.
  }
}
void writeDegrees(uint8_t degrees) {
  const uint16_t ticks = ticksForDegrees(degrees);
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { OCR1A = ticks; }
}
}
#endif

#include "AdcAvr.h"
#include "../../BuildConfig.h"
#if ARDUCORE_TEMPERATURE
#include <Arduino.h>
#include <avr/interrupt.h>
#include <util/atomic.h>
#if !defined(__AVR_ATmega328P__) || F_CPU != 16000000UL
#error ADC driver requires ATmega328P at 16 MHz
#endif
namespace {
volatile bool busy = false, ready = false, discardFirst = true;
volatile uint8_t remaining = 0;
volatile uint16_t accumulator = 0, result = 0;
volatile uint32_t completedAt = 0;
const uint8_t control = _BV(ADEN) | _BV(ADIE) | _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0);
}
ISR(ADC_vect) {
  const uint16_t raw = ADC; // AVR reads ADCL then ADCH as required.
  if (!busy) return;
  if (discardFirst) discardFirst = false;
  else { accumulator += raw; --remaining; }
  if (remaining) ADCSRA = control | _BV(ADSC);
  else {
    result = accumulator;
    completedAt = millis();
    ready = true;
    busy = false;
  }
}
namespace adc {
void begin() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    PRR &= ~_BV(PRADC);
    ADCSRA = 0;
    ADMUX = _BV(REFS0); // AVcc reference, right-adjusted ADC0 (A0).
    ADCSRB = 0; // Software-started single conversions; no auto-trigger.
    DIDR0 |= _BV(ADC0D);
    busy = ready = false;
    discardFirst = true;
    ADCSRA = control | _BV(ADIF); // Clear any pending interrupt flag.
  }
}
bool request() {
  bool started = false;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    // Do not overwrite a completed sample that the main loop has not consumed.
    if (!busy && !ready) {
      accumulator = 0;
      remaining = 4;
      busy = true;
      ADCSRA = control | _BV(ADIF) | _BV(ADSC);
      started = true;
    }
  }
  return started;
}
bool take(Sample &sample) {
  bool available = false;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    if (ready) {
      sample.sum = result;
      sample.time = completedAt;
      ready = false;
      available = true;
    }
  }
  return available;
}
}
#endif

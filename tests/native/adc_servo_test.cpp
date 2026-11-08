#include <Arduino.h>
#include <assert.h>
#include <stdio.h>
uint8_t PRR = 255, ADCSRA, ADCSRB, ADMUX, DIDR0;
uint16_t ADC;
uint8_t TCCR1A, TCCR1B, TIMSK1 = 255, PORTB = 255, DDRB, TIFR1;
uint16_t TCNT1, ICR1, OCR1A;
uint32_t fakeMicros = 0;
#include "../../firmware/arducore/src/drivers/AdcAvr.cpp"
#include "../../firmware/arducore/src/drivers/ServoPwmAvr.cpp"
static void conversion(uint16_t raw) {
  assert(ADCSRA & _BV(ADSC));
  ADC = raw;
  fakeMicros += 104;
  ADCSRA &= ~_BV(ADSC);
  ADC_vect();
}
int main() {
  adc::begin();
  assert(!(PRR & _BV(PRADC)) && ADMUX == _BV(REFS0));
  assert(ADCSRB == 0 && (DIDR0 & _BV(ADC0D)));
  assert((ADCSRA & 7) == 7); // /128 => 125 kHz at 16 MHz.
  adc::Sample sample;
  assert(!adc::take(sample));
  assert(adc::request() && !adc::request());
  conversion(1023); // First conversion is intentionally discarded.
  assert(!adc::take(sample));
  conversion(50); conversion(51); conversion(52);
  assert(!adc::take(sample));
  conversion(53);
  assert(!(ADCSRA & _BV(ADSC)));
  assert(!adc::request()); // Unread completed result cannot be overwritten.
  fakeMicros += 100000;
  assert(adc::take(sample) && sample.sum == 206 && sample.time == 0);
  assert(!adc::take(sample));
  assert(adc::request());
  conversion(10); conversion(20); conversion(30); conversion(40);
  assert(adc::take(sample) && sample.sum == 100 && sample.time == 100);
  adc::begin();
  assert(adc::request());
  conversion(1023); conversion(1023); conversion(1023); conversion(1023); conversion(1023);
  assert(adc::take(sample) && sample.sum == 4092);

  servo_pwm::begin();
  assert(ICR1 == 39999 && TCNT1 == 0);
  assert(OCR1A == 2 * ARDUCORE_SERVO_MIN_US && TIMSK1 == 0);
  assert((DDRB & _BV(DDB1)) && !(PORTB & _BV(PB1)));
  assert(TCCR1A == (_BV(COM1A1) | _BV(WGM11)));
  assert(TCCR1B == (_BV(WGM13) | _BV(WGM12) | _BV(CS11)));
  uint16_t previous = 0;
  for (unsigned i = 0; i < 256; ++i) {
    servo_pwm::writeDegrees(i);
    assert(OCR1A >= previous && OCR1A < ICR1);
    assert(OCR1A >= 2 * ARDUCORE_SERVO_MIN_US && OCR1A <= 2 * ARDUCORE_SERVO_MAX_US);
    previous = OCR1A;
  }
  assert(OCR1A == 2 * ARDUCORE_SERVO_MAX_US);
  puts("ADC burst and Timer1 configuration tests passed (simulated registers)");
}

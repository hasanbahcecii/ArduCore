#ifndef TEST_ARDUINO_H
#define TEST_ARDUINO_H
#include <stdint.h>
#include <stdlib.h>
#define __AVR_ATmega328P__ 1
#define F_CPU 16000000UL
#define _BV(x) (1U << (x))
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define A0 14
#define PD6 6
#define PCIF2 2
#define PCINT22 6
#define PCIE2 2
#define WDRF 3
#define FE0 4
#define DOR0 3
#define UPE0 2
#define UDRIE0 5
#define UCSZ01 2
#define UCSZ00 1
#define RXEN0 4
#define TXEN0 3
#define RXCIE0 7
extern uint8_t PIND, PCIFR, PCMSK2, PCICR;
extern uint8_t UCSR0A, UCSR0B, UCSR0C, UBRR0H, UBRR0L, UDR0;
extern uint32_t fakeMicros;
extern int adcValue, pins[20], watchdogServices, triggerCount;
inline uint32_t millis() { return fakeMicros / 1000; }
inline uint32_t micros() { return fakeMicros; }
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t pin, uint8_t value) {
  pins[pin] = value;
  if (pin == 4 && value) ++triggerCount;
}
inline void delayMicroseconds(uint16_t amount) { fakeMicros += amount; }

// Additional register symbols for compile-time driver fixtures.
#define ADEN 7
#define ADIE 3
#define ADPS2 2
#define ADPS1 1
#define ADPS0 0
#define ADSC 6
#define ADIF 4
#define PRADC 0
#define REFS0 6
#define ADC0D 0
#define PB1 1
#define DDB1 1
#define ICF1 5
#define OCF1B 2
#define OCF1A 1
#define TOV1 0
#define COM1A1 7
#define WGM11 1
#define WGM13 4
#define WGM12 3
#define CS11 1
extern uint8_t PRR, ADCSRA, ADCSRB, ADMUX, DIDR0;
extern uint16_t ADC;
extern uint8_t TCCR1A, TCCR1B, TIMSK1, PORTB, DDRB, TIFR1;
extern uint16_t TCNT1, ICR1, OCR1A;

#endif

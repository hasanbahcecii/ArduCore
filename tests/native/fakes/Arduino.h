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
extern int adcValue, pins[20], servoPosition, watchdogServices, triggerCount;
inline uint32_t millis() { return fakeMicros / 1000; }
inline uint32_t micros() { return fakeMicros; }
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t pin, uint8_t value) {
  pins[pin] = value;
  if (pin == 4 && value) ++triggerCount;
}
inline void delayMicroseconds(uint16_t amount) { fakeMicros += amount; }
inline int analogRead(uint8_t) { return adcValue; }
#endif

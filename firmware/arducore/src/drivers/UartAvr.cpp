#include "UartAvr.h"
#include "../core/ByteQueue.h"
#include <Arduino.h>
#include <avr/interrupt.h>
#include <util/atomic.h>
#if !defined(__AVR_ATmega328P__) || F_CPU != 16000000UL
#error ArduCore UART currently requires ATmega328P at 16 MHz
#endif
namespace {
ByteQueue<uart::Received, 64> rx;
ByteQueue<uint8_t, 192> tx;
volatile bool lost = false;
volatile uint16_t errorCount = 0;
void recordError() {
  lost = true;
  if (errorCount != UINT16_MAX) ++errorCount;
}
}
ISR(USART_RX_vect) {
  const uint8_t status = UCSR0A; // Read status before UDR0 (datasheet).
  const uint8_t byte = UDR0;
  if (status & (_BV(FE0) | _BV(DOR0) | _BV(UPE0))) { recordError(); return; }
  if (lost) return;
  const uart::Received item = {byte, millis()};
  if (!rx.push(item)) recordError();
}
ISR(USART_UDRE_vect) {
  uint8_t byte;
  if (tx.pop(byte)) UDR0 = byte;
  else UCSR0B &= ~_BV(UDRIE0);
}
namespace uart {
void begin() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    UCSR0B = 0;
    UCSR0A = 0; // Normal speed, 9600 baud: 16 MHz / (16 * 104).
    UBRR0H = 0;
    UBRR0L = 103;
    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00); // Asynchronous 8N1.
    UCSR0B = _BV(RXEN0) | _BV(TXEN0) | _BV(RXCIE0);
  }
}
bool read(Received &item) { return rx.pop(item); }
bool send(const char *data, size_t length) {
  if (length > tx.free()) return false;
  for (size_t i = 0; i < length; ++i) tx.push(static_cast<uint8_t>(data[i]));
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { UCSR0B |= _BV(UDRIE0); }
  return true;
}
bool recover() {
  bool result;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    result = lost;
    if (lost) { rx.clear(); lost = false; }
  }
  return result;
}
void discardRx() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { rx.clear(); lost = false; }
}
uint16_t errors() {
  uint16_t result;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { result = errorCount; }
  return result;
}
}

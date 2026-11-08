#ifndef ARDUCORE_UART_AVR_H
#define ARDUCORE_UART_AVR_H
#include <stdint.h>
#include <stddef.h>
namespace uart {
struct Received { uint8_t byte; uint32_t time; };
void begin();
bool read(Received &item);
bool send(const char *data, size_t length); // Whole message or nothing; no wait.
bool recover(); // Flush RX after loss/error, return true once per recovery.
void discardRx();
uint16_t errors();
}
#endif

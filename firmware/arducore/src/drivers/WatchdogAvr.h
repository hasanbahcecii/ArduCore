#ifndef ARDUCORE_WATCHDOG_AVR_H
#define ARDUCORE_WATCHDOG_AVR_H
#include <stdint.h>
extern uint8_t resetFlags;
void startWatchdog();
void serviceWatchdog();
#endif

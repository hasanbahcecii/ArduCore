#include "WatchdogAvr.h"
#include <avr/io.h>
#include <avr/wdt.h>
uint8_t resetFlags __attribute__((section(".noinit")));
// avr-libc early watchdog shutdown pattern. Bootloaders may clear MCUSR before
// reaching this hook, so an absent WDRF does not prove a clean hardware reset.
void earlyWatchdog() __attribute__((used, naked, section(".init3")));
void earlyWatchdog() {
  resetFlags = MCUSR;
  MCUSR = 0;
  wdt_disable();
}
void startWatchdog() { wdt_enable(WDTO_2S); }
void serviceWatchdog() { wdt_reset(); }

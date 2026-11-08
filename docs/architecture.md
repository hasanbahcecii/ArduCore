# Architecture: v0.7

## Boundaries

- firmware/arducore/arducore.ino: scheduling, wiring, commands, outputs and JSON.
- src/core/SystemCore.h: MCU-independent state, fault and temperature rules.
- src/core/ByteQueue.h: single-producer/single-consumer fixed-size queue.
- FrameParser.h: portable sliding-window frame decoder with timeout/reset.
- EchoCapture.h: echo state and distance freshness, portable timing logic.
- src/drivers/UartAvr.cpp: ATmega328P USART0 register and interrupt ownership.
- src/drivers/WatchdogAvr.cpp: early watchdog shutdown and loop watchdog service.

Paths above are relative to firmware/arducore except the sketch itself.

## Execution

setup configures neutral outputs, Servo, echo interrupts, UART and watchdog.
AUTO starts with a one-second sensor acquisition grace. Observable WDRF starts
in FAULT; reset flag visibility depends on the bootloader.

Each loop consumes echo data, triggers the next measurement every 100 ms,
samples temperature every 200 ms, refreshes health, processes at most 16 RX
bytes, reapplies state rules and outputs, and queues telemetry if due/requested.
Only then is the two-second watchdog fed. Time comparisons use unsigned
subtraction and support normal millis/micros rollover, assuming loop execution
continues within the corresponding counter period.

A distance result is consumed before rearming. EchoCapture accepts one ordered
edge pair completed within 30 ms of arming. Main-loop access to this object is
inside ATOMIC_RESTORESTATE. Consumption carries the elapsed completion age
into distance freshness (millisecond resolution); results left unconsumed for
300 ms from arming are discarded. Valid stored distance expires after 300 ms.

Temperature uses a floating-point four-sample average, nominal 5000 mV reference
and 10 mV/C. Zero and above-range ADC sums invalidate the reading; accepted
range is (0,150] C. Sampling is synchronous. A disconnected input that happens
to look plausible cannot be identified by this check.

## State policy

AUTO enters ALARM below 20 cm or above 35 C. Automatic ALARM exits only with
both valid inputs, >=25 cm and <=33 C. Explicit ALARM is held until a mode/reset
command. Every mode derives outputs from its current state; no output or alarm
flag is inherited from the previous mode. MANUAL is explicitly neutral; there
is no implemented actuator command.

After the startup grace, invalid inputs in any active mode latch FAULT.
IDLE tolerates missing inputs. FAULT commands and observable watchdog reset
also latch FAULT. FAULT cannot be bypassed through IDLE or MANUAL. Only RESET
or SET_MODE AUTO after 500 ms continuously valid inputs clears it; immediately
unsafe thresholds can then enter ALARM. FAULT recovery does not require normal
thresholds, only valid inputs. It never happens automatically.

## Resource ownership and bounded work

Arduino Timer0 supplies millis/micros. Servo owns Timer1. PCINT2 is owned by the
echo driver. USART_RX and USART_UDRE belong only to UartAvr; the sketch must not
reference HardwareSerial/Serial, which would introduce competing handlers.

RX has 63 usable slots, each storing a byte and its receive timestamp. TX has
191 usable bytes. RX/error flags/counters and echo data are consumed atomically
where needed. Queue index publication uses compiler barriers; indices are
8-bit atomic values on AVR. This queue is designed for AVR ISR/main SPSC use,
not general multithreaded use.

TX never waits for capacity; messages either enqueue completely or increment
tx_dropped. GET_STATUS requests are coalesced within one loop. Input processing
has a fixed byte budget, protecting sensing and watchdog progress under load.
RX loss invalidates queued input and parser state. Saturating diagnostics do
not wrap to zero. See protocol.md for exact command semantics.

ADC, short trigger delays, formatting and interrupt exclusion still consume
synchronous time. Static RAM figures do not prove a stack bound. There is no
dynamic allocation in the application. Native fake peripherals exercise control
flow, not AVR instruction timing, electrical behavior or interrupt priority.

# Observed SRAM and stack usage (simulator)

This is scenario coverage, not an exhaustive worst-case stack proof or hardware
measurement. The firmware and release ELF/HEX files are not instrumented or
rewritten. The headless runner observes an emulated ATmega328P's stack pointer.

## Method

The runner reads linker `_end`, including .data/.bss/.noinit, and rejects images
linking malloc/calloc/realloc. This method assumes the current heap-free firmware.
At the first .init3 watchdog hook, after SP initialization and before a live
call frame, only unused SRAM from `_end` through RAMEND is filled with 0xA5.
No static variable or peripheral register is painted. SRAM is 0x100..0x8ff.

The emulator runs at an instruction boundary limit of one. SP is observed around
instructions and interrupt dispatch, so reserved local frames and ISR pushes
contribute. GCC writes SPH/SPL separately when adjusting a frame: the monitor
waits for the low-byte commit rather than treating the transient half-updated
16-bit pair as stack use. Both OUT and absolute STS writes are recognized.
Startup and runtime are covered; minima persist across an emulated reset.

Two independent observations are recorded:

- observed_stack_bytes = RAMEND - minimum committed SP.
- watermark_changed_span = highest-SRAM span down to the first byte no longer
  equal to 0xA5. Untouched-but-reserved frames can make these differ; bytes that
  happen to equal 0xA5 can evade the watermark. SP is the primary budget check.

minimum_gap_bytes = minimum SP - `_end` + 1. This plus observed stack and static
SRAM totals 2048 bytes. The runner fails on an observed stack/static collision.
A 512-byte minimum-gap regression budget is enforced by profile_matrix.py; it
is a project guardrail, not a guarantee for unexecuted branches or hardware.

## Scenarios and results

Every production profile is loaded separately and checked for correct identity,
required sensors, disabled outputs/interrupts, modes, alarm thresholds,
latched sensor loss/recovery and UART error recovery. A 160-request burst causes
TX backpressure while Timer0, ADC and echo IRQs remain active where enabled.
Three diagnostic counters are set to 65535 in simulator SRAM only to format
maximum-width diagnostics; near-upper-range sensor readings also exercise
the longest numeric readings. No arbitrary RAM-write command is exposed, and the
release file is unchanged. This injected counter case is not normal RX loss.

| Profile | Static SRAM | Observed stack peak | Minimum observed gap |
| --- | --- | --- | --- |
| full | 782 | 298 | 968 |
| uart | 759 | 284 | 1005 |
| distance | 763 | 289 | 996 |
| temperature | 776 | 284 | 988 |
| buzzer | 759 | 284 | 1005 |
| servo | 761 | 284 | 1003 |

All values are bytes, CLI 1.5.1 / AVR Core 1.8.6, default pulse bounds. The
watermark matched the SP span in these runs. This does not establish a static
upper bound or real-board interrupt timing. Firmware uses non-nested ISRs;
future nesting, heap allocation, larger buffers or different toolchains require
new analysis. Do not turn the observed gap into a claim of proven free RAM in
all possible executions.

See evidence/profile-matrix.json for image hashes and checkpoints. Repeat with
commands in simulation.md. The same all-profile scenario and budget run in CI.

References: [avr-libc SRAM/stack layout](https://avrdudes.github.io/avr-libc/avr-libc-user-manual/malloc.html)
and the pinned [simavr source](https://github.com/buserror/simavr/tree/v1.8).

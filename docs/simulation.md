# Headless AVR simulation and host end-to-end validation

These tests run CPU-only. No GPU, OpenGL window, physical serial port, board
connection or firmware upload is used. A Linux pseudo-terminal (/dev/pts/*)
connects the real Python CLI to the emulator during the end-to-end test.

## Prerequisites and pinned simulator

Use Linux, a host C compiler, make, git, Python with pyserial 3.5, pkg-config and
libelf development headers. On Ubuntu the missing development package is
libelf-dev. Helpers do not install global packages or run sudo themselves.
Arduino CLI/core remain pinned to 1.5.1 / arduino:avr@1.8.6.

simavr is built from v1.8, commit
`f44723e8c42431136d5b4de81f789ded56d7e8fa`. The setup helper rejects an existing
checkout at a different revision. Older v1.7 modeled Timer1 mode 14 incompletely
for this test: OCR1A changed but its simulated pulse width did not. The v1.8
pin model handles the tested update; firmware was not changed to fit v1.7.
No upstream code is vendored in the repository or release bundle.

From the repository root:

```sh
mkdir -p build
tools/build_firmware.sh full --build-path "$PWD/build/uno"
tools/simulation/setup_simavr.sh "$PWD/build/simavr"
tools/simulation/build_runner.sh "$PWD/build/simavr" "$PWD/build/avr-runner"
export ARDUCORE_SIM_RUNNER="$PWD/build/avr-runner"
export ARDUCORE_SIM_ELF="$PWD/build/uno/arducore.ino.elf"
python3 -m unittest discover -s tests/simulation -v
python3 -m unittest discover -s tests/e2e -v
python3 tests/simulation/soak.py --runner "$ARDUCORE_SIM_RUNNER" --elf "$ARDUCORE_SIM_ELF" --minutes 60 --report build/soak.json
```

An Arduino CLI --config-file option can be passed through build_firmware.sh
when the pinned core is installed in an isolated toolchain directory.
Without the two ARDUCORE_SIM_* variables, unittest discovery skips these suites;
that skip is not a simulation pass. CI sets both and runs a one-minute simulated
stress check in addition to the instruction and host tests.

## What actually executes

runner.c loads the production Uno ELF into an emulated ATmega328P at 16 MHz.
It supplies a nominal 5 V ADC reference and controllable millivolt input,
schedules echo edges from TRIG, captures UART output bytes and B1/D7 pin events,
and accepts paced host frames over pipes. No test-only code is compiled into
the release firmware. The bridge keeps a separate monotonic cycle total across
simavr reset-local cycle counters; timing comparisons never span MCU boots. UART input is spaced at 1100 us per byte; this respects
the nominal 9600 8N1 line rate rather than overfilling simavr's own input FIFO.
The bridge protocol is a local test interface, not a new device UART protocol.

Six instruction-level tests exercise ADC/echo measurements, bad-frame recovery,
USART framing-error recovery, mode changes, stable 1 ms/2 ms servo pulses and 20 ms periods, latched sensor
FAULT/recovery, and watchdog expiry after injected PC lockup. Timing assertions
allow 2 us for instruction/event scheduling differences. Pin changes in simavr
are not oscilloscope measurements or proof of SG90 motion.

Watchdog fault injection strands the simulated PC in spare flash containing
an infinite loop. This changes only the loaded simulator instance; release ELF
and HEX files are untouched. The test loads no Uno bootloader: MCUSR is visible
to the startup hook here. Real Optiboot reset-cause limitations still apply.

The end-to-end test launches the actual Python CLI with pyserial, a persistent
console and a JSONL log, connected through a newly allocated Linux PTY to the
running ELF. It checks mode commands, loss/refused recovery/restoration/reset,
telemetry parsing and persisted records. Opening/configuring a serial stream
may flush part of an initial banner; recovery before the first complete JSON
line is allowed. Malformed firmware output after synchronization fails the test.

## Deterministic stress and limits

soak.py defaults to 60 simulated minutes, seed 42517. Each simulated minute
cycles distance and thermal alarms, sensor loss, refused and accepted recovery,
noise and malformed frames, seeded mode commands and a status request flood.
It asserts telemetry state, no unexpected reset, no loss at paced RX line rate,
and exercised non-blocking TX backpressure. A summary records seed, virtual and
wall time, assertions, telemetry count, counters, PWM events and ADC triggers.

Simulated time is accelerated; one simulated hour is not a one-hour wall-clock
burn-in. No wall-clock longevity, electrical accuracy, oscillator tolerance,
noise, power supply or mechanics claim follows from this run. Native unsigned
counter-wrap tests remain separate; the one-hour run does not reach the
49-day millis rollover. Input RX overflow/error behavior has native tests;
this paced simulator run is not evidence of loss-free overload beyond line rate.

Sources: [simavr upstream](https://github.com/buserror/simavr/tree/v1.8), including
its UART/ADC/pin APIs. simavr is GPL-3.0 licensed and is built as an external
headless test dependency; its GUI examples are not built or linked.

## All-profile coverage and SRAM observation

Build each profile under build/profiles/<name>, set ARDUCORE_SIM_ELF_DIR to
that parent directory and ARDUCORE_SIM_ELF to its full/arducore.ino.elf. Then:

```sh
python3 tests/simulation/profile_matrix.py --runner "$ARDUCORE_SIM_RUNNER" --elf-dir "$ARDUCORE_SIM_ELF_DIR" --report build/profile-matrix.json
python3 tests/simulation/bench_matrix.py --runner "$ARDUCORE_SIM_RUNNER" --elf-dir "$ARDUCORE_SIM_ELF_DIR" --report-dir build/bench-matrix
```

The profile matrix checks all six real ELF images, sensor requirements and
disabled pins/interrupts, thresholds, FAULT recovery and communication load.
It also records stack-pointer minima and SRAM watermark observations. See
[memory measurement](memory.md) for the 512-byte observed-headroom budget and
limits, and [bench assistant](bench-assistant.md) for the future serial helper.
No simulator result certifies electrical or mechanical behavior.

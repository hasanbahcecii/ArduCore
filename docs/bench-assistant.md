# Profile-aware bench assistant

The assistant executes a fixed diagnostic sequence, logs commands and telemetry,
and writes a result file. No firmware upload or automatic port selection occurs.
Its physical serial backend has only been tested through a Linux pseudo-terminal
connected to an emulated firmware. Real board checks remain deferred.

## Hardware-free use now

Use Python 3.8+, pyserial 3.5 and the headless simulation setup in simulation.md.
Build full/uart/distance/temperature/buzzer/servo under build/profiles/<name>.
For example:

```sh
mkdir -p build
for profile in full uart distance temperature buzzer servo; do
  tools/build_firmware.sh "$profile" --build-path "$PWD/build/profiles/$profile"
done
python3 tools/host/bench.py --simulate --profile full --actuate \
  --runner "$PWD/build/avr-runner" --elf-dir "$PWD/build/profiles" \
  --report-dir build/bench-full
```

--report-dir must be a new directory; existing records are never overwritten.
It contains report.json and timestamped events.jsonl. --timeout is per step,
3 seconds by default, in virtual time for --simulate. --simulate requires the
specified runner and all-profile ELF directory; it does not open pyserial.

In simulation the sequence can supply threshold/loss stimuli and inspect pin
model results. Full requires --actuate to run its output-bearing scenarios;
otherwise those steps are skipped. An explicit simulated run is never labeled
a successful physical hardware test.

## Later real-board use, one component at a time

First upload the matching profile separately, using bench-testing.md. Then open
one persistent connection with an explicitly selected port (example only):

```sh
python3 tools/host/bench.py --port /dev/ttyACM0 --profile uart --report-dir build/bench-uart
python3 tools/host/bench.py --port /dev/ttyACM0 --profile distance --report-dir build/bench-distance
python3 tools/host/bench.py --port /dev/ttyACM0 --profile temperature --report-dir build/bench-temperature
python3 tools/host/bench.py --port /dev/ttyACM0 --profile buzzer --actuate --report-dir build/bench-buzzer
python3 tools/host/bench.py --port /dev/ttyACM0 --profile servo --actuate --report-dir build/bench-servo
```

These are deferred commands; none was run on a real device during development.
Serial open may reset Uno via DTR; the default startup wait is two seconds.
The selected profile must match telemetry's numeric profile before any command
is sent. Unknown/legacy or mismatched profiles fail without sending mode/reset
commands. A changed profile revokes command permission during a session.

The assistant checks that required sensor data is available, requests IDLE,
optionally ALARM, returns to IDLE and records the resulting telemetry. Buzzer,
servo and full profiles require --actuate before an explicit ALARM command is
sent; without it that sequence is skipped. Disabled-output sensor/UART profiles
can exercise mode commands without actuating those disabled outputs. No sweep
is performed. Normal firmware startup can still command a servo position even
without --actuate; the option controls the assistant's command sequence only.

At completion or failure, IDLE is attempted only after profile verification.
An unhealthy latched FAULT may reject it or a disconnect may prevent confirmation;
the report records unconfirmed cleanup and exits with failure. IDLE is the
firmware's logical neutral position, not a power disconnect or proof of movement.
The tool does not bypass FAULT with repeated RESETs on real hardware.

## What a pass means

A serial run reports software_checks_passed_hardware_pending, never hardware
verified. UART telemetry cannot prove sensor calibration, buzzer sound, servo
travel or power integrity. Manual checks remain listed in the report. Real
threshold and unplug/reconnect tests require later external stimuli; these are
automated only against the simulator. A sent event is not a protocol ACK.

A simulated run reports simulated_checks_passed, with hardware_verified=false.
Failures and interruptions retain partial checks and attempt cleanup. Exit 0
means its selected software sequence passed, 1 means failure, 2 argument/path
error, 130 interruption (or 1 if cleanup could not be confirmed).

Tests: tests/bench unit cases, tests/simulation/bench_matrix.py across all six
ELFs, and tests/e2e/test_bench_serial.py for real pyserial over virtual ports.

# Python host tool

Python 3.8+ and pyserial 3.5. No automatic device selection or firmware upload.
The demo does not import pyserial or open a serial device.

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r tools/host/requirements.txt
python3 tools/host/arducore_host.py --demo
```

For a later hardware session (example port only):

```sh
python3 tools/host/arducore_host.py --list-ports
python3 tools/host/arducore_host.py --port /dev/ttyACM0 monitor
python3 tools/host/arducore_host.py --port /dev/ttyACM0 --duration 10 --log readings.jsonl monitor
python3 tools/host/arducore_host.py --port /dev/ttyACM0 status
python3 tools/host/arducore_host.py --port /dev/ttyACM0 mode idle
python3 tools/host/arducore_host.py --port /dev/ttyACM0 reset
python3 tools/host/arducore_host.py --port /dev/ttyACM0 console
```

Options precede the subcommand. `--json` prints structured events instead of
human-readable readings. `--log` appends UTC timestamped JSONL events and does
not overwrite the file. Invalid readings display as --; a missing profile on
legacy telemetry displays unknown, not full. Extra JSON fields are preserved.

`monitor` and `console` run until Ctrl+C by default. One-shot commands listen
for three seconds; --duration overrides this (0 means unlimited). The console
accepts status, reset, mode idle/auto/manual/alarm/fault, and quit, one command
per line while telemetry continues. EOF also leaves the console. Use a single
console connection when changing modes: repeatedly opening a Uno port can
reset the board through DTR. --startup-wait defaults to two seconds.

Commands are five-byte frames sent in a single write. Short writes and serial
errors are reported without automatic command retries. A sent event means the
host write succeeded, not that the firmware accepted the command. The protocol
has no acknowledgements or sequence numbers; unsolicited telemetry received
near a command may predate it. Inspect subsequent state/rejected counters.
Logical reset does not reboot the MCU and cannot bypass a latched unhealthy
FAULT. No speed command is offered because firmware does not implement it.

The reader handles fragmented/multiple lines, startup banners, non-ASCII or
invalid JSON and oversized lines. At most 4096 bytes of an unfinished line are
stored; oversized input is discarded through its next newline. Types, finite
readings, known mode/profile ranges and diagnostic bounds are validated.
Unknown JSON fields are permitted. This is a diagnostic console, not an
authenticated or guaranteed-delivery transport.

Exit codes: 0 for success/demo/console quit; 1 for connection/log errors or no
valid telemetry in a finite listening session; 2 for invalid arguments; 130
for Ctrl+C. A read timeout may extend a finite session by about 0.2 seconds.

Tests (software mocks and pyserial loop://, no hardware):

```sh
python3 -m unittest discover -s tests/host -v
```

Sources: [pyserial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
and [software URL transports](https://pyserial.readthedocs.io/en/latest/url_handlers.html).

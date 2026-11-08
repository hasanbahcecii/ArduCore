#!/usr/bin/env python3
"""ArduCore UART console. No port is opened without an explicit --port."""
import argparse
import datetime
import json
import math
import queue
import threading
import sys
import time
from pathlib import Path

MODES = {"idle": 0, "auto": 1, "manual": 2, "alarm": 3, "fault": 4}
PROFILES = {0: "full", 1: "uart", 2: "distance", 3: "temperature", 4: "buzzer", 5: "servo"}


def frame(command, data=0):
    if type(command) is not int or type(data) is not int or not (0 <= command <= 255 and 0 <= data <= 255):
        raise ValueError("Command and data must be bytes")
    return bytes((2, command, data, command ^ data, 3))


def telemetry(line):
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Telemetry must be an object")
    if type(value.get("state")) is not int or not 0 <= value["state"] <= 4:
        raise ValueError("Invalid state")
    if type(value.get("alarm")) is not bool:
        raise ValueError("Invalid alarm flag")
    for key, upper in (("dist", 400), ("temp", 150)):
        reading = value.get(key)
        if type(reading) not in (int, float) or not math.isfinite(reading):
            raise ValueError("Invalid " + key)
        if reading != -1 and not 0 <= reading <= upper:
            raise ValueError("Out-of-range " + key)
    for key in ("rx_errors", "tx_dropped", "rejected", "reset_flags", "profile"):
        if key in value:
            limit = 5 if key == "profile" else 255 if key == "reset_flags" else 65535
            if type(value[key]) is not int or not 0 <= value[key] <= limit:
                raise ValueError("Invalid " + key)
    return value


class LineDecoder:
    """Bounded streaming decoder; a long/invalid line cannot poison the next."""
    def __init__(self, limit=4096):
        self.pending = bytearray()
        self.limit = limit
        self.dropping = False

    def feed(self, chunk):
        events = []
        for byte in chunk:
            if byte == 10:
                if self.dropping:
                    self.dropping = False
                elif self.pending:
                    raw = bytes(self.pending).rstrip(b"\r")
                    try:
                        line = raw.decode("ascii")
                        if line.startswith("ArduCore ") and line.endswith(" READY"):
                            if not line.isprintable():
                                raise ValueError("Non-printable startup banner")
                            events.append(("banner", line))
                        else:
                            events.append(("telemetry", telemetry(line)))
                    except (ValueError, UnicodeError, OverflowError, RecursionError) as exc:
                        events.append(("invalid", {"reason": str(exc)[:200], "raw": repr(raw[:200])}))
                self.pending.clear()
            elif not self.dropping:
                if len(self.pending) >= self.limit:
                    self.pending.clear()
                    self.dropping = True
                    events.append(("invalid", {"reason": "Line exceeded size limit"}))
                else:
                    self.pending.append(byte)
        return events


def event(kind, data):
    return {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(), "type": kind, "data": data}


def display(item):
    data = item["data"]
    if item["type"] != "telemetry":
        return item["type"] + ": " + str(data)
    def reading(key, unit):
        return "--" if data[key] == -1 else f"{data[key]:.1f}{unit}"
    profile = PROFILES.get(data.get("profile"), "unknown (legacy firmware)")
    return (f"profile={profile} state={data['state']} dist={reading('dist', 'cm')} "
            f"temp={reading('temp', 'C')} alarm={data['alarm']} "
            f"rx_errors={data.get('rx_errors', '?')} tx_dropped={data.get('tx_dropped', '?')} "
            f"rejected={data.get('rejected', '?')}")


def console_command(line):
    words = line.strip().split()
    if words == ["quit"]:
        return "quit", None
    if words == ["status"]:
        return "status", frame(3)
    if words == ["reset"]:
        return "reset", frame(255)
    if len(words) == 2 and words[0] == "mode" and words[1] in MODES:
        return "mode " + words[1], frame(1, MODES[words[1]])
    raise ValueError("Use status, reset, mode idle|auto|manual|alarm|fault, or quit")


def send(connection, payload, label, emit):
    if connection.write(payload) != len(payload):
        raise OSError("Incomplete command write; not automatically retried")
    emit(event("sent", {"command": label, "frame": payload.hex(" "),
                        "note": "Sent only; protocol has no acknowledgement"}))


def receive(connection, duration, emit, clock=time.monotonic, commands=None):
    decoder = LineDecoder()
    started = clock()
    count = 0
    while duration == 0 or clock() - started < duration:
        if commands is not None:
            line = commands()
            if line is not None:
                try:
                    label, payload = console_command(line)
                    if label == "quit":
                        break
                    send(connection, payload, label, emit)
                except ValueError as exc:
                    emit(event("invalid", {"reason": str(exc)}))
        chunk = connection.read(256)
        for kind, data in decoder.feed(chunk):
            emit(event(kind, data))
            if kind == "telemetry":
                count += 1
    return count


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Explicit serial device, e.g. /dev/ttyACM0")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Display synthetic data without opening a port")
    parser.add_argument("--duration", type=float, help="Seconds to listen; 0 means until Ctrl+C")
    parser.add_argument("--startup-wait", type=float, default=2.0, help="Boot wait after open, default 2 seconds")
    parser.add_argument("--log", type=Path, help="Append timestamped events to a JSONL file")
    parser.add_argument("--json", action="store_true", help="Print normalized JSONL events")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("monitor")
    sub.add_parser("status")
    sub.add_parser("console", help="Send commands without reopening/resetting the port")
    mode = sub.add_parser("mode")
    mode.add_argument("value", choices=MODES)
    sub.add_parser("reset", help="Logical recovery request, not an MCU reboot")
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration < 0):
        parser.error("--duration must be finite and nonnegative")
    if not math.isfinite(args.startup_wait) or args.startup_wait < 0:
        parser.error("--startup-wait must be finite and nonnegative")
    if args.demo and (args.port or args.list_ports or args.command):
        parser.error("--demo cannot be combined with a port or command")
    if args.list_ports and (args.port or args.command):
        parser.error("--list-ports cannot be combined with a port or command")
    if not (args.demo or args.list_ports or args.port):
        parser.error("Specify --port, --list-ports or --demo")
    log = None
    try:
        if args.log:
            log = args.log.open("a", encoding="utf-8")
        def emit(item):
            encoded = json.dumps(item, ensure_ascii=True, allow_nan=False)
            print(encoded if args.json else display(item), flush=True)
            if log:
                log.write(encoded + "\n")
                log.flush()
        if args.demo:
            emit(event("demo", "Synthetic data; no hardware accessed"))
            emit(event("telemetry", {"state": 1, "dist": 34.3, "temp": 25.4,
                                   "alarm": False, "profile": 0, "rx_errors": 0,
                                   "tx_dropped": 0, "rejected": 0, "reset_flags": 0}))
            return 0
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            print("Install dependencies: python3 -m pip install -r tools/host/requirements.txt", file=sys.stderr)
            return 1
        if args.list_ports:
            for port in list_ports.comports():
                print(f"{port.device}\t{port.description}")
            return 0
        command = args.command or "monitor"
        duration = args.duration if args.duration is not None else (0 if command in ("monitor", "console") else 3)
        with serial.serial_for_url(args.port, baudrate=9600, timeout=0.2, write_timeout=1) as connection:
            # Uno may reset on open through DTR. Preserve incoming startup lines.
            time.sleep(args.startup_wait)
            if command not in ("monitor", "console"):
                cmd, data = {"status": (3, 0), "mode": (1, MODES.get(getattr(args, "value", ""), 0)),
                             "reset": (255, 0)}[command]
                send(connection, frame(cmd, data), command, emit)
            commands = None
            if command == "console":
                print("Commands: status, mode idle|auto|manual|alarm|fault, reset, quit", file=sys.stderr)
                inbox = queue.Queue(maxsize=16)
                def stdin_worker():
                    for line in sys.stdin:
                        inbox.put(line)
                    inbox.put("quit")
                threading.Thread(target=stdin_worker, daemon=True).start()
                def poll_command():
                    try:
                        return inbox.get_nowait()
                    except queue.Empty:
                        return None
                commands = poll_command
            count = receive(connection, duration, emit, commands=commands)
            if not count and command != "console":
                print("No valid telemetry received within the listening interval", file=sys.stderr)
                return 1
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as exc:
        print(f"Connection/log error: {exc}", file=sys.stderr)
        return 1
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    sys.exit(main())

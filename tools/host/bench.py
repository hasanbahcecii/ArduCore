#!/usr/bin/env python3
"""Profile-aware bench sequence; explicit port or simulator, no auto-upload."""
import argparse
import datetime
import importlib.util
import json
import math
import pathlib
import sys
import time

import arducore_host as host

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROFILES = tuple(host.PROFILES.values())


class Simulation:
    def __init__(self, runner, elf):
        spec = importlib.util.spec_from_file_location("bench_sim_bridge", ROOT / "tests/simulation/bridge.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.device = module.Device(runner, elf)

    def poll(self, seconds):
        return self.device.run(seconds)

    def send(self, payload):
        return self.device.exchange("rx " + payload.hex())[0]

    def stimulus(self, command):
        return self.device.exchange(command)[0]

    def metrics(self):
        return self.device.metrics()

    def close(self):
        self.device.close()


class Serial:
    def __init__(self, port, startup_wait):
        import serial
        self.connection = serial.serial_for_url(port, baudrate=9600, timeout=0.1, write_timeout=1)
        try:
            time.sleep(startup_wait)
        except BaseException:
            self.connection.close()
            raise

    def poll(self, seconds):
        until = time.monotonic() + seconds
        output = bytearray()
        while time.monotonic() < until:
            output.extend(self.connection.read(256))
        return bytes(output)

    def send(self, payload):
        if self.connection.write(payload) != len(payload):
            raise OSError("Incomplete command write; not retried")
        return b""

    def close(self):
        self.connection.close()


class Session:
    def __init__(self, transport, profile, timeout, log, report):
        self.transport, self.profile, self.timeout = transport, profile, timeout
        self.log, self.report = log, report
        self.decoder = host.LineDecoder()
        self.latest = None
        self.profile_verified = False

    def emit(self, kind, data):
        self.log.write(json.dumps(host.event(kind, data), allow_nan=False) + "\n")
        self.log.flush()

    def ingest(self, wire):
        for kind, data in self.decoder.feed(wire):
            self.emit(kind, data)
            if kind == "telemetry":
                self.latest = data
                if self.profile_verified and data.get("profile") != PROFILES.index(self.profile):
                    self.profile_verified = False
                    raise ValueError("Firmware profile changed during session")

    def wait(self, predicate):
        # Each bounded poll advances virtual time or consumes real port time.
        for _ in range(math.ceil(self.timeout / 0.1)):
            self.ingest(self.transport.poll(0.1))
            if self.latest is not None and predicate(self.latest):
                return self.latest
        raise TimeoutError("Expected telemetry was not observed before step timeout")

    def command(self, command, data=0):
        if not self.profile_verified:
            raise ValueError("Refusing commands before profile verification")
        payload = host.frame(command, data)
        self.emit("sent", {"frame": payload.hex(" "), "acknowledged": False})
        self.ingest(self.transport.send(payload))

    def mode(self, value):
        self.command(1, value)
        self.wait(lambda item: item["state"] == value)

    def check(self, name, function):
        result = {"name": name, "status": "failed"}
        self.report["checks"].append(result)
        try:
            function()
        except (OSError, ValueError, AssertionError, TimeoutError, RuntimeError) as exc:
            result["detail"] = str(exc)
            self.emit("check", result)
            raise
        result["status"] = "passed"
        if self.latest:
            result["telemetry"] = dict(self.latest)
        self.emit("check", result)


def sequence(session, actuate, simulated):
    profile = session.profile
    required_distance = profile in ("full", "distance")
    required_temperature = profile in ("full", "temperature")
    def identity():
        session.wait(lambda item: True)
        if session.latest.get("profile") != PROFILES.index(profile):
            raise ValueError(f"Expected profile {profile}, received {session.latest.get('profile')}; no commands sent")
        session.profile_verified = True
    session.check("firmware_profile", identity)
    def health():
        session.wait(lambda item: (not required_distance or item["dist"] > 0) and
                     (not required_temperature or item["temp"] >= 0))
    session.check("required_sensor_data_available", health)
    session.check("idle_command_and_telemetry", lambda: session.mode(0))
    if actuate or profile in ("uart", "distance", "temperature"):
        # Explicit --actuate is required for output-bearing profiles. No sweep.
        session.check("alarm_command_and_telemetry", lambda: session.mode(3))
        if simulated:
            def pins():
                metrics = session.transport.metrics()
                assert metrics["buzzer"] == int(profile in ("full", "buzzer")), metrics
                if profile in ("full", "servo"):
                    assert metrics["ocr1a"] == 4000 and metrics["pulses"] > 0, metrics
                elif metrics["pulses"]:
                    raise ValueError("Disabled servo generated simulated pulses")
            session.check("simulated_output_pins", pins)
        session.check("idle_after_alarm", lambda: session.mode(0))
    else:
        session.report["skipped"].append("Alarm/output sequence: --actuate was not provided")
    if simulated and (required_distance or required_temperature) and (actuate or profile != "full"):
        session.check("auto_command", lambda: session.mode(1))
        trigger = "echo 1000" if required_distance else "temp 450"
        restore = "echo 2000" if required_distance else "temp 250"
        def threshold():
            session.ingest(session.transport.stimulus(trigger))
            session.wait(lambda item: item["state"] == 3)
            session.ingest(session.transport.stimulus(restore))
            session.wait(lambda item: item["state"] == 1)
        session.check("simulated_threshold_and_hysteresis", threshold)
        def loss_and_recovery():
            loss = "echo 0" if required_distance else "temp 0"
            session.ingest(session.transport.stimulus(loss))
            session.wait(lambda item: item["state"] == 4)
            previous = session.latest.get("rejected", 0)
            session.command(255)
            session.wait(lambda item: item["state"] == 4 and item.get("rejected", 0) > previous)
            session.ingest(session.transport.stimulus(restore))
            # Keep the fault latched while accumulating the 500 ms healthy interval.
            for _ in range(10):
                session.ingest(session.transport.poll(0.1))
            session.command(255)
            session.wait(lambda item: item["state"] == 1)
        session.check("simulated_fault_and_recovery", loss_and_recovery)
    session.check("final_idle_telemetry", lambda: session.mode(0))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--port", help="Explicit serial device; never auto-detected")
    selection.add_argument("--simulate", action="store_true")
    parser.add_argument("--profile", required=True, choices=PROFILES)
    parser.add_argument("--runner", type=pathlib.Path)
    parser.add_argument("--elf-dir", type=pathlib.Path)
    parser.add_argument("--report-dir", type=pathlib.Path, required=True, help="New directory; existing reports are not overwritten")
    parser.add_argument("--actuate", action="store_true", help="Allow explicit ALARM command for buzzer/servo/full profiles")
    parser.add_argument("--timeout", type=float, default=3, help="Per-step seconds (virtual with --simulate)")
    parser.add_argument("--startup-wait", type=float, default=2)
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0.1 <= args.timeout <= 60:
        parser.error("--timeout must be finite within 0.1..60 seconds")
    if not math.isfinite(args.startup_wait) or not 0 <= args.startup_wait <= 60:
        parser.error("--startup-wait must be finite within 0..60 seconds")
    if args.simulate and not (args.runner and args.elf_dir):
        parser.error("--simulate requires --runner and --elf-dir")
    if args.simulate and (not args.runner.is_file() or not (args.elf_dir / args.profile / "arducore.ino.elf").is_file()):
        parser.error("Simulator runner and selected profile ELF must exist")
    if args.port and (args.runner or args.elf_dir):
        parser.error("Simulator arguments cannot accompany a real port")
    try:
        args.report_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(str(exc))
    report = {"profile": args.profile, "backend": "simavr" if args.simulate else "serial",
              "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "target_port": args.port, "actuation_requested": args.actuate, "checks": [], "skipped": [],
              "hardware_verified": False, "observations": "UART confirms state, not physical output/accuracy",
              "manual_checks_pending": ["electrical connections and supply", "sensor accuracy and actual disconnection",
                                        "actuator motion/sound when applicable", "final full-system hardware integration"]}
    transport = session = None
    result = 1
    with (args.report_dir / "events.jsonl").open("x", encoding="utf-8") as log:
        try:
            transport = Simulation(args.runner, args.elf_dir / args.profile / "arducore.ino.elf") if args.simulate else Serial(args.port, args.startup_wait)
            session = Session(transport, args.profile, args.timeout, log, report)
            sequence(session, args.actuate, args.simulate)
            report["status"] = "simulated_checks_passed" if args.simulate else "software_checks_passed_hardware_pending"
            result = 0
        except (OSError, ValueError, AssertionError, TimeoutError, RuntimeError, ImportError) as exc:
            report["status"], report["error"] = "failed", str(exc)
        except KeyboardInterrupt:
            report["status"], report["error"] = "interrupted", "User interrupted the sequence"
            result = 130
        finally:
            if session and session.profile_verified:
                try:
                    session.mode(0)
                    report["cleanup"] = "idle_confirmed_by_telemetry"
                except (OSError, ValueError, AssertionError, TimeoutError, RuntimeError) as exc:
                    report["cleanup"] = "unconfirmed: " + str(exc)
                    report["status"], result = "failed", 1
            if transport:
                try:
                    transport.close()
                except OSError as exc:
                    report["close_error"] = str(exc)
                    report["status"], result = "failed", 1
            report["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (args.report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report_dir / "report.json")}))
    return result


if __name__ == "__main__":
    sys.exit(main())

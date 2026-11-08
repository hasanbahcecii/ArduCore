"""Control a headless simavr child; transport is pipes, never a physical port."""
import importlib.util
import json
import os
import pathlib
import select
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("arducore_host", ROOT / "tools/host/arducore_host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class Device:
    def __init__(self, runner, elf):
        self.process = subprocess.Popen([str(runner), str(elf)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, bufsize=0)
        self.pending = bytearray()
        self.decoder = host.LineDecoder()
        self.records = []
        self.raw = bytearray()
        deadline = time.monotonic() + 10
        while self.line(deadline) != "READY":
            pass

    def line(self, deadline):
        while b"\n" not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError("Simulator bridge did not respond")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError(f"Simulator exited: {self.process.poll()}")
            self.pending.extend(chunk)
        line, _, rest = self.pending.partition(b"\n")
        self.pending[:] = rest
        return line.decode("ascii")

    def exchange(self, command):
        self.process.stdin.write(command.encode("ascii") + b"\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 30
        metrics = None
        received = bytearray()
        while True:
            line = self.line(deadline)
            if line == "DONE":
                break
            if line.startswith("TX "):
                received.extend(bytes.fromhex(line[3:]))
            elif line.startswith("METRICS "):
                metrics = json.loads(line[8:])
            else:
                raise RuntimeError("Unexpected simulator response: " + line)
        self.raw.extend(received)
        for kind, value in self.decoder.feed(received):
            if kind == "invalid":
                raise AssertionError("Firmware emitted invalid host telemetry: " + str(value))
            if kind == "telemetry":
                self.records.append(value)
        return bytes(received), metrics

    def run(self, seconds):
        return self.exchange("run " + str(int(seconds * 1000000)))[0]

    def command(self, command, data=0):
        return self.exchange("rx " + host.frame(command, data).hex())[0]

    def metrics(self):
        return self.exchange("metrics")[1]

    def latest(self):
        if not self.records:
            raise AssertionError("No telemetry from firmware")
        return self.records[-1]

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b"quit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

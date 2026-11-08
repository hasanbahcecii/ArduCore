"""Real host CLI <-> Linux virtual serial port <-> release ELF under simavr."""
import json
import os
import pathlib
import pty
import queue
import select
import subprocess
import sys
import tempfile
import threading
import time
import tty
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/simulation"))
from bridge import Device
RUNNER = os.environ.get("ARDUCORE_SIM_RUNNER")
ELF = os.environ.get("ARDUCORE_SIM_ELF")


class VirtualPort:
    def __init__(self):
        self.master, self.slave = pty.openpty()
        tty.setraw(self.slave)
        self.path = os.ttyname(self.slave)
        if not self.path.startswith("/dev/pts/"):
            raise RuntimeError("Expected a Linux pseudo-terminal, never a physical port")
        self.jobs = queue.Queue()
        self.failure = None
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def deliver(self, data):
        while data:
            amount = os.write(self.master, data)
            data = data[amount:]

    def run(self):
        try:
            with Device(RUNNER, ELF) as device:
                while not self.stop.is_set():
                    try:
                        command, completed = self.jobs.get_nowait()
                        self.deliver(device.exchange(command)[0])
                        completed.set()
                    except queue.Empty:
                        pass
                    if select.select([self.master], [], [], 0.02)[0]:
                        wire = os.read(self.master, 128)
                        if wire:
                            self.deliver(device.exchange("rx " + wire.hex())[0])
                    self.deliver(device.run(0.02))
        except BaseException as exc:
            self.failure = exc

    def sensor(self, command):
        completed = threading.Event()
        self.jobs.put((command, completed))
        if not completed.wait(5):
            raise RuntimeError(f"Virtual device stalled: {self.failure}")

    def close(self):
        self.stop.set()
        self.worker.join(5)
        os.close(self.master)
        os.close(self.slave)
        if self.worker.is_alive():
            raise RuntimeError("Virtual device worker did not stop")
        if self.failure:
            raise self.failure


@unittest.skipUnless(RUNNER and ELF, "Set simulator runner and ELF")
class EndToEndTests(unittest.TestCase):
    def test_console_commands_fault_recovery_and_recording(self):
        port = VirtualPort()
        child = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                log = pathlib.Path(directory) / "events.jsonl"
                child = subprocess.Popen([sys.executable, str(ROOT / "tools/host/arducore_host.py"),
                                          "--port", port.path, "--startup-wait", "0", "--json",
                                          "--log", str(log), "console"], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                events = queue.Queue()
                def capture():
                    for line in child.stdout:
                        try:
                            events.put(json.loads(line))
                        except ValueError as exc:
                            events.put(exc)
                reader = threading.Thread(target=capture, daemon=True)
                reader.start()

                def wait_state(state):
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        if port.failure:
                            raise port.failure
                        try:
                            item = events.get(timeout=0.3)
                        except queue.Empty:
                            continue
                        if isinstance(item, Exception):
                            raise item
                        if item["type"] == "telemetry" and item["data"]["state"] == state:
                            self.assertEqual(item["data"]["profile"], 0)
                            return item["data"]
                    self.fail(f"Host did not report state={state}; exit={child.poll()}")

                def command(text):
                    child.stdin.write(text + "\n")
                    child.stdin.flush()

                wait_state(1)
                command("mode alarm")
                wait_state(3)
                command("mode idle")
                wait_state(0)
                command("mode auto")
                wait_state(1)
                port.sensor("echo 0")
                bad = wait_state(4)
                self.assertEqual(bad["dist"], -1)
                command("reset")
                # Wait until the rejected counter proves the device refused recovery.
                deadline = time.monotonic() + 5
                while True:
                    fault = wait_state(4)
                    if fault["rejected"] > bad["rejected"]:
                        break
                    self.assertLess(time.monotonic(), deadline)
                port.sensor("echo 2000")
                time.sleep(1.2) # Real virtual-port pump time, not a hardware wait.
                command("reset")
                wait_state(1)
                command("status")
                wait_state(1)
                command("quit")
                self.assertEqual(child.wait(timeout=5), 0)
                reader.join(2)
                recorded = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertTrue(all("time" in item for item in recorded))
                states = {item["data"]["state"] for item in recorded if item["type"] == "telemetry"}
                self.assertTrue({0, 1, 3, 4}.issubset(states))
                self.assertGreaterEqual(sum(item["type"] == "sent" for item in recorded), 6)
                # Opening/configuring a serial port may flush a partial startup
                # banner. Recovery before the first complete telemetry is valid;
                # malformed lines after synchronization remain a failure.
                first_valid = next(i for i, item in enumerate(recorded) if item["type"] == "telemetry")
                self.assertFalse(any(item["type"] == "invalid" for item in recorded[first_valid:]),
                                 [item for item in recorded[first_valid:] if item["type"] == "invalid"])
        finally:
            if child:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=3)
                child.stdin.close()
                child.stdout.close()
                child.stderr.close()
            port.close()


if __name__ == "__main__":
    unittest.main()

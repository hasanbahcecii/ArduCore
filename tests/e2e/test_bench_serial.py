"""Exercise the bench tool's real pyserial backend on an emulated UART image."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_host_firmware import ROOT, RUNNER, ELF, VirtualPort

ELF_DIR = os.environ.get("ARDUCORE_SIM_ELF_DIR")


@unittest.skipUnless(RUNNER and ELF and ELF_DIR, "Set simulator and all-profile ELF directory")
class BenchSerialTests(unittest.TestCase):
    def test_uart_bench_over_real_pyserial_and_virtual_port(self):
        port = VirtualPort(elf=Path(ELF_DIR) / "uart/arducore.ino.elf")
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "result"
                child = subprocess.run([sys.executable, str(ROOT / "tools/host/bench.py"), "--port", port.path,
                                        "--profile", "uart", "--startup-wait", "0", "--timeout", "5",
                                        "--report-dir", str(target)], capture_output=True, text=True, timeout=25)
                self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
                report = json.loads((target / "report.json").read_text())
                self.assertEqual(report["status"], "software_checks_passed_hardware_pending")
                self.assertFalse(report["hardware_verified"])
                self.assertEqual(report["cleanup"], "idle_confirmed_by_telemetry")
                self.assertTrue(all(check["status"] == "passed" for check in report["checks"]))
                self.assertTrue(port.received)
        finally:
            port.close()

    def test_wrong_image_prevents_every_command(self):
        port = VirtualPort(elf=Path(ELF_DIR) / "uart/arducore.ino.elf")
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "result"
                child = subprocess.run([sys.executable, str(ROOT / "tools/host/bench.py"), "--port", port.path,
                                        "--profile", "servo", "--actuate", "--startup-wait", "0",
                                        "--report-dir", str(target)], capture_output=True, text=True, timeout=15)
                self.assertEqual(child.returncode, 1)
                report = json.loads((target / "report.json").read_text())
                self.assertEqual(report["status"], "failed")
                self.assertIn("no commands sent", report["error"])
                self.assertEqual(port.received, b"")
        finally:
            port.close()


if __name__ == "__main__":
    unittest.main()

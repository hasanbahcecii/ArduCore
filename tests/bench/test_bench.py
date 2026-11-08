import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host"))
import bench


class Fake:
    def __init__(self, profile=1, healthy=True, fail_alarm=False):
        self.profile = profile
        self.healthy = healthy
        self.fail_alarm = fail_alarm
        self.state = 1
        self.writes = []
        self.closed = False

    def poll(self, _):
        return (json.dumps({"profile": self.profile, "state": self.state,
                            "alarm": self.state in (3, 4), "dist": 30 if self.healthy else -1,
                            "temp": 25 if self.healthy else -1, "rejected": 0}) + "\r\n").encode()

    def send(self, payload):
        self.writes.append(payload)
        if self.fail_alarm and payload[2] == 3:
            raise OSError("Lost connection")
        self.state = payload[2]
        return b""

    def close(self):
        self.closed = True


class BenchTests(unittest.TestCase):
    def execute(self, fake, profile, *extra):
        with tempfile.TemporaryDirectory() as directory:
            report_dir = pathlib.Path(directory) / "new-report"
            with mock.patch.object(bench, "Serial", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
                code = bench.main(["--port", "FAKE", "--profile", profile,
                                   "--report-dir", str(report_dir), *extra])
            report = json.loads((report_dir / "report.json").read_text())
            events = [json.loads(line) for line in (report_dir / "events.jsonl").read_text().splitlines()]
            return code, report, events

    def test_uart_sequence_reports_hardware_pending(self):
        fake = Fake()
        code, report, events = self.execute(fake, "uart")
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "software_checks_passed_hardware_pending")
        self.assertFalse(report["hardware_verified"])
        self.assertTrue(fake.closed)
        self.assertEqual(fake.state, 0)
        self.assertTrue(all(item["data"]["acknowledged"] is False for item in events if item["type"] == "sent"))

    def test_wrong_profile_never_sends_commands(self):
        fake = Fake(profile=0)
        code, report, _ = self.execute(fake, "uart")
        self.assertEqual(code, 1)
        self.assertEqual(fake.writes, [])
        self.assertIn("Expected profile", report["error"])

    def test_actuator_requires_explicit_option(self):
        fake = Fake(profile=4)
        code, report, _ = self.execute(fake, "buzzer")
        self.assertEqual(code, 0)
        self.assertTrue(report["skipped"])
        self.assertFalse(any(frame[2] == 3 for frame in fake.writes))
        fake = Fake(profile=4)
        code, report, _ = self.execute(fake, "buzzer", "--actuate")
        self.assertEqual(code, 0)
        self.assertTrue(any(frame[2] == 3 for frame in fake.writes))

    def test_failed_command_still_attempts_idle(self):
        fake = Fake(profile=4, fail_alarm=True)
        code, report, _ = self.execute(fake, "buzzer", "--actuate")
        self.assertEqual(code, 1)
        self.assertEqual(report["cleanup"], "idle_confirmed_by_telemetry")
        self.assertEqual(fake.writes[-1][2], 0)
        self.assertTrue(fake.closed)

    def test_missing_required_sensor_is_not_a_pass(self):
        code, report, _ = self.execute(Fake(profile=2, healthy=False), "distance", "--timeout", "0.1")
        self.assertEqual(code, 1)
        self.assertEqual(report["checks"][-1]["name"], "required_sensor_data_available")
        self.assertEqual(report["checks"][-1]["status"], "failed")

    def test_profile_change_revokes_command_permission(self):
        fake = Fake(profile=1)
        session = bench.Session(fake, "uart", 1, io.StringIO(), {"checks": []})
        session.profile_verified = True
        fake.profile = 0
        with self.assertRaises(ValueError):
            session.ingest(fake.poll(0))
        with self.assertRaises(ValueError):
            session.command(1, 0)
        self.assertEqual(fake.writes, [])

    def test_report_directory_and_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            for args in (["--port", "FAKE", "--profile", "uart", "--report-dir", directory],
                         ["--simulate", "--profile", "uart", "--report-dir", directory],
                         ["--port", "FAKE", "--profile", "uart", "--timeout", "nan", "--report-dir", directory]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    bench.main(args)


if __name__ == "__main__":
    unittest.main()

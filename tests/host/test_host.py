import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("host", ROOT / "tools/host/arducore_host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
GOOD = {"state": 1, "dist": 34.3, "temp": 25.4, "alarm": False, "profile": 0}


class HostTests(unittest.TestCase):
    def test_every_command_data_pair(self):
        for cmd in range(256):
            for data in range(256):
                self.assertEqual(host.frame(cmd, data), bytes((2, cmd, data, cmd ^ data, 3)))
        for bad in (-1, 256, True, 1.0, "1"):
            with self.assertRaises(ValueError):
                host.frame(bad)

    def test_fragmented_stream(self):
        line = json.dumps(GOOD).encode() + b"\r\n"
        stream = b"ArduCore v0.8 READY\r\n" + line + b"broken\n" + line
        decoder = host.LineDecoder()
        events = []
        for byte in stream:
            events.extend(decoder.feed(bytes((byte,))))
        self.assertEqual([e[0] for e in events], ["banner", "telemetry", "invalid", "telemetry"])
        self.assertEqual(events[1][1], GOOD)

    def test_size_limit_and_invalid_unicode_recovery(self):
        decoder = host.LineDecoder(8)
        self.assertEqual(decoder.feed(b"x" * 10000)[0][0], "invalid")
        self.assertLessEqual(len(decoder.pending), 8)
        self.assertEqual(decoder.feed(b"\n\xff\n")[0][0], "invalid")
        decoder = host.LineDecoder()
        events = decoder.feed(b'{"state":NaN}\n' + json.dumps(GOOD).encode() + b"\n")
        self.assertEqual([e[0] for e in events], ["invalid", "telemetry"])

    def test_validation_and_legacy(self):
        legacy = dict(GOOD)
        del legacy["profile"]
        self.assertEqual(host.telemetry(json.dumps(legacy)), legacy)
        self.assertIn("legacy", host.display(host.event("telemetry", legacy)))
        for key, value in (("state", True), ("dist", True), ("temp", float("nan")),
                           ("temp", float("inf")), ("profile", 6), ("state", 5),
                           ("rx_errors", -1), ("alarm", 0), ("dist", -2), ("temp", 151)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                host.telemetry(json.dumps(dict(GOOD, **{key: value})))
        invalid = dict(GOOD, dist=-1, temp=-1)
        self.assertIn("dist=-- temp=--", host.display(host.event("telemetry", invalid)))

    def test_demo_never_opens_port_and_log_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            log = pathlib.Path(directory) / "events.jsonl"
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(host.main(["--demo", "--log", str(log)]), 0)
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(events), 4)
            self.assertEqual(events[0]["type"], "demo")
            self.assertIn("+00:00", events[0]["time"])

    def test_arguments_and_missing_port(self):
        for args in ([], ["--demo", "--port", "X"], ["--demo", "mode", "alarm"],
                     ["--demo", "--duration", "nan"], ["--demo", "--duration", "-1"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                host.main(args)

    def test_receive_deadline_and_partial_reads(self):
        wire = json.dumps(GOOD).encode() + b"\n"
        connection = mock.Mock()
        connection.read.side_effect = [wire[:8], wire[8:], b""]
        output = []
        clock = iter((0, 0, 0.1, 0.2, 1.0))
        self.assertEqual(host.receive(connection, 1, output.append, lambda: next(clock)), 1)
        self.assertEqual(output[0]["data"], GOOD)

    def test_software_serial_loopback(self):
        try:
            import serial
        except ImportError:
            self.skipTest("pyserial not installed")
        # loop:// is an in-process software transport, never a physical port.
        with serial.serial_for_url("loop://", timeout=0.01, write_timeout=0.1) as connection:
            payload = host.frame(1, 3)
            self.assertEqual(connection.write(payload), 5)
            self.assertEqual(connection.read(5), payload)
            wire = json.dumps(GOOD).encode() + b"\r\n"
            connection.write(wire)
            decoder = host.LineDecoder()
            self.assertEqual(decoder.feed(connection.read(len(wire))), [("telemetry", GOOD)])

    def test_console_keeps_one_connection_and_quits(self):
        connection = mock.Mock()
        connection.write.return_value = 5
        connection.read.return_value = b""
        lines = iter(("mode alarm", "nonsense", "status", "quit"))
        output = []
        host.receive(connection, 0, output.append, commands=lambda: next(lines))
        self.assertEqual(connection.write.call_count, 2)
        self.assertEqual([item["type"] for item in output], ["sent", "invalid", "sent"])
        self.assertEqual(host.console_command("reset")[1], host.frame(255))

    def test_partial_write_and_disconnect_are_reported(self):
        import serial
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.write.return_value = 2
        with mock.patch.object(serial, "serial_for_url", return_value=connection), \
             mock.patch.object(host.time, "sleep"), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(host.main(["--port", "FAKE", "status"]), 1)
        self.assertIn("Incomplete command write", errors.getvalue())
        with mock.patch.object(serial, "serial_for_url", side_effect=serial.SerialException("Disconnected")), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(host.main(["--port", "FAKE", "monitor"]), 1)
        self.assertIn("Disconnected", errors.getvalue())

    def test_command_cli_reports_sent_without_ack_claim(self):
        import serial
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.write.return_value = 5
        with mock.patch.object(serial, "serial_for_url", return_value=connection), \
             mock.patch.object(host.time, "sleep"), \
             mock.patch.object(host, "receive", return_value=1), \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(host.main(["--port", "FAKE", "mode", "alarm"]), 0)
        connection.write.assert_called_once_with(b"\x02\x01\x03\x02\x03")
        self.assertIn("no acknowledgement", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

"""Tests of release ELF instructions/peripherals under simavr, no bootloader."""
import os
import unittest
from bridge import Device

RUNNER = os.environ.get("ARDUCORE_SIM_RUNNER")
ELF = os.environ.get("ARDUCORE_SIM_ELF")


@unittest.skipUnless(RUNNER and ELF, "Set ARDUCORE_SIM_RUNNER and ARDUCORE_SIM_ELF")
class AvrTests(unittest.TestCase):
    def setUp(self):
        self.device = Device(RUNNER, ELF)
        self.device.run(1.3)
        self.assertEqual(self.device.latest()["state"], 1)

    def tearDown(self):
        self.device.close()

    def test_adc_and_distance_interrupts(self):
        reading = self.device.latest()
        self.assertAlmostEqual(reading["dist"], 34.3, delta=0.2)
        self.assertAlmostEqual(reading["temp"], 25, delta=0.6)
        initial = self.device.metrics()
        self.device.exchange("temp 400")
        self.device.run(0.8)
        self.assertEqual(self.device.latest()["state"], 3)
        self.assertAlmostEqual(self.device.latest()["temp"], 40, delta=0.6)
        self.assertGreater(self.device.metrics()["adc_triggers"], initial["adc_triggers"])
        self.device.exchange("temp 250")
        self.device.run(0.8)
        self.assertEqual(self.device.latest()["state"], 1)

    def test_uart_modes_and_pwm_waveform(self):
        initial = self.device.metrics()
        self.assertLess(abs(initial["period_min"] / 16 - 20000), 2)
        self.assertLess(abs(initial["period_max"] / 16 - 20000), 2)
        self.assertLess(abs(initial["width_min"] / 16 - 1000), 2)
        self.device.command(1, 3)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 3)
        self.device.exchange("clear_metrics")
        self.device.run(0.15)
        alarm = self.device.metrics()
        self.assertEqual(alarm["buzzer"], 1)
        self.assertEqual(alarm["ocr1a"], 4000)
        self.assertLess(abs(alarm["width_min"] / 16 - 2000), 2)
        self.assertLess(abs(alarm["width_max"] / 16 - 2000), 2)
        self.assertLess(abs(alarm["period_min"] / 16 - 20000), 2)
        self.assertLess(abs(alarm["period_max"] / 16 - 20000), 2)
        self.device.command(1, 0)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 0)
        self.assertEqual(self.device.metrics()["buzzer"], 0)

    def test_sensor_fault_and_explicit_recovery(self):
        self.device.exchange("echo 0")
        self.device.run(1)
        self.assertEqual(self.device.latest()["state"], 4)
        self.assertEqual(self.device.latest()["dist"], -1)
        self.device.command(255)
        self.device.run(0.6)
        self.assertEqual(self.device.latest()["state"], 4)
        self.device.exchange("echo 2000")
        self.device.run(1)
        self.assertEqual(self.device.latest()["state"], 4)
        self.device.command(255)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 1)

    def test_bad_frame_then_valid_command(self):
        self.device.exchange("rx 0201030209")
        self.device.run(0.6)
        self.assertEqual(self.device.latest()["state"], 1)
        self.device.command(1, 3)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 3)

    def test_uart_framing_error_discards_partial_command(self):
        self.device.exchange("rx 020103")
        self.device.exchange("fe 2")
        self.device.exchange("rx 03")
        self.device.run(0.6)
        self.assertEqual(self.device.latest()["state"], 1)
        self.assertGreaterEqual(self.device.latest()["rx_errors"], 1)
        self.device.command(1, 3)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 3)

    def test_watchdog_reset_after_injected_hang(self):
        initial = self.device.metrics()
        self.device.exchange("hang")
        self.device.run(3.3)
        after = self.device.metrics()
        self.assertEqual(after["boots"], initial["boots"] + 1)
        elapsed = (after["last_boot_cycle"] - initial["cycles"]) / 16000000
        self.assertGreater(elapsed, 1.8)
        self.assertLess(elapsed, 2.2)
        self.assertEqual(self.device.latest()["state"], 4)
        self.assertTrue(self.device.latest()["reset_flags"] & 8)
        # Deliberately no Uno bootloader in this test; MCUSR visibility differs.
        self.device.run(0.7)
        self.device.command(255)
        self.device.run(0.7)
        self.assertEqual(self.device.latest()["state"], 1)


if __name__ == "__main__":
    unittest.main()

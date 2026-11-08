#!/usr/bin/env python3
"""Seeded accelerated soak of the production ELF, without hardware or GPU."""
import argparse
import hashlib
import json
import pathlib
import random
import time
from bridge import Device, host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--elf", required=True)
    parser.add_argument("--minutes", type=int, default=60, help="Simulated minutes, not wall time")
    parser.add_argument("--seed", type=int, default=42517)
    parser.add_argument("--report", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 1440:
        parser.error("--minutes must be in 1..1440")
    rng = random.Random(args.seed)
    started = time.monotonic()
    checks = 0
    with Device(args.runner, args.elf) as device:
        device.run(1.3)
        initial = device.metrics()
        for minute in range(args.minutes):
            cycle_start = device.metrics()["cycles"]
            def state(expected):
                nonlocal checks
                actual = device.latest()
                assert actual["state"] == expected, (minute, expected, actual)
                checks += 1
            # Alarm and hysteresis from actual emulated ADC/PCINT inputs.
            device.exchange("echo 1000"); device.run(0.7); state(3)
            device.exchange("echo 2000"); device.run(0.7); state(1)
            device.exchange("temp 400"); device.run(0.7); state(3)
            device.exchange("temp 250"); device.run(0.7); state(1)
            # Latched loss, refused reset, restored health, explicit recovery.
            device.exchange("echo 0"); device.run(0.8); state(4)
            device.command(255); device.run(0.6); state(4)
            device.exchange("echo 2000"); device.run(1); state(4)
            device.command(255); device.run(0.7); state(1)
            # Noise excluding STX cannot create a complete frame by itself.
            noise = bytes(rng.choice([x for x in range(256) if x != 2]) for _ in range(64))
            device.exchange("rx " + noise.hex())
            device.exchange("rx 0201030209") # Good checksum, bad ETX: no command.
            device.run(0.6); state(1)
            # Every command goes over the emulator UART and host frame encoder.
            for _ in range(12):
                mode = rng.choice([0, 1, 2, 3])
                device.command(1, mode)
                device.command(3)
                device.run(0.18)
                state(mode)
            device.command(1, 1)
            device.run(0.6); state(1)
            # Deliberate request burst faster than telemetry TX capacity.
            device.exchange("rx " + (host.frame(3) * 40).hex())
            device.run(0.7); state(1)
            elapsed = (device.metrics()["cycles"] - cycle_start) / 16000000
            device.run(max(0, 60 - elapsed))
            state(1)
            metrics = device.metrics()
            assert metrics["boots"] == initial["boots"], "Unexpected watchdog/reset during traffic"
            assert device.latest()["rx_errors"] == 0, "Loss at paced, line-rate UART input"
            assert device.latest()["tx_dropped"] > 0, "Status flood did not exercise TX backpressure"
            checks += 3
            print(f"Completed simulated minute {minute + 1}/{args.minutes}", flush=True)
        final = device.metrics()
        result = {"kind": "simavr_instruction_soak", "seed": args.seed,
                  "requested_simulated_minutes": args.minutes,
                  "firmware_sha256": hashlib.sha256(pathlib.Path(args.elf).read_bytes()).hexdigest(),
                  "runner_sha256": hashlib.sha256(pathlib.Path(args.runner).read_bytes()).hexdigest(),
                  "simulated_seconds": final["cycles"] / 16000000,
                  "wall_seconds": round(time.monotonic() - started, 3),
                  "assertions": checks, "telemetry_lines": len(device.records),
                  "final_telemetry": device.latest(), "metrics": final,
                  "hardware_accessed": False, "gpu_used": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""All-profile release ELF scenarios plus observed stack/headroom, CPU-only."""
import argparse
import hashlib
import json
from pathlib import Path
from bridge import Device, host

PROFILES = ("full", "uart", "distance", "temperature", "buzzer", "servo")


def exercise(runner, elf, name, minimum_gap):
    identity = PROFILES.index(name)
    distance = name in ("full", "distance")
    temperature = name in ("full", "temperature")
    buzzer = name in ("full", "buzzer")
    servo = name in ("full", "servo")
    checks = 0
    with Device(runner, elf) as device:
        def state(expected):
            nonlocal checks
            # A periodic line may have been queued before the command. Allow
            # the 500 ms schedule plus complete 9600-baud transmission to finish.
            for _ in range(15):
                if device.latest()["state"] == expected:
                    break
                device.run(0.1)
            actual = device.latest()
            assert actual["profile"] == identity, actual
            assert actual["state"] == expected, (name, expected, actual)
            assert actual["alarm"] == (expected in (3, 4)), actual
            if not distance:
                assert actual["dist"] == -1, actual
            if not temperature:
                assert actual["temp"] == -1, actual
            checks += 1
        device.run(1.3); state(1)
        initial = device.metrics()
        assert initial["boots"] == 1
        assert initial["adc_irq_enabled"] == int(temperature)
        assert initial["pcint_enabled"] == int(distance)
        assert bool(initial["ddrb"] & 2) == servo
        assert bool(initial["ddrd"] & 0x80) == buzzer
        assert bool(initial["ddrd"] & 0x10) == distance
        if not servo:
            assert initial["pulses"] == 0
        if not temperature:
            assert initial["adc_triggers"] == 0
        device.command(1, 3); device.run(0.7); state(3)
        alarm = device.metrics()
        assert alarm["buzzer"] == int(buzzer)
        if servo:
            assert alarm["ocr1a"] == 4000
            device.exchange("clear_metrics"); device.run(0.15)
            waveform = device.metrics()
            for key, expected in (("width_min", 2000), ("width_max", 2000),
                                  ("period_min", 20000), ("period_max", 20000)):
                assert abs(waveform[key] / 16 - expected) < 2, waveform
        device.command(1, 0); device.run(0.6); state(0)
        assert device.metrics()["buzzer"] == 0
        device.command(1, 1); device.run(0.6); state(1)
        device.exchange("echo 1000"); device.run(0.7); state(3 if distance else 1)
        device.exchange("echo 2000"); device.run(0.7); state(1)
        device.exchange("temp 450"); device.run(0.7); state(3 if temperature else 1)
        device.exchange("temp 250"); device.run(0.7); state(1)
        device.exchange("echo 0"); device.exchange("temp 0"); device.run(0.9)
        fault = 4 if distance or temperature else 1
        state(fault)
        device.command(255); device.run(0.6); state(fault)
        device.exchange("echo 2000"); device.exchange("temp 250"); device.run(1)
        state(fault)
        device.command(255); device.run(0.7); state(1)
        # UART TX and RX IRQs overlap ADC/PCINT/Timer0 and JSON formatting.
        device.exchange("rx " + (host.frame(3) * 160).hex()); device.run(0.7); state(1)
        assert device.latest()["rx_errors"] == 0
        assert device.latest()["tx_dropped"] > 0
        for _ in range(12):
            device.exchange("fe 255")
            device.command(3)
        device.run(0.7); state(1)
        assert device.latest()["rx_errors"] >= 12
        # Simulator-only diagnostic injection, to exercise widest counter text.
        # No arbitrary memory write interface and no release file modification.
        device.exchange("max_counters")
        device.command(3); device.run(0.7); state(1)
        assert all(device.latest()[key] == 65535 for key in ("rx_errors", "tx_dropped", "rejected"))
        device.exchange("echo 23260"); device.exchange("temp 1490"); device.run(0.8)
        state(3 if temperature else 1)
        if distance:
            assert device.latest()["dist"] > 390
        if temperature:
            assert device.latest()["temp"] > 140
        device.exchange("echo 2000"); device.exchange("temp 250"); device.run(0.8); state(1)
        memory = device.memory()
        assert memory["static_bytes"] + memory["observed_stack_bytes"] + memory["minimum_gap_bytes"] == 2048
        assert memory["watermark_untouched_bytes"] >= memory["minimum_gap_bytes"]
        assert memory["minimum_gap_bytes"] >= minimum_gap, (name, memory)
        assert device.metrics()["boots"] == 1
        return {"profile": name, "profile_id": identity, "state_checkpoints": checks,
                "elf_sha256": hashlib.sha256(Path(elf).read_bytes()).hexdigest(),
                "hex_sha256": hashlib.sha256(Path(elf).with_suffix('.hex').read_bytes()).hexdigest(),
                "telemetry_lines": len(device.records), "memory": memory,
                "metrics": device.metrics(), "final_telemetry": device.latest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--elf-dir", type=Path, required=True, help="Contains full/, uart/, etc. build directories")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--minimum-gap", type=int, default=512, help="Observed regression budget, not a worst-case proof")
    args = parser.parse_args()
    if not 1 <= args.minimum_gap <= 2048:
        parser.error("--minimum-gap must be 1..2048")
    results = []
    for name in PROFILES:
        results.append(exercise(args.runner, args.elf_dir / name / "arducore.ino.elf", name, args.minimum_gap))
        print(name + ": passed; " + json.dumps(results[-1]["memory"]), flush=True)
    report = {"kind": "all_profile_instruction_and_stack_scenarios", "minimum_gap_budget": args.minimum_gap,
              "runner_sha256": hashlib.sha256(Path(args.runner).read_bytes()).hexdigest(),
              "profiles": results, "hardware_accessed": False, "gpu_used": False,
              "scope": "Observed instruction-boundary SP and unused-SRAM watermark; not exhaustive WCET/stack proof"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

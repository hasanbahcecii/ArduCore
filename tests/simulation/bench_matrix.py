#!/usr/bin/env python3
"""Run the real bench CLI against all six virtual ELF profiles."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from bridge import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--elf-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=False)
    for profile in ("full", "uart", "distance", "temperature", "buzzer", "servo"):
        target = args.report_dir / profile
        subprocess.run([sys.executable, str(ROOT / "tools/host/bench.py"), "--simulate", "--actuate",
                        "--runner", args.runner, "--elf-dir", str(args.elf_dir), "--profile", profile,
                        "--report-dir", str(target)], check=True)
        report = json.loads((target / "report.json").read_text())
        assert report["status"] == "simulated_checks_passed" and not report["hardware_verified"]
        assert report["cleanup"] == "idle_confirmed_by_telemetry"


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build all Uno profiles and package checksummed artifacts. Never uploads."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROFILES = ("full", "uart", "distance", "temperature", "buzzer", "servo")


def run(argv):
    return subprocess.check_output(argv, cwd=ROOT, text=True, stderr=subprocess.STDOUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v0.8.0")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "build/releases")
    parser.add_argument("--config-file", type=pathlib.Path)
    parser.add_argument("--allow-dirty", action="store_true", help="Development package, explicitly recorded in manifest")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.version):
        parser.error("Version must be a simple artifact label")
    status = run(["git", "status", "--porcelain"])
    if status and not args.allow_dirty:
        parser.error("Commit source changes first, or explicitly use --allow-dirty")
    cli_args = ["--config-file", str(args.config_file.resolve())] if args.config_file else []
    cli_version = json.loads(run(["arduino-cli", "version", "--format", "json"]))
    if cli_version.get("VersionString") != "1.5.1":
        parser.error("Release build requires Arduino CLI 1.5.1")
    platforms = json.loads(run(["arduino-cli", "core", "list", "--format", "json", *cli_args]))
    installed = {p["id"]: p.get("installed_version") for p in platforms.get("platforms", [])}
    if installed.get("arduino:avr") != "1.8.6":
        parser.error("Release build requires installed arduino:avr@1.8.6")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    name = "ArduCore-" + args.version
    archive = output / (name + ".zip")
    if archive.exists():
        parser.error("Refusing to overwrite " + str(archive))
    with tempfile.TemporaryDirectory(prefix="arducore-package-") as scratch:
        scratch = pathlib.Path(scratch)
        tree = scratch / name
        source = tree / "source"
        source.mkdir(parents=True)
        # Include tracked source; development-only mode also captures untracked
        # non-ignored source and records that this is not a clean release.
        tracked = run(["git", "ls-files", "-z"]).split("\0")
        if args.allow_dirty:
            tracked += run(["git", "ls-files", "--others", "--exclude-standard", "-z"]).split("\0")
        for relative in sorted(set(tracked) - {""}):
            original = ROOT / relative
            if original.is_file():
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
        manifest = {"version": args.version, "firmware_banner": "ArduCore v0.8 READY",
                    "source_commit": run(["git", "rev-parse", "HEAD"]).strip(),
                    "dirty": bool(status), "source_status": status.splitlines(),
                    "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "arduino_cli": "1.5.1", "avr_core": "1.8.6", "fqbn": "arduino:avr:uno",
                    "servo_min_us": os.environ.get("ARDUCORE_SERVO_MIN_US", "1000"),
                    "servo_max_us": os.environ.get("ARDUCORE_SERVO_MAX_US", "2000"),
                    "hardware_verified": False, "profiles": {}, "files": {}}
        for profile in PROFILES:
            build = scratch / ("build-" + profile)
            command = [str(ROOT / "tools/build_firmware.sh"), profile, *cli_args,
                       "--build-path", str(build)]
            log = run(command)
            target = tree / "firmware" / profile
            target.mkdir(parents=True)
            for suffix in ("hex", "elf"):
                shutil.copy2(build / ("arducore.ino." + suffix), target)
            (target / "build.log").write_text(log)
            flash = re.search(r"Sketch uses (\d+) bytes", log)
            ram = re.search(r"Global variables use (\d+) bytes", log)
            if not flash or not ram:
                raise RuntimeError("Could not parse compiler size summary")
            manifest["profiles"][profile] = {"id": PROFILES.index(profile),
                                              "flash": int(flash[1]), "static_ram": int(ram[1])}
            print(f"Packaged {profile}: {flash[1]} flash, {ram[1]} RAM", flush=True)
        (tree / "README.txt").write_text(
            "ArduCore Uno software-validated firmware bundle. Hardware unverified.\n"
            "Choose the correct profile; full requires both sensors.\n"
            "No bootloader image is included. These files do not upload themselves.\n"
            "Read source/docs/bench-testing.md before a later hardware session.\n"
            "manifest.json identifies source, toolchain, profile IDs and file hashes.\n")
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                manifest["files"][str(path.relative_to(tree))] = hashlib.sha256(path.read_bytes()).hexdigest()
        (tree / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary = output / (name + ".zip.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(tree.rglob("*")):
                    if path.is_file():
                        bundle.write(path, str(path.relative_to(scratch)))
            # Same-directory hard link publishes the complete file atomically
            # and refuses to replace any existing artifact.
            os.link(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n")
    print(archive)
    print("SHA-256 " + checksum)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.output)
    except OSError as exc:
        raise SystemExit(str(exc))

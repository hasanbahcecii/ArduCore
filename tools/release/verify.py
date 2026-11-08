#!/usr/bin/env python3
"""Verify an ArduCore ZIP's checksum and complete manifest without extracting."""
import argparse
import hashlib
import json
import pathlib
import re
import stat
import zipfile


def verify(archive, allow_dirty=False):
    archive = pathlib.Path(archive)
    sidecar = archive.with_suffix(".zip.sha256").read_text().split()
    if len(sidecar) != 2 or sidecar[1] != archive.name:
        raise ValueError("Malformed archive checksum file")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != sidecar[0]:
        raise ValueError("Archive SHA-256 mismatch")
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [item.filename for item in members]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive paths")
        if sum(item.file_size for item in members) > 64 * 1024 * 1024:
            raise ValueError("Unexpectedly large firmware bundle")
        for item in members:
            path = pathlib.PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                raise ValueError("Unsafe archive path")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unexpected symlink in archive")
        roots = {pathlib.PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError("Expected one bundle root")
        prefix = roots.pop() + "/"
        manifest_name = prefix + "manifest.json"
        manifest = json.loads(bundle.read(manifest_name))
        if manifest["dirty"] and not allow_dirty:
            raise ValueError("Development bundle contains uncommitted source")
        if not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]):
            raise ValueError("Invalid source commit")
        if manifest["hardware_verified"] is not False:
            raise ValueError("Unexpected hardware verification claim")
        profiles = ("full", "uart", "distance", "temperature", "buzzer", "servo")
        if set(manifest["profiles"]) != set(profiles):
            raise ValueError("Missing build profile")
        expected = {manifest_name}
        for relative, digest in manifest["files"].items():
            name = prefix + relative
            expected.add(name)
            if hashlib.sha256(bundle.read(name)).hexdigest() != digest:
                raise ValueError("Payload SHA-256 mismatch: " + relative)
        if set(names) != expected:
            raise ValueError("Unmanifested or missing archive members")
        for profile in profiles:
            if manifest["profiles"][profile]["id"] != profiles.index(profile):
                raise ValueError("Profile ID mismatch")
            for suffix in ("elf", "hex"):
                required = prefix + f"firmware/{profile}/arducore.ino.{suffix}"
                if required not in expected:
                    raise ValueError("Missing firmware artifact")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=pathlib.Path)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    try:
        manifest = verify(args.archive, args.allow_dirty)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc))
    print(f"Verified {manifest['version']} from {manifest['source_commit']}; six profiles; hardware unverified")


if __name__ == "__main__":
    main()

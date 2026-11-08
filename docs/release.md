# Firmware bundle preparation

The bundle builder compiles all six profiles and packages HEX, ELF, build logs,
source and a manifest. It never opens a serial device, uploads firmware, creates
a Git tag, publishes a GitHub release, or pushes Git history.

```sh
python3 tools/release/package.py --version v0.8.0
python3 tools/release/verify.py build/releases/ArduCore-v0.8.0.zip
```

Requires Arduino CLI 1.5.1 and installed AVR Core 1.8.6; no Servo library.
--config-file selects an isolated Arduino CLI installation; --output chooses
the destination (default build/releases, ignored by Git). Source must be clean
and committed by default. --allow-dirty explicitly labels a development-only
bundle and records Git status; it is not used for the final release artifact.
Existing archives are never overwritten. Do not use a version label as proof
that a matching Git tag exists: the manifest records the actual source commit.

The ZIP contains firmware/<profile>/arducore.ino.hex and .elf, without bootloader
images, plus source/, README.txt and manifest.json. The manifest includes source
commit/dirty status, build time, CLI/core versions, profile IDs, pulse bounds,
flash/RAM sizes and SHA-256 for every payload file (excluding the manifest
itself). A separate .zip.sha256 checks integrity of the complete archive
when obtained from a trusted source; hashes are not a digital signature.

The default label v0.8.0 corresponds to firmware banner ArduCore v0.8 READY.
Hardware status is always unverified. Use docs/bench-testing.md later to select
the correct profile; a partial-test image must not be mistaken for full.

The manual Build firmware bundle GitHub Actions workflow produces downloadable
workflow artifacts. It does not create a GitHub release. CI generation does not
replace the native/instruction/host test workflows or physical validation.

The verifier checks the outer archive checksum, every manifest payload hash,
complete profile artifacts and IDs, clean-source status and archive member
paths without extracting. Test it with `python3 -m unittest discover -s
tests/release -v`. Corrupted/missing/unmanifested content is rejected.

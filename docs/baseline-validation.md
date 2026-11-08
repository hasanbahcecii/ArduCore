# v0.6 baseline validation

Validation date: 2026-11-08. Target: arduino:avr:uno.

## Source preservation

The uploaded sketch is authoritative. Only Unicode comment separators, an em
dash, and an arrow were replaced with ASCII characters. Removing line comments
from both versions yields identical source text.

SHA-256 of the uploaded UTF-8 file:

`de5bc4cb13663e1aad0634a5692de15cf86bc00d11d535bc93a65714935bd1d6`

SHA-256 of the repository sketch:

`add3f1404995e0ac94500b6684de5d87c9c04b3303b3a9757886dc8fba6dcc78`

Both versions were separately cross-compiled. Their generated non-bootloader
Intel HEX files are byte-identical, with SHA-256:

`4e3c49805cbc7e6f2a184cd1191ed7aa166f9196d7bb7f223a7ba036c60975b7`

## Build

- Arduino CLI: 1.5.1.
- Arduino AVR Core: 1.8.6.
- Servo: 1.2.2.
- Compile: --fqbn arduino:avr:uno --warnings all.
- Flash: 6226 / 32256 bytes.
- Static RAM: 343 / 2048 bytes; this is not a stack-usage guarantee.
- Result: success for both sketches.
- Warnings: four unused-parameter warnings in Arduino core new.cpp.

## Repository checks

All repository text must remain ASCII. The repository contains a single sketch;
no duplicated source modules, generated binaries, or credentials are included.
The workflow installs pinned dependencies and fails if compilation fails.
Check the GitHub Actions run for the relevant commit for remote CI status;
configuration alone is not evidence of a passing run.

## Limits

No physical hardware tests or native unit tests were performed. Known firmware
defects remain unchanged, including parser dispatch before ETX validation,
silent buffer overflow, non-atomic echo data access, stale distance readings,
temperature validity handling, alarm transitions, and empty MANUAL/FAULT states.
Register mappings still require the datasheet confirmation noted in hardware.md.

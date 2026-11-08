#!/bin/sh
# Build the headless library and CLI only. No global install, apt, GPU or GUI.
set -eu
if [ "$#" -ne 1 ]; then echo "Usage: $0 source-directory" >&2; exit 2; fi
revision=f44723e8c42431136d5b4de81f789ded56d7e8fa
if [ ! -d "$1/.git" ]; then
  git clone --depth 1 --branch v1.8 https://github.com/buserror/simavr.git "$1"
fi
actual=$(git -C "$1" rev-parse HEAD)
if [ "$actual" != "$revision" ]; then
  echo "Expected simavr v1.8 ($revision), found $actual; use a fresh directory" >&2
  exit 2
fi
if ! command -v pkg-config >/dev/null || ! pkg-config --exists libelf; then
  echo "Install build prerequisites first: make, gcc, pkg-config, libelf-dev" >&2
  exit 2
fi
make -C "$1/simavr" -j2 CC="${CC:-/usr/bin/cc}"

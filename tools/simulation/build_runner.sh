#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then echo "Usage: $0 simavr-source output-runner" >&2; exit 2; fi
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
source=$(CDPATH= cd -- "$1" && pwd)
revision=$(git -C "$source" rev-parse HEAD)
if [ "$revision" != f44723e8c42431136d5b4de81f789ded56d7e8fa ]; then
  echo "Runner requires pinned simavr v1.8; see setup_simavr.sh" >&2; exit 2
fi
compiler=${CC:-/usr/bin/cc}
architecture=$("$compiler" -dumpmachine)
exec "$compiler" -std=c11 -Wall -Wextra -Werror \
  -I"$source/simavr/sim" "$root/tests/simulation/runner.c" \
  "$source/simavr/obj-$architecture/libsimavr.a" -lelf -lm -pthread -o "$2"

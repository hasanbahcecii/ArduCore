#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT HUP INT TERM
for source in "$root"/tests/native/*_test.cpp; do
  "${CXX:-g++}" -std=c++11 -Wall -Wextra -Werror -pedantic \
    -I"$root/tests/native/fakes" -fsanitize=undefined -fno-sanitize-recover=all \
    "$source" -o "$build/test"
  "$build/test"
done

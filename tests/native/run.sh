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
for profile in 1 2 3 4 5; do
  "${CXX:-g++}" -std=c++11 -Wall -Wextra -Werror -pedantic \
    -I"$root/tests/native/fakes" -DARDUCORE_PROFILE="$profile" \
    -fsanitize=undefined -fno-sanitize-recover=all \
    "$root/tests/native/firmware_integration_test.cpp" -o "$build/profile"
  "$build/profile"
done

#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
profile=${1:-full}
if [ "$#" -gt 0 ]; then shift; fi
case "$profile" in
  full) id=0 ;; uart) id=1 ;; distance) id=2 ;; temperature) id=3 ;;
  buzzer) id=4 ;; servo) id=5 ;;
  *) echo "Profile must be full, uart, distance, temperature, buzzer or servo" >&2; exit 2 ;;
esac
minimum=${ARDUCORE_SERVO_MIN_US:-1000}
maximum=${ARDUCORE_SERVO_MAX_US:-2000}
case "$minimum:$maximum" in *[!0-9:]*) echo "Servo limits must be integer microseconds" >&2; exit 2 ;; esac
exec arduino-cli compile --fqbn arduino:avr:uno --warnings all \
  --build-property "compiler.cpp.extra_flags=-DARDUCORE_PROFILE=$id -DARDUCORE_SERVO_MIN_US=$minimum -DARDUCORE_SERVO_MAX_US=$maximum" \
  "$@" "$root/firmware/arducore"

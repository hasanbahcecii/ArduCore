# UART protocol: v0.7

## Wire format

9600 baud, asynchronous 8N1, USART0. Every host command is five bytes:

```text
[STX 02][CMD][DATA][CMD XOR DATA][ETX 03]
```

There is no length, escaping, sequence number or acknowledgement. All byte
values, including 02 and 03, are legal in CMD/DATA/checksum positions.

| CMD | Name | DATA and effect |
| --- | --- | --- |
| 01 | SET_MODE | 0 IDLE, 1 AUTO, 2 MANUAL, 3 ALARM, 4 FAULT |
| 02 | SET_SPEED | Unsupported, increments rejected |
| 03 | GET_STATUS | DATA ignored; requests a current JSON line |
| FF | RESET | DATA ignored; logical AUTO/recovery request |

Unknown commands, invalid mode values and refused fault recovery increment
rejected. Bad framing/checksum has no command effect. Mode numbers are stable.

MANUAL has neutral outputs and no actuator command. Explicit ALARM is held
until another accepted mode/reset request. FAULT latches; only AUTO or RESET
after 500 ms continuous sensor validity releases it. RESET preserves sensor
history, fault latch when unhealthy, diagnostics and scheduling timestamps.
It resets the parser and discards pending RX bytes, including following frames
already queued in that batch. It does not reboot the MCU. Control rules execute
before outputs/telemetry, so unsafe inputs can immediately re-enter ALARM.

GET_STATUS example: `02 03 00 03 03` (hex).

## Validation and recovery

The parser scans a sliding five-byte window and dispatches only after checksum
and ETX validation. It finds the next complete valid frame after malformed
input without interpreting delimiter bytes inside payload as unconditional
restarts. Successful dispatch clears the window. An inter-byte gap >=100 ms
clears an incomplete window. Timestamps come from the RX ISR, not dequeue time.

Checksum XOR and unescaped delimiters cannot provide authentication or eliminate
accidental valid frames in arbitrary noise. There is no exact delivery guarantee
or duplicate suppression in this protocol.

The RX queue has 63 usable entries. Overflow or USART framing/overrun/parity
error increments rx_errors (saturating at 65535), drops subsequent bytes until
main-loop recovery, flushes queued RX and clears the parser. The host should
retry a complete command after overload has ceased. Frames pending at loss
can be discarded, including otherwise valid ones. At most 16 bytes are handled
per loop, so the control loop cannot be starved by unlimited host traffic.

## Device output

Startup banner: `ArduCore v0.7 READY` followed by CRLF.

JSON telemetry is requested every 500 ms and by GET_STATUS. Multiple requests
in a single loop produce one line. One request also resets the periodic timer.

```json
{"state":1,"dist":34.3,"temp":25.4,"alarm":false,"rx_errors":0,"tx_dropped":0,"rejected":0,"reset_flags":0}
```

- state: current mode number; alarm is true in ALARM or FAULT.
- dist: cm, -1.0 when unavailable/invalid or at least 300 ms old.
- temp: C, -1.0 when unavailable/invalid or at least 750 ms old.
- rx_errors: detected receive loss/error events, not a count of bad-checksum frames.
- tx_dropped: complete output messages skipped for insufficient TX space.
- rejected: unsupported commands, invalid modes or refused recovery requests.
- reset_flags: raw MCUSR observed before C++ initialization, best-effort only.

Numeric readings round to one decimal. Diagnostic counters saturate at 65535
and survive logical RESET, but reset with the MCU. MCUSR may already have been
cleared by the bootloader; reset_flags=0 means unknown, not confirmed power-on.

TX has 191 usable bytes. Each line queues whole or is skipped; it never blocks
waiting for room and never enqueues a partial line. tx_dropped becomes visible
in a later successfully queued line. Flooding GET_STATUS may drop responses;
there is no guaranteed per-command reply. At 9600 baud the nominal 500 ms output
rate is below link capacity.

Compatibility: the binary frame and original state/dist/temp/alarm keys remain.
Added diagnostic keys, v0.7 banner, -1.0 invalid readings and FAULT alarm policy
are intentional host-visible changes. Hosts must parse complete JSON lines and
allow extra keys.

// ArduCore v0.7 - software reliability release; hardware validation pending.
#include <Servo.h>
#include <stdio.h>
#include <util/atomic.h>
#include "FrameParser.h"
#include "EchoCapture.h"
#include "src/core/SystemCore.h"
#include "src/drivers/UartAvr.h"
#include "src/drivers/WatchdogAvr.h"

static const uint8_t TRIG_PIN = 4, ECHO_PIN = 6, BUZZER_PIN = 7, SERVO_PIN = 9;
EchoCapture echoCapture;
DistanceReading distanceReading;
arduc::TemperatureReading temperature;
arduc::SystemCore systemCore;
FrameParser parser;
Servo lockServo;
uint32_t lastTrigger = 0, lastTempRead = 0, lastTelemetry = 0;
uint16_t txDropped = 0, rejected = 0;
bool statusRequested = false;

void countSaturating(uint16_t &count) { if (count != UINT16_MAX) ++count; }

ISR(PCINT2_vect) {
  echoCapture.edge((PIND & _BV(PD6)) != 0, micros());
}

void triggerSensor() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { echoCapture.arm(micros()); }
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
}

void updateDistance() {
  uint32_t duration = 0, age = 0;
  bool ready;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { ready = echoCapture.take(micros(), duration, age); }
  if (ready) distanceReading.update(duration, millis() - age / 1000);
}

void updateTemperature(uint32_t now) {
  uint16_t sum = 0;
  for (uint8_t i = 0; i < 4; ++i) sum += analogRead(A0);
  temperature.update(sum, now);
}

void applyOutputs() {
  digitalWrite(BUZZER_PIN, systemCore.buzzer() ? HIGH : LOW);
  // Avoid rewriting the Servo command on every loop iteration.
  static int16_t previous = -1;
  const uint8_t degrees = systemCore.servoDegrees();
  if (previous != degrees) { lockServo.write(degrees); previous = degrees; }
}

void processCommand(uint8_t cmd, uint8_t data, uint32_t now) {
  switch (cmd) {
    case 0x01:
      if (!systemCore.mode(data, now)) countSaturating(rejected);
      break;
    case 0x03: statusRequested = true; break;
    case 0xFF:
      if (!systemCore.reset(now)) countSaturating(rejected);
      parser.reset();
      uart::discardRx(); // RESET is a boundary: queued commands are discarded.
      break;
    default: countSaturating(rejected); break; // Includes unsupported SET_SPEED.
  }
}

void receiveCommands(uint32_t now) {
  // Bounded work prevents RX traffic from starving sensing and watchdog service.
  for (uint8_t i = 0; i < 16; ++i) {
    if (uart::recover()) parser.reset();
    uart::Received item;
    if (!uart::read(item)) break;
    uint8_t cmd, data;
    if (parser.feed(item.byte, item.time, cmd, data)) processCommand(cmd, data, now);
  }
}

int16_t telemetryTenths(float value) {
  return value >= 0 ? static_cast<int16_t>(value * 10 + 0.5f) : -10;
}

void sendTelemetry(uint32_t now) {
  const int16_t dist = telemetryTenths(distanceReading.value(now));
  const int16_t temp = telemetryTenths(temperature.value(now));
  char line[160];
  const int length = snprintf(line, sizeof line,
      "{\"state\":%u,\"dist\":%d.%u,\"temp\":%d.%u,\"alarm\":%s,"
      "\"rx_errors\":%u,\"tx_dropped\":%u,\"rejected\":%u,\"reset_flags\":%u}\r\n",
      static_cast<unsigned>(systemCore.state()), dist / 10,
      static_cast<unsigned>(abs(dist % 10)), temp / 10,
      static_cast<unsigned>(abs(temp % 10)), systemCore.alarm() ? "true" : "false",
      static_cast<unsigned>(uart::errors()), static_cast<unsigned>(txDropped),
      static_cast<unsigned>(rejected), static_cast<unsigned>(resetFlags));
  if (length < 0 || static_cast<size_t>(length) >= sizeof line ||
      !uart::send(line, static_cast<size_t>(length))) countSaturating(txDropped);
}

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  lockServo.attach(SERVO_PIN);
  systemCore.begin(millis(), (resetFlags & _BV(WDRF)) != 0);
  applyOutputs();
  PCIFR = _BV(PCIF2);
  PCMSK2 = _BV(PCINT22);
  PCICR |= _BV(PCIE2);
  uart::begin();
  static const char banner[] = "ArduCore v0.7 READY\r\n";
  uart::send(banner, sizeof banner - 1);
  startWatchdog();
}

void loop() {
  uint32_t now = millis();
  updateDistance();
  if (static_cast<uint32_t>(now - lastTrigger) >= 100) {
    lastTrigger = now;
    triggerSensor();
  }
  if (static_cast<uint32_t>(now - lastTempRead) >= 200) {
    lastTempRead = now;
    updateTemperature(now);
  }
  // Refresh sensor health before commands, especially FAULT recovery requests.
  now = millis();
  systemCore.update(now, distanceReading.value(now), temperature.value(now), temperature.valid(now));
  receiveCommands(now);
  systemCore.update(now, distanceReading.value(now), temperature.value(now), temperature.valid(now));
  applyOutputs();
  if (statusRequested || static_cast<uint32_t>(now - lastTelemetry) >= 500) {
    statusRequested = false; // Multiple status requests in one loop are coalesced.
    lastTelemetry = now;
    sendTelemetry(now);
  }
  serviceWatchdog(); // Only after sensing, parsing and outputs have progressed.
}

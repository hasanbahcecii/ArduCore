#include <Arduino.h>
#include <assert.h>
#include <string>
#include <stdio.h>
uint8_t PIND, PCIFR, PCMSK2, PCICR, UCSR0A, UCSR0B, UCSR0C, UBRR0H, UBRR0L, UDR0;
uint8_t PRR, ADCSRA, ADCSRB, ADMUX, DIDR0;
uint16_t ADC;
uint8_t TCCR1A, TCCR1B, TIMSK1, PORTB, DDRB, TIFR1;
uint16_t TCNT1, ICR1, OCR1A;
uint32_t fakeMicros = 0;
int adcValue = 51, pins[20] = {}, watchdogServices = 0, triggerCount = 0;
uint8_t resetFlags = 0;
void startWatchdog() {}
void serviceWatchdog() { ++watchdogServices; }
#include "../../firmware/arducore/src/drivers/UartAvr.cpp"
#include "../../firmware/arducore/src/drivers/AdcAvr.cpp"
#include "../../firmware/arducore/src/drivers/ServoPwmAvr.cpp"
#include "../../firmware/arducore/arducore.ino"

static std::string drain() {
  std::string output;
  while (UCSR0B & _BV(UDRIE0)) {
    USART_UDRE_vect();
    if (UCSR0B & _BV(UDRIE0)) output += static_cast<char>(UDR0);
  }
  return output;
}
static void byte(uint8_t value) { UCSR0A = 0; UDR0 = value; USART_RX_vect(); }
static void command(uint8_t cmd, uint8_t data) {
  byte(2); byte(cmd); byte(data); byte(cmd ^ data); byte(3);
}
static void step(bool echo = true) {
  fakeMicros += 1000;
  const int previousTriggers = triggerCount;
  loop();
#if ARDUCORE_DISTANCE
  if (echo && triggerCount != previousTriggers) {
    fakeMicros += 100;
    PIND = _BV(PD6); PCINT2_vect();
    fakeMicros += 2000; // About 34 cm.
    PIND = 0; PCINT2_vect();
  }
#else
  (void)echo; (void)previousTriggers;
#endif
#if ARDUCORE_TEMPERATURE
  for (unsigned i = 0; ADCSRA & _BV(ADSC); ++i) {
    assert(i < 6);
    fakeMicros += 104;
    ADC = adcValue;
    ADCSRA &= ~_BV(ADSC);
    ADC_vect();
  }
#endif
  drain();
}
static void run(unsigned steps, bool echo = true) { while (steps--) step(echo); }
int main() {
  setup();
  assert(UBRR0L == 103 && UCSR0C == (_BV(UCSZ01) | _BV(UCSZ00)));
  assert(drain() == "ArduCore v0.8 READY\r\n");
#if ARDUCORE_PROFILE == 0
  run(1200);
  assert(systemCore.state() == arduc::AUTO && !pins[7] && OCR1A == servo_pwm::ticksForDegrees(0));
  adcValue = 90; // ~44 C.
  run(250);
  assert(systemCore.state() == arduc::ALARM && pins[7] && OCR1A == servo_pwm::ticksForDegrees(180));
  run(100);
  assert(systemCore.state() == arduc::ALARM); // Healthy distance cannot clear hot alarm.
  adcValue = 51;
  run(250);
  assert(systemCore.state() == arduc::AUTO);
  command(1, arduc::ALARM); step();
  assert(systemCore.state() == arduc::ALARM && pins[7]);
  command(1, arduc::MANUAL); step();
  assert(systemCore.state() == arduc::MANUAL && !pins[7] && OCR1A == servo_pwm::ticksForDegrees(0));
  run(500, false);
  assert(systemCore.state() == arduc::FAULT && pins[7] && OCR1A == servo_pwm::ticksForDegrees(0));
  command(255, 0); step(false);
  assert(systemCore.state() == arduc::FAULT);
  run(900);
  command(255, 0); step();
  assert(systemCore.state() == arduc::AUTO);
  command(1, arduc::ALARM); // Valid prefix followed by overload: flush whole RX queue.
  for (unsigned i = 0; i < 100; ++i) byte(0);
  step();
  assert(systemCore.state() == arduc::AUTO && uart::errors() > 0);
  command(1, arduc::IDLE); step();
  assert(systemCore.state() == arduc::IDLE);
  // Corrupted hardware byte must also invalidate partial frames.
  byte(2); byte(1); byte(3);
  UCSR0A = _BV(DOR0); UDR0 = 2; USART_RX_vect();
  byte(3); step();
  assert(systemCore.state() == arduc::IDLE);
  command(1, arduc::AUTO); step();
  assert(systemCore.state() == arduc::AUTO);
  command(255, 0);
  command(1, arduc::ALARM); // RESET discards queued later commands.
  step();
  assert(systemCore.state() == arduc::AUTO);
  // RX timestamps, not parsing time, enforce the inter-byte timeout.
  byte(2); byte(1);
  fakeMicros += 100000;
  byte(3); byte(2); byte(3); step();
  assert(systemCore.state() == arduc::AUTO);
  command(1, arduc::IDLE); step();
  assert(systemCore.state() == arduc::IDLE);
  // Non-blocking whole-message TX rejection, with no partial text queued.
  drain();
  std::string payload(190, 'x');
  assert(uart::send(payload.data(), payload.size()));
  assert(!uart::send("BAD", 3));
  assert(drain() == payload);
  sendTelemetry(millis());
  const std::string json = drain();
  assert(json.find("\"state\":0") != std::string::npos);
  assert(json.find("rx_errors") != std::string::npos);
  assert(json.substr(json.size() - 2) == "\r\n");
  run(800, false);
  adcValue = 0;
  run(250, false);
  sendTelemetry(millis());
  const std::string invalid = drain();
  assert(invalid.find("\"dist\":-1.0") != std::string::npos);
  assert(invalid.find("\"temp\":-1.0") != std::string::npos);
  // Worst-case diagnostics must still fit one whole TX message.
  errorCount = txDropped = rejected = UINT16_MAX;
  resetFlags = UINT8_MAX;
  sendTelemetry(millis());
  const std::string longest = drain();
  assert(!longest.empty() && longest.size() < 176);
  assert(longest.find("65535") != std::string::npos);
  countSaturating(txDropped);
  assert(txDropped == UINT16_MAX);
  assert(telemetryTenths(25.29f) == 253);
  assert(watchdogServices > 1000);
#else
  run(1200);
  assert(systemCore.state() == arduc::AUTO);
  assert(((PCICR & _BV(PCIE2)) != 0) == static_cast<bool>(ARDUCORE_DISTANCE));
  assert(((ADCSRA & _BV(ADEN)) != 0) == static_cast<bool>(ARDUCORE_TEMPERATURE));
  assert(((TCCR1A & _BV(COM1A1)) != 0) == static_cast<bool>(ARDUCORE_SERVO));
  sendTelemetry(millis());
  const std::string initial = drain();
  assert(initial.find("\"profile\":" + std::to_string(ARDUCORE_PROFILE)) != std::string::npos);
  if (!ARDUCORE_DISTANCE) assert(initial.find("\"dist\":-1.0") != std::string::npos);
  if (!ARDUCORE_TEMPERATURE) assert(initial.find("\"temp\":-1.0") != std::string::npos);
  command(1, arduc::ALARM); step();
  assert(systemCore.state() == arduc::ALARM);
  assert(pins[7] == static_cast<int>(ARDUCORE_BUZZER));
  if (ARDUCORE_SERVO) assert(OCR1A == servo_pwm::ticksForDegrees(180));
  command(1, arduc::IDLE); step();
  assert(!pins[7]);
  if (ARDUCORE_SERVO) assert(OCR1A == servo_pwm::ticksForDegrees(0));
#if ARDUCORE_DISTANCE || ARDUCORE_TEMPERATURE
  command(1, arduc::AUTO); step();
  adcValue = 0;
  run(900, false);
  assert(systemCore.state() == arduc::FAULT);
#else
  command(1, arduc::AUTO); run(900, false);
  assert(systemCore.state() == arduc::AUTO); // No fabricated sensor inputs required.
#endif
#endif
  puts("Firmware and UART integration tests passed (simulated peripherals)");
}

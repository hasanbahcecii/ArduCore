#ifndef ARDUCORE_ECHO_CAPTURE_H
#define ARDUCORE_ECHO_CAPTURE_H
#include <stdint.h>

// Caller must exclude interrupts while using this object outside the ISR.
class EchoCapture {
 public:
  static const uint32_t TIMEOUT_US = 30000;
  EchoCapture() : armed_(false), rising_(false), ready_(false),
                  triggered_(0), start_(0), duration_(0), finished_(0) {}
  void arm(uint32_t now) {
    triggered_ = now;
    armed_ = true;
    rising_ = ready_ = false;
  }
  void edge(bool high, uint32_t now) {
    if (!armed_) return;
    if (static_cast<uint32_t>(now - triggered_) >= TIMEOUT_US) {
      armed_ = false;
      return;
    }
    if (high && !rising_) {
      start_ = now;
      rising_ = true;
    } else if (!high && rising_) {
      duration_ = now - start_;
      finished_ = now;
      ready_ = true;
      armed_ = false;
    }
  }
  bool take(uint32_t now, uint32_t &duration) {
    uint32_t age;
    return take(now, duration, age);
  }
  bool take(uint32_t now, uint32_t &duration, uint32_t &age) {
    if (ready_ && static_cast<uint32_t>(now - triggered_) >= 300000)
      ready_ = false; // Never resurrect a delayed result as a fresh reading.
    if (ready_) {
      duration = duration_;
      age = now - finished_;
      ready_ = false;
      return true;
    }
    if (armed_ && static_cast<uint32_t>(now - triggered_) >= TIMEOUT_US)
      armed_ = false;
    return false;
  }
 private:
  volatile bool armed_, rising_, ready_;
  volatile uint32_t triggered_, start_, duration_, finished_;
};

class DistanceReading {
 public:
  static const uint32_t MAX_AGE_MS = 300;
  DistanceReading() : cm_(-1.0f), updated_(0) {}
  void update(uint32_t pulse, uint32_t now) {
    const float cm = pulse * 0.0343f / 2.0f;
    cm_ = (cm > 0.0f && cm < 400.0f) ? cm : -1.0f;
    updated_ = now;
  }
  float value(uint32_t now) const {
    return static_cast<uint32_t>(now - updated_) < MAX_AGE_MS ? cm_ : -1.0f;
  }
 private:
  float cm_;
  uint32_t updated_;
};
#endif

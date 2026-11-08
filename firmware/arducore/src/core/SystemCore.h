#ifndef ARDUCORE_SYSTEM_CORE_H
#define ARDUCORE_SYSTEM_CORE_H
#include <stdint.h>

namespace arduc {
enum State { IDLE, AUTO, MANUAL, ALARM, FAULT };
class SystemCore {
 public:
  SystemCore() : state_(AUTO), forcedAlarm_(false), fault_(false),
                 healthy_(false), healthySince_(0), boot_(0) {}
  void begin(uint32_t now, bool watchdogReset) {
    boot_ = now;
    fault_ = watchdogReset;
    forcedAlarm_ = healthy_ = false;
    state_ = fault_ ? FAULT : AUTO;
  }
  void update(uint32_t now, float distance, float temp, bool tempValid) {
    const bool valid = distance > 0 && tempValid;
    if (valid && !healthy_) healthySince_ = now;
    healthy_ = valid;
    if (!valid && state_ != IDLE &&
        static_cast<uint32_t>(now - boot_) >= 1000) fault_ = true;
    if (fault_) { state_ = FAULT; return; }
    if (state_ == AUTO && ((distance > 0 && distance < 20) ||
                          (tempValid && temp > 35))) state_ = ALARM;
    if (state_ == ALARM && !forcedAlarm_ && valid &&
        distance >= 25 && temp <= 33) state_ = AUTO;
  }
  bool mode(uint8_t requested, uint32_t now) {
    if (requested > FAULT) return false;
    if (requested == FAULT) { fault_ = true; state_ = FAULT; return true; }
    if (fault_) {
      if (requested != AUTO || !healthy_ ||
          static_cast<uint32_t>(now - healthySince_) < 500) return false;
      fault_ = false;
    }
    state_ = static_cast<State>(requested);
    forcedAlarm_ = state_ == ALARM;
    return true;
  }
  bool reset(uint32_t now) { return mode(AUTO, now); }
  State state() const { return state_; }
  bool alarm() const { return state_ == ALARM || state_ == FAULT; }
  bool buzzer() const { return alarm(); }
  uint8_t servoDegrees() const { return state_ == ALARM ? 180 : 0; }
 private:
  State state_;
  bool forcedAlarm_, fault_, healthy_;
  uint32_t healthySince_, boot_;
};

class TemperatureReading {
 public:
  TemperatureReading() : celsius_(-1), updated_(0), valid_(false) {}
  void update(uint16_t sum, uint32_t now) {
    // Four 10-bit readings; nominal 5 V AVcc and 10 mV/C LM35.
    celsius_ = sum * (500.0f / (4.0f * 1023.0f));
    valid_ = sum > 0 && sum <= 1227; // Application range (0,150] C.
    updated_ = now;
  }
  bool valid(uint32_t now) const {
    return valid_ && static_cast<uint32_t>(now - updated_) < 750;
  }
  float value(uint32_t now) const { return valid(now) ? celsius_ : -1.0f; }
 private:
  float celsius_;
  uint32_t updated_;
  bool valid_;
};
}
#endif

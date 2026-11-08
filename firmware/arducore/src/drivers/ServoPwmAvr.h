#ifndef ARDUCORE_SERVO_PWM_AVR_H
#define ARDUCORE_SERVO_PWM_AVR_H
#include <stdint.h>
#ifndef ARDUCORE_SERVO_MIN_US
#define ARDUCORE_SERVO_MIN_US 1000
#endif
#ifndef ARDUCORE_SERVO_MAX_US
#define ARDUCORE_SERVO_MAX_US 2000
#endif
#if ARDUCORE_SERVO_MIN_US < 500 || ARDUCORE_SERVO_MAX_US > 2500 || ARDUCORE_SERVO_MIN_US >= ARDUCORE_SERVO_MAX_US
#error Servo bounds must be ordered within 500..2500 us
#endif
namespace servo_pwm {
static const uint16_t TOP = 39999; // 16 MHz / 8 / 40000 = 50 Hz.
inline uint16_t ticksForDegrees(uint8_t degrees) {
  if (degrees > 180) degrees = 180;
  const uint32_t ticks = 2UL * ARDUCORE_SERVO_MIN_US +
      (2UL * (ARDUCORE_SERVO_MAX_US - ARDUCORE_SERVO_MIN_US) * degrees + 90) / 180;
  return static_cast<uint16_t>(ticks);
}
void begin();
void writeDegrees(uint8_t degrees);
}
#endif

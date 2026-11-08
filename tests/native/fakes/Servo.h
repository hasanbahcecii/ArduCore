#include <Arduino.h>
class Servo {
 public:
  void attach(uint8_t) {}
  void write(uint8_t value) { servoPosition = value; }
};

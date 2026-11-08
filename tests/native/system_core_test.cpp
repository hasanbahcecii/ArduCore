#include "../../firmware/arducore/src/core/SystemCore.h"
#include <assert.h>
#include <stdio.h>
using namespace arduc;
int main() {
  SystemCore core;
  core.begin(0, false);
  core.update(0, -1, -1, false);
  assert(core.state() == AUTO);
  core.update(999, -1, -1, false);
  assert(core.state() == AUTO);
  core.update(1000, -1, -1, false);
  assert(core.state() == FAULT && core.buzzer() && core.servoDegrees() == 0);
  assert(!core.reset(1001) && !core.mode(IDLE, 1001));
  core.update(1100, 30, 25, true);
  assert(!core.reset(1599));
  assert(core.reset(1600));
  core.update(1600, 30, 36, true);
  assert(core.state() == ALARM && core.servoDegrees() == 180);
  core.update(1700, 100, 36, true); // Distance alone cannot clear temperature alarm.
  assert(core.state() == ALARM);
  core.update(1800, 24, 32, true);
  assert(core.state() == ALARM);
  core.update(1900, 25, 33, true);
  assert(core.state() == AUTO && !core.alarm());
  core.update(2000, 19, 25, true);
  assert(core.state() == ALARM);
  assert(core.mode(IDLE, 2000));
  assert(!core.alarm() && !core.buzzer() && core.servoDegrees() == 0);
  assert(core.mode(MANUAL, 2100));
  assert(!core.alarm() && core.servoDegrees() == 0);
  assert(core.mode(ALARM, 2200));
  core.update(2300, 100, 25, true);
  assert(core.state() == ALARM); // Explicit alarm is held until a mode/reset command.
  assert(core.reset(2300));
  core.update(2400, -1, 25, true);
  assert(core.state() == FAULT);
  core.update(2500, 100, 25, true);
  core.update(2900, -1, 25, true);
  core.update(3000, 100, 25, true);
  assert(!core.reset(3400)); // Health must be continuous.
  assert(core.reset(3500));
  assert(!core.mode(255, 3500));
  core.begin(UINT32_MAX - 100, true);
  assert(core.state() == FAULT);
  core.update(UINT32_MAX - 100, 100, 25, true);
  assert(!core.reset(398));
  assert(core.reset(399));
  core.begin(UINT32_MAX - 100, false);
  core.update(898, -1, -1, false);
  assert(core.state() == AUTO);
  core.update(899, -1, -1, false);
  assert(core.state() == FAULT);

  TemperatureReading temp;
  assert(!temp.valid(0));
  temp.update(4 * 51 + 3, 1); // Fractional ADC average is preserved.
  assert(temp.value(1) > 25.29f && temp.value(1) < 25.30f);
  assert(temp.valid(750) && !temp.valid(751));
  temp.update(0, 800);
  assert(!temp.valid(800));
  temp.update(4092, 900);
  assert(!temp.valid(900));
  temp.update(1227, 950);
  assert(temp.valid(950));
  temp.update(1228, 960);
  assert(!temp.valid(960));
  temp.update(200, UINT32_MAX - 100);
  assert(temp.valid(648) && !temp.valid(649));
  puts("System core and temperature tests passed");
}

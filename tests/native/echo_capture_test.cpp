#include "../../firmware/arducore/EchoCapture.h"
#include <assert.h>
#include <stdio.h>

int main() {
  EchoCapture echo;
  uint32_t pulse = 123;
  echo.edge(false, 10);
  assert(!echo.take(20, pulse));
  echo.arm(100);
  echo.edge(false, 110); // Falling edge without a rising edge is ignored.
  assert(!echo.take(120, pulse));
  echo.edge(true, 200);
  echo.edge(true, 300); // Duplicate rising edge must not restart timing.
  echo.edge(false, 1200);
  assert(echo.take(1300, pulse) && pulse == 1000);
  assert(!echo.take(1400, pulse));
  echo.edge(true, 1500);
  echo.edge(false, 1600);
  assert(!echo.take(1700, pulse));
  echo.arm(2000);
  echo.edge(true, 2100);
  assert(!echo.take(32000, pulse)); // No falling edge: expire.
  echo.edge(false, 33000);
  assert(!echo.take(34000, pulse));
  echo.arm(40000);
  echo.edge(true, 40100);
  echo.edge(false, 70000); // Late edge rejected even without take().
  assert(!echo.take(70001, pulse));
  echo.arm(UINT32_MAX - 100);
  echo.edge(true, UINT32_MAX - 50);
  echo.edge(false, 949);
  assert(echo.take(1000, pulse) && pulse == 1000);
  echo.arm(UINT32_MAX - 100);
  assert(!echo.take(29899, pulse));
  echo.edge(true, 29900);
  echo.edge(false, 30000);
  assert(!echo.take(30001, pulse));

  echo.arm(1000000);
  echo.edge(true, 1000100);
  echo.edge(false, 1001100);
  uint32_t age;
  assert(echo.take(1101100, pulse, age) && age == 100000 && pulse == 1000);
  echo.arm(2000000);
  echo.edge(true, 2000100);
  echo.edge(false, 2001100);
  assert(!echo.take(2300000, pulse)); // Discard unconsumed old results.

  DistanceReading distance;
  assert(distance.value(0) == -1.0f);
  distance.update(1000, 10);
  assert(distance.value(309) > 17 && distance.value(309) < 18);
  assert(distance.value(310) == -1.0f);
  distance.update(0, 400);
  assert(distance.value(400) == -1.0f);
  distance.update(24000, 500);
  assert(distance.value(500) == -1.0f);
  distance.update(1000, 600);
  assert(distance.value(600) > 0); // Recover after invalid readings.
  distance.update(1000, UINT32_MAX - 100);
  assert(distance.value(198) > 0);
  assert(distance.value(199) == -1.0f);
  puts("Echo capture and distance tests passed");
}

#ifndef ARDUCORE_ADC_AVR_H
#define ARDUCORE_ADC_AVR_H
#include <stdint.h>
namespace adc {
struct Sample { uint16_t sum; uint32_t time; };
void begin();
bool request(); // Start a four-sample burst; never wait for conversion.
bool take(Sample &sample);
}
#endif

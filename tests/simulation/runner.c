// Headless instruction-level bridge. No physical I/O or graphics dependencies.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <inttypes.h>
#include "sim_avr.h"
#include "sim_elf.h"
#include "avr_uart.h"
#include "avr_adc.h"
#include "avr_ioport.h"

static avr_t *mcu;
static avr_irq_t *uart_in, *echo_pin, *adc_pin;
static uint32_t temperature_mv = 250, echo_us = 2000;
static uint8_t tx[65536];
static size_t tx_length;
static int trigger_high, pwm_high, buzzer, boots;
static avr_cycle_count_t rising_at, last_rise, width_min = UINT64_MAX, width_max;
static avr_cycle_count_t period_min = UINT64_MAX, period_max;
static unsigned pulses, adc_triggers;
static avr_cycle_count_t last_boot_cycle, total_cycles;
static uint32_t early_address = UINT32_MAX;

static void no_sleep(avr_t *avr, avr_cycle_count_t cycles) { (void)avr; (void)cycles; }
static void uart_output(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param;
  if (tx_length == sizeof tx) { fputs("TX capture overflow\n", stderr); exit(2); }
  tx[tx_length++] = value;
}
static void adc_trigger(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)value; (void)param;
  ++adc_triggers;
  avr_raise_irq(adc_pin, temperature_mv);
}
static avr_cycle_count_t echo_rise(avr_t *avr, avr_cycle_count_t when, void *param) {
  (void)avr; (void)when; (void)param; avr_raise_irq(echo_pin, 1); return 0;
}
static avr_cycle_count_t echo_fall(avr_t *avr, avr_cycle_count_t when, void *param) {
  (void)avr; (void)when; (void)param; avr_raise_irq(echo_pin, 0); return 0;
}
static void trigger(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param;
  const int high = value & 1;
  if (trigger_high && !high && echo_us) {
    avr_cycle_timer_register_usec(mcu, 100, echo_rise, NULL);
    avr_cycle_timer_register_usec(mcu, 100 + echo_us, echo_fall, NULL);
  }
  trigger_high = high;
}
static void pwm(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param;
  const int high = value & 1;
  // simavr resets its local cycle counter on MCU reset. Do not compare pin
  // timestamps across different boots or report unsigned underflow as a period.
  if (mcu->cycle < last_rise || mcu->cycle < rising_at) {
    last_rise = rising_at = 0;
    pwm_high = 0;
  }
  if (high && !pwm_high) {
    if (last_rise) {
      const avr_cycle_count_t period = mcu->cycle - last_rise;
      if (period < period_min) period_min = period;
      if (period > period_max) period_max = period;
    }
    last_rise = rising_at = mcu->cycle;
  } else if (!high && pwm_high) {
    const avr_cycle_count_t width = mcu->cycle - rising_at;
    if (width < width_min) width_min = width;
    if (width > width_max) width_max = width;
    ++pulses;
  }
  pwm_high = high;
}
static void buzzer_output(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param; buzzer = value & 1;
}
static void run_us(uint32_t us) {
  const avr_cycle_count_t until = total_cycles + (uint64_t)us * 16;
  while (total_cycles < until) {
    if (mcu->pc == early_address) { ++boots; last_boot_cycle = total_cycles; }
    const avr_cycle_count_t before = mcu->cycle;
    int state = avr_run(mcu);
    // Keep bridge time monotonic even when avr_reset resets mcu->cycle. The
    // reset instruction boundary contributes one cycle; timing tests tolerate
    // instruction/event granularity, not this as a physical reset measurement.
    total_cycles += mcu->cycle >= before ? mcu->cycle - before : 1;
    if (state == cpu_Done || state == cpu_Crashed) {
      fprintf(stderr, "AVR stopped: state=%d pc=%x\n", state, mcu->pc); exit(2);
    }
  }
}
static void flush_tx(void) {
  if (!tx_length) return;
  fputs("TX ", stdout);
  for (size_t i = 0; i < tx_length; ++i) printf("%02x", tx[i]);
  putchar('\n'); tx_length = 0;
}
int main(int argc, char **argv) {
  if (argc != 2) { fputs("Usage: runner firmware.elf\n", stderr); return 2; }
  elf_firmware_t firmware = {0};
  if (elf_read_firmware(argv[1], &firmware) < 0) return 2;
  for (uint32_t i = 0; i < firmware.symbolcount; ++i)
    if (!strcmp(firmware.symbol[i]->symbol, "_Z13earlyWatchdogv")) early_address = firmware.symbol[i]->addr;
  if (early_address == UINT32_MAX) { fputs("Missing watchdog boot hook\n", stderr); return 2; }
  mcu = avr_make_mcu_by_name("atmega328p");
  if (!mcu || avr_init(mcu) < 0) return 2;
  mcu->frequency = 16000000;
  mcu->vcc = mcu->avcc = mcu->aref = 5000;
  mcu->sleep = no_sleep;
  avr_load_firmware(mcu, &firmware);
  uint32_t flags = 0;
  avr_ioctl(mcu, AVR_IOCTL_UART_SET_FLAGS('0'), &flags);
  uart_in = avr_io_getirq(mcu, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_INPUT);
  echo_pin = avr_io_getirq(mcu, AVR_IOCTL_IOPORT_GETIRQ('D'), IOPORT_IRQ_PIN6);
  adc_pin = avr_io_getirq(mcu, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_ADC0);
  avr_irq_register_notify(avr_io_getirq(mcu, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT), uart_output, NULL);
  avr_irq_register_notify(avr_io_getirq(mcu, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_OUT_TRIGGER), adc_trigger, NULL);
  avr_irq_register_notify(avr_io_getirq(mcu, AVR_IOCTL_IOPORT_GETIRQ('D'), IOPORT_IRQ_PIN4), trigger, NULL);
  avr_irq_register_notify(avr_io_getirq(mcu, AVR_IOCTL_IOPORT_GETIRQ('B'), IOPORT_IRQ_PIN1), pwm, NULL);
  avr_irq_register_notify(avr_io_getirq(mcu, AVR_IOCTL_IOPORT_GETIRQ('D'), IOPORT_IRQ_PIN7), buzzer_output, NULL);
  avr_raise_irq(echo_pin, 0);
  puts("READY"); fflush(stdout);
  char line[8192];
  while (fgets(line, sizeof line, stdin)) {
    uint32_t value;
    if (sscanf(line, "run %u", &value) == 1 && value <= 60000000) run_us(value);
    else if (sscanf(line, "temp %u", &value) == 1 && value <= 5000) temperature_mv = value;
    else if (sscanf(line, "echo %u", &value) == 1 && value <= 100000) echo_us = value;
    else if (sscanf(line, "fe %u", &value) == 1 && value <= 255) {
      avr_raise_irq(uart_in, value | UART_INPUT_FE);
      run_us(1100);
    } else if (!strncmp(line, "rx ", 3)) {
      char *p = line + 3;
      while (*p && *p != '\n') {
        unsigned byte; int n;
        if (sscanf(p, "%2x%n", &byte, &n) != 1) return 2;
        avr_raise_irq(uart_in, byte);
        run_us(1100); // 9600 8N1: never overfill simulator's input FIFO.
        p += n;
      }
    } else if (!strcmp(line, "metrics\n")) {
      printf("METRICS {\"cycles\":%" PRIu64 ",\"boots\":%d,\"buzzer\":%d,\"pulses\":%u,"
             "\"last_boot_cycle\":%" PRIu64 ",\"ocr1a\":%u,\"top\":%u,\"width_min\":%" PRIu64 ",\"width_max\":%" PRIu64 ",\"period_min\":%" PRIu64 ","
             "\"period_max\":%" PRIu64 ",\"adc_triggers\":%u}\n",
             (uint64_t)total_cycles, boots, buzzer, pulses, (uint64_t)last_boot_cycle, (unsigned)(mcu->data[0x88] | (mcu->data[0x89] << 8)), (unsigned)(mcu->data[0x86] | (mcu->data[0x87] << 8)), (uint64_t)width_min, (uint64_t)width_max,
             (uint64_t)period_min, (uint64_t)period_max, adc_triggers);
    } else if (!strcmp(line, "clear_metrics\n")) {
      width_min = period_min = UINT64_MAX;
      width_max = period_max = 0;
      pulses = 0;
    } else if (!strcmp(line, "hang\n")) {
      // Fault injection in simulator RAM/flash only: strand PC in a spare-flash
      // infinite loop. The release ELF/HEX file is never changed.
      mcu->flash[0x7000] = 0xff; mcu->flash[0x7001] = 0xcf;
      mcu->pc = 0x7000;
    } else if (!strcmp(line, "quit\n")) break;
    else { fputs("Bad bridge command\n", stderr); return 2; }
    flush_tx(); puts("DONE"); fflush(stdout);
  }
  avr_terminate(mcu);
  return 0;
}

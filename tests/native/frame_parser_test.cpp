#include "../../firmware/arducore/FrameParser.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static unsigned feed(FrameParser &p, const uint8_t *bytes, unsigned n,
                     uint32_t start = 0) {
  unsigned count = 0;
  uint8_t cmd = 0, data = 0;
  for (unsigned i = 0; i < n; ++i)
    if (p.feed(bytes[i], start + i, cmd, data)) {
      assert(cmd == 1 && data == 2);
      ++count;
    }
  return count;
}
int main() {
  const uint8_t valid[] = {2, 1, 2, 3, 3};
  {
    FrameParser p;
    assert(feed(p, valid, 4) == 0); // No effect before terminator.
    uint8_t cmd, data;
    assert(p.feed(3, 4, cmd, data) && cmd == 1 && data == 2);
    assert(feed(p, valid, 5, 5) == 1);
  }
  {
    FrameParser p;
    const uint8_t bad[] = {2, 1, 2, 3, 9, 2, 1, 2, 3, 3};
    assert(feed(p, bad, sizeof bad) == 1);
  }
  {
    FrameParser p;
    const uint8_t bad[] = {2, 1, 2, 8, 3, 2, 1, 2, 3, 3};
    assert(feed(p, bad, sizeof bad) == 1);
  }
  {
    FrameParser p;
    const uint8_t restart[] = {2, 1, 2, 3, 2, 1, 2, 3, 3};
    assert(feed(p, restart, sizeof restart) == 1);
  }
  {
    FrameParser p;
    assert(feed(p, valid, 2) == 0);
    assert(feed(p, valid, 5, 101) == 1);
  }
  {
    FrameParser p;
    assert(feed(p, valid, 2, UINT32_MAX - 2) == 0);
    assert(feed(p, valid, 5, 100) == 1); // Clock wrap.
  }
  {
    FrameParser p;
    uint8_t cmd, data;
    const uint8_t embedded[] = {2, 2, 3, 1, 3};
    for (unsigned i = 0; i < 4; ++i)
      assert(!p.feed(embedded[i], i, cmd, data));
    assert(p.feed(embedded[4], 4, cmd, data));
    assert(cmd == 2 && data == 3); // Delimiters are valid payload bytes.
  }
  for (unsigned c = 0; c < 256; ++c) {
    for (unsigned d = 0; d < 256; ++d) {
      FrameParser p;
      uint8_t cmd, data;
      const uint8_t frame[] = {2, static_cast<uint8_t>(c), static_cast<uint8_t>(d),
                              static_cast<uint8_t>(c ^ d), 3};
      for (unsigned i = 0; i < 4; ++i) assert(!p.feed(frame[i], i, cmd, data));
      assert(p.feed(frame[4], 4, cmd, data));
      assert(cmd == c && data == d);
      p.reset();
      const uint8_t bad[] = {2, 1, 2, 3, 9};
      for (unsigned i = 0; i < 5; ++i) assert(!p.feed(bad[i], 10 + i, cmd, data));
      for (unsigned i = 0; i < 4; ++i) assert(!p.feed(frame[i], 20 + i, cmd, data));
      assert(p.feed(frame[4], 24, cmd, data) && cmd == c && data == d);
    }
  }
  puts("Frame parser tests passed (all 65536 command/data combinations)");
}

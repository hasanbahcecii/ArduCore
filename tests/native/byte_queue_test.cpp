#include "../../firmware/arducore/src/core/ByteQueue.h"
#include <assert.h>
#include <deque>
#include <stdio.h>
int main() {
  ByteQueue<uint8_t, 192> queue;
  std::deque<uint8_t> reference;
  uint32_t random = 17;
  for (unsigned i = 0; i < 200000; ++i) {
    random = random * 1664525UL + 1013904223UL;
    if ((random >> 16) % 11 == 0) { queue.clear(); reference.clear(); }
    else if ((random >> 16) & 1) {
      const uint8_t byte = random >> 24;
      const bool expected = reference.size() < 191;
      assert(queue.push(byte) == expected);
      if (expected) reference.push_back(byte);
    } else {
      uint8_t byte = 0;
      assert(queue.pop(byte) == !reference.empty());
      if (!reference.empty()) { assert(byte == reference.front()); reference.pop_front(); }
    }
    assert(queue.free() == 191 - reference.size());
  }
  queue.clear();
  for (unsigned i = 0; i < 191; ++i) assert(queue.push(i));
  assert(!queue.push(0));
  puts("Queue reference-model tests passed");
}

#ifndef ARDUCORE_BYTE_QUEUE_H
#define ARDUCORE_BYTE_QUEUE_H
#include <stdint.h>

// Single-producer, single-consumer queue; capacity N-1. AVR uint8_t indices
// are atomic. Payload is published only after its write completes.
template <typename T, uint8_t N>
class ByteQueue {
  static_assert(N > 1, "Queue requires at least two slots");
 public:
  ByteQueue() : head_(0), tail_(0) {}
  bool push(const T &item) {
    const uint8_t next = (head_ + 1) % N;
    if (next == tail_) return false;
    items_[head_] = item;
    asm volatile("" ::: "memory");
    head_ = next;
    return true;
  }
  bool pop(T &item) {
    if (head_ == tail_) return false;
    asm volatile("" ::: "memory");
    item = items_[tail_];
    asm volatile("" ::: "memory");
    tail_ = (tail_ + 1) % N;
    return true;
  }
  uint8_t free() const { return (tail_ + N - head_ - 1) % N; }
  void clear() { tail_ = head_; } // Consumer only; interrupt exclusion for reset.
 private:
  T items_[N];
  volatile uint8_t head_, tail_;
};
#endif

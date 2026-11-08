#ifndef ARDUCORE_FRAME_PARSER_H
#define ARDUCORE_FRAME_PARSER_H
#include <stdint.h>

// Sliding five-byte window: malformed input cannot hide the next complete
// frame. Delimiter bytes are legal payload bytes, so do not reset on every STX.
class FrameParser {
 public:
  static const uint32_t TIMEOUT_MS = 100;
  FrameParser() : used_(0), lastByte_(0) {}
  void reset() { used_ = 0; }
  bool feed(uint8_t byte, uint32_t now, uint8_t &cmd, uint8_t &data) {
    if (used_ && static_cast<uint32_t>(now - lastByte_) >= TIMEOUT_MS) reset();
    lastByte_ = now;
    if (used_ == 5) {
      for (uint8_t i = 0; i < 4; ++i) bytes_[i] = bytes_[i + 1];
      used_ = 4;
    }
    bytes_[used_++] = byte;
    if (used_ == 5 && bytes_[0] == 2 && bytes_[4] == 3 &&
        static_cast<uint8_t>(bytes_[1] ^ bytes_[2]) == bytes_[3]) {
      cmd = bytes_[1]; data = bytes_[2]; reset(); return true;
    }
    return false;
  }
 private:
  uint8_t bytes_[5], used_;
  uint32_t lastByte_;
};
#endif

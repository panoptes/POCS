#ifndef RESOURCES_ARDUINO_FILES_SHARED_CHAR_BUFFER_H
#define RESOURCES_ARDUINO_FILES_SHARED_CHAR_BUFFER_H

// CharBuffer stores characters and supports (minimal) parsing of
// the buffered characters.
template <uint8_t kBufferSize>
class CharBuffer {
  public:
    CharBuffer() {
      Reset();
    }
    void Reset() {
      write_cursor_ = read_cursor_ = 0;
    }
    // Appends a character to the buffer if there is room.
    // Returns true if there is room, else returns false.
    bool Append(char c) {
      if (write_cursor_ < kBufferSize) {
        buf_[write_cursor_++] = c;
        return true;
      }
      return false;
    }
    bool Empty() {
      return read_cursor_ >= write_cursor_;
    }
    char Next() {
      return buf_[read_cursor_++];
    }
    char Peek() {
      return buf_[read_cursor_];
    }
    // Parses the integer (uint8_t) in buffer starting at read_cursor_.
    // The integer must be non-negative (leading + or - are not supported).
    // Returns true if successful, false if there is not an integer at
    // read_cursor_ or if the integer is too big to fit into *output.
    bool ParseUInt8(uint8_t* output) {
      uint16_t v = 0;
      uint8_t len = 0;
      while (!Empty() && isdigit(Peek())) {
        char c = Next();
        v = v * 10 + c - '0';
        ++len;
        if (len > 3) {
          return false;
        }
      }
      if (len == 0 || v > 255) {
        return false;
      }
      *output = static_cast<uint8_t>(v);
      return true;
    }
    bool ParseName(char** name, uint8_t* name_len) {
      if (Empty() || !islower(Peek())) {
        return false;
      }
      *name = buf_ + read_cursor_;
      Next();
      uint8_t len = 1;
      while (!Empty()) {
        char c = Peek();
        if (islower(c) || isdigit(c) || c == '_') {
          Next();
          len++;
          continue;
        }
        break;
      }
      *name_len = len;
      return true;
    }
    bool MatchAndConsume(char c) {
      if (Empty() || Peek() != c) {
        return false;
      }
      Next();
      return true;
    }
    void WriteBuffer() {
      Serial.write(buf_, write_cursor_);
    }

  private:
    char buf_[kBufferSize];
    uint8_t write_cursor_;
    uint8_t read_cursor_;
};

#endif  // RESOURCES_ARDUINO_FILES_SHARED_CHAR_BUFFER_H

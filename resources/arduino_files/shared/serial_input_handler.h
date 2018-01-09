#ifndef RESOURCES_ARDUINO_FILES_SHARED_SERIAL_INPUT_HANDLER_H
#define RESOURCES_ARDUINO_FILES_SHARED_SERIAL_INPUT_HANDLER_H

#include <ctype.h>

// Support for accumulating a line of text input to be parsed by the sub-class.
// Only characters satisfying IsNewLine() or isprint() are acceptable.
template <uint8_t kBufferSize>
class SerialInputHandler {
  public:
    typedef void (*ProcessNumCommaNumFn)(uint8_t pin_num, uint8_t value);
    typedef void (*ProcessNameEqNumFn)(char* name, uint8_t name_len, uint8_t value);
    SerialInputHandler(ProcessNumCommaNumFn num_num_fn, ProcessNameEqNumFn name_num_fn)
        : num_num_fn_(num_num_fn), name_num_fn_(name_num_fn) {}

    void Handle() {
      while (AccumulateLine()) {
        wait_for_new_line_ = false;
        has_line_ = false;
        uint8_t pin_num;
        if (input_buffer_.ParseUInt8(&pin_num)) {
          uint8_t pin_status;
          if (input_buffer_.MatchAndConsume(',') &&
              input_buffer_.ParseUInt8(&pin_status) &&
              input_buffer_.Empty()) {
            num_num_fn_(pin_num, pin_status);
          } else {
            LineNotMatched(1);
          }
          input_buffer_.Reset();
          continue;
        }
        char* name = nullptr;
        uint8_t name_len = 0;
        if (input_buffer_.ParseName(&name, &name_len)) {
          uint8_t pin_status;
          if (input_buffer_.MatchAndConsume('=') &&
              input_buffer_.ParseUInt8(&pin_status) &&
              input_buffer_.Empty()) {
            name_num_fn_(name, name_len, pin_status);
          } else {
            LineNotMatched(2);
          }
          input_buffer_.Reset();
          continue;
        }
        LineNotMatched(0);
        input_buffer_.Reset();
      }
    }

  protected:
    bool AccumulateLine() {
      if (has_line_) {
        return true;
      }
      while (Serial && Serial.available() > 0) {
        int c = Serial.read();
        if (wait_for_new_line_) {
          if (IsNewLine(c)) {
            wait_for_new_line_ = false;
            input_buffer_.Reset();
          }
        } else if (IsNewLine(c)) {
          if (!input_buffer_.Empty()) {
            has_line_ = true;
            return true;
          }
        } else if (isblank(c)) {
          // Ignore space and tabs.
        } else if (isprint(c)) {
          if (!input_buffer_.Append(static_cast<char>(c))) {
            // Too full.
            wait_for_new_line_ = true;
          }
        } else {
          // Input is not an acceptable character.
          if (input_buffer_.Empty()) {
            // Ignore unacceptable characters at the start of a line. Choosing to do this because
            // we sometimes see garbage when first connecting.
          } else {
            wait_for_new_line_ = true;
          }
        }
      }
      return false;
    }

    // Allow the input line to end with NL, CR NL or CR.
    bool IsNewLine(int c) {
      return c == '\n' || c == '\r';
    }

    void LineNotMatched(int reason) {
      Serial.print("LINE NOT MATCHED, reason=");
      Serial.println(reason);
      Serial.print("LINE: \"");
      input_buffer_.WriteBuffer();
      Serial.println("\"");
    }

    // Buffer in which we're accumulating
    CharBuffer<kBufferSize> input_buffer_;

    const ProcessNumCommaNumFn num_num_fn_;
    const ProcessNameEqNumFn name_num_fn_;

    // Has a line been accumulated but not yet processed?
    bool has_line_{false};

    // Has invalid input been received, and we're now waiting for a new line before restarting
    // the process of accumulating a line?
    bool wait_for_new_line_{false};
};

#endif  // RESOURCES_ARDUINO_FILES_SHARED_SERIAL_INPUT_HANDLER_H

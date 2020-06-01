#include "interval_timer.h"

#include "Arduino.h"

IntervalTimer::IntervalTimer(millis_t interval_ms)
    : IntervalTimer(interval_ms, interval_ms) {}

IntervalTimer::IntervalTimer(millis_t interval_ms, millis_t remaining_ms)
    : last_time_(millis()), remaining_(remaining_ms), interval_(interval_ms) {}

void IntervalTimer::Reset() {
  last_time_ = millis();
  remaining_ = interval_;
}

bool IntervalTimer::HasExpired() {
  millis_t now = millis();
  millis_t elapsed;
  if (now < last_time_) {
    // We've had wrap around of the millisecond clock. When we do so, we keep things simple by
    // NOT tracking the time up to the wrap around (i.e. static_cast<millis_t>(-1LL) - last_time_).
    elapsed = now;
  } else {
    elapsed = now - last_time_;
  }
  last_time_ = now;

  if (remaining_ <= elapsed) {
    // All done. Compute amount of time in next interval that has been consumed.
    elapsed -= remaining_;
    if (elapsed >= interval_) {
      remaining_ = 1;
    } else {
      remaining_ = interval_ - elapsed;
    }
    return true;
  } else {
    remaining_ -= elapsed;
    return false;
  }
}

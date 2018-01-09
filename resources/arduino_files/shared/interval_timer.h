#ifndef RESOURCES_ARDUINO_FILES_SHARED_INTERVAL_TIMER_H
#define RESOURCES_ARDUINO_FILES_SHARED_INTERVAL_TIMER_H

// A simple repeating, count-down timer. Avoids problems with wrap-around
// by tracking the remaining time left rather than the absolute time.
class IntervalTimer {
  public:
    // The type returned by millis().
    typedef unsigned long millis_t;

    // Constructs a timer where the first expiration is in interval_ms, and
    // then every interval_ms after that.
    IntervalTimer(millis_t interval_ms);

    // Constructs a timer where the first expiration is in remaining_ms, and
    // then every interval_ms after that.
    IntervalTimer(millis_t interval_ms, millis_t remaining_ms);

    // Starts a new interval at the current time.
    void Reset();

    // Returns true if the current interval has expired, in which case a new interval is started.
    bool HasExpired();

  private:
    millis_t last_time_;
    millis_t remaining_;
    const millis_t interval_;
};

#endif  // RESOURCES_ARDUINO_FILES_SHARED_INTERVAL_TIMER_H

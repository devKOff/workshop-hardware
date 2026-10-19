#pragma once

#include <Arduino.h>
#include <cstdint>
#include "config.h"

namespace button_handler {

enum class ButtonEvent : uint8_t {
    NONE = 0,
    SHORT_PRESS,
    LONG_PRESS
};

enum class ButtonState : uint8_t {
    IDLE = 0,
    DEBOUNCE_PRESS,
    PRESSED,
    DEBOUNCE_RELEASE,
    LONG_PRESS_DETECTED
};

class ButtonHandler {
public:
    ButtonHandler(uint8_t pin = config::PIN_BUTTON,
                  uint8_t active_level = config::BUTTON_ACTIVE_LEVEL,
                  uint16_t debounce_ms = config::BUTTON_DEBOUNCE_MS,
                  uint16_t long_press_ms = config::BUTTON_LONG_PRESS_MS);

    void begin();
    void update();
    ButtonEvent getEvent();
    bool isPressed() const;
    uint32_t getPressDuration() const;

private:
    const uint8_t pin_;
    const uint8_t active_level_;
    const uint16_t debounce_ms_;
    const uint16_t long_press_ms_;

    ButtonState state_;
    ButtonEvent pending_event_;
    uint32_t last_change_time_;
    uint32_t press_start_time_;
    bool last_raw_state_;

    bool readRawState() const;
    void transitionTo(ButtonState new_state);
};

} // namespace button_handler
#include "button_handler.h"

namespace button_handler {

ButtonHandler::ButtonHandler(uint8_t pin, uint8_t active_level,
                             uint16_t debounce_ms, uint16_t long_press_ms)
    : pin_(pin), active_level_(active_level), debounce_ms_(debounce_ms),
      long_press_ms_(long_press_ms), state_(ButtonState::IDLE),
      pending_event_(ButtonEvent::NONE), last_change_time_(0),
      press_start_time_(0), last_raw_state_(!active_level) {}

void ButtonHandler::begin() {
    pinMode(pin_, INPUT_PULLUP);
    last_raw_state_ = readRawState();
    last_change_time_ = millis();
    state_ = ButtonState::IDLE;
    pending_event_ = ButtonEvent::NONE;
}

bool ButtonHandler::readRawState() const {
    return digitalRead(pin_) == active_level_;
}

void ButtonHandler::transitionTo(ButtonState new_state) {
    state_ = new_state;
    last_change_time_ = millis();
}

void ButtonHandler::update() {
    uint32_t now = millis();
    bool raw_state = readRawState();

    if (raw_state != last_raw_state_) {
        last_change_time_ = now;
        last_raw_state_ = raw_state;
    }

    switch (state_) {
        case ButtonState::IDLE:
            if (raw_state) {
                transitionTo(ButtonState::DEBOUNCE_PRESS);
            }
            break;

        case ButtonState::DEBOUNCE_PRESS:
            if (!raw_state) {
                transitionTo(ButtonState::IDLE);
            } else if (now - last_change_time_ >= debounce_ms_) {
                press_start_time_ = now;
                transitionTo(ButtonState::PRESSED);
            }
            break;

        case ButtonState::PRESSED:
            if (!raw_state) {
                transitionTo(ButtonState::DEBOUNCE_RELEASE);
            } else if (now - press_start_time_ >= long_press_ms_) {
                pending_event_ = ButtonEvent::LONG_PRESS;
                transitionTo(ButtonState::LONG_PRESS_DETECTED);
            }
            break;

        case ButtonState::DEBOUNCE_RELEASE:
            if (raw_state) {
                transitionTo(ButtonState::PRESSED);
            } else if (now - last_change_time_ >= debounce_ms_) {
                if (pending_event_ != ButtonEvent::LONG_PRESS) {
                    pending_event_ = ButtonEvent::SHORT_PRESS;
                }
                transitionTo(ButtonState::IDLE);
            }
            break;

        case ButtonState::LONG_PRESS_DETECTED:
            if (!raw_state) {
                transitionTo(ButtonState::DEBOUNCE_RELEASE);
            }
            break;
    }
}

ButtonEvent ButtonHandler::getEvent() {
    ButtonEvent event = pending_event_;
    pending_event_ = ButtonEvent::NONE;
    return event;
}

bool ButtonHandler::isPressed() const {
    return state_ == ButtonState::PRESSED || state_ == ButtonState::LONG_PRESS_DETECTED;
}

uint32_t ButtonHandler::getPressDuration() const {
    if (state_ == ButtonState::PRESSED || state_ == ButtonState::LONG_PRESS_DETECTED) {
        return millis() - press_start_time_;
    }
    return 0;
}

} // namespace button_handler
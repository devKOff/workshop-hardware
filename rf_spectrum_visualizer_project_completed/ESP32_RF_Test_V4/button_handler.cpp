#include "button_handler.h"
#include "Arduino.h"

namespace button {

ButtonHandler::ButtonHandler(const config::ButtonConfig& cfg)
    : config_(cfg), last_raw_state_(cfg.active_low), debounced_state_(cfg.active_low), last_debounced_state_(cfg.active_low) {
    pinMode(config_.pin, config_.active_low ? INPUT_PULLUP : INPUT);
}

void ButtonHandler::begin(PressCallback callback) {
    callback_ = callback;
    callback_registered_ = true;
    last_raw_state_ = readRawState();
    debounced_state_ = last_raw_state_;
    last_debounced_state_ = debounced_state_;
    last_change_time_ = millis();
}

void ButtonHandler::update() {
    bool raw = readRawState();
    uint32_t now = millis();

    if (raw != last_raw_state_) {
        last_change_time_ = now;
        last_raw_state_ = raw;
        return;
    }

    if (raw != debounced_state_ && (now - last_change_time_) >= config_.debounce_ms) {
        debounced_state_ = raw;
        if (!debounced_state_ && last_debounced_state_) {
            handlePress();
        }
        last_debounced_state_ = debounced_state_;
    }
}

bool ButtonHandler::isPressed() const {
    return !debounced_state_;
}

uint32_t ButtonHandler::getPressCount() const {
    return press_count_;
}

void ButtonHandler::resetPressCount() {
    press_count_ = 0;
}

bool ButtonHandler::readRawState() const {
    bool raw = digitalRead(config_.pin);
    return config_.active_low ? !raw : raw;
}

void ButtonHandler::handlePress() {
    press_count_++;
    if (callback_registered_ && callback_) {
        callback_();
    }
}

} // namespace button
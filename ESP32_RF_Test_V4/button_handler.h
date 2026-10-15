#pragma once

#include <cstdint>
#include <functional>
#include "config.h"

namespace button {

class ButtonHandler {
public:
    using PressCallback = std::function<void()>;

    explicit ButtonHandler(const config::ButtonConfig& cfg);
    ~ButtonHandler() = default;

    ButtonHandler(const ButtonHandler&) = delete;
    ButtonHandler& operator=(const ButtonHandler&) = delete;
    ButtonHandler(ButtonHandler&&) = delete;
    ButtonHandler& operator=(ButtonHandler&&) = delete;

    void begin(PressCallback callback);
    void update();
    bool isPressed() const;
    uint32_t getPressCount() const;
    void resetPressCount();

private:
    const config::ButtonConfig& config_;
    PressCallback callback_;
    bool last_raw_state_ = false;
    bool debounced_state_ = false;
    bool last_debounced_state_ = false;
    uint32_t last_change_time_ = 0;
    uint32_t press_count_ = 0;
    bool callback_registered_ = false;

    bool readRawState() const;
    void handlePress();
};

} // namespace button
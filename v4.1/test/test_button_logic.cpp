#include "test_button_logic.h"

static button_handler::ButtonHandler* btn = nullptr;

void simulateShortPress(uint32_t duration_ms) {
    mock_pin_state = false;
    mock_time += 10;
    btn->update();
    mock_time += duration_ms;
    btn->update();
}

void simulateLongPress(uint32_t duration_ms) {
    mock_pin_state = false;
    mock_time += 10;
    btn->update();
    mock_time += duration_ms;
    btn->update();
    // Advance time past long press threshold and update
    mock_time += 1000;
    btn->update();
}

void simulateRelease() {
    mock_pin_state = true;
    mock_time += 10;
    btn->update();
    mock_time += 50;
    btn->update();
}

void test_button_short_press() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    simulateShortPress(100);
    simulateRelease();
    button_handler::ButtonEvent evt = btn->getEvent();
    TEST_ASSERT_EQUAL(button_handler::ButtonEvent::SHORT_PRESS, evt);
    delete btn;
}

void test_button_long_press() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    simulateLongPress(1500);
    button_handler::ButtonEvent evt = btn->getEvent();
    TEST_ASSERT_EQUAL(button_handler::ButtonEvent::LONG_PRESS, evt);
    simulateRelease();
    delete btn;
}

void test_button_press_too_short() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    mock_pin_state = false;
    mock_time += 10;
    btn->update();
    mock_time += 30;
    btn->update();
    mock_pin_state = true;
    mock_time += 10;
    btn->update();
    mock_time += 50;
    btn->update();
    button_handler::ButtonEvent evt = btn->getEvent();
    TEST_ASSERT_EQUAL(button_handler::ButtonEvent::NONE, evt);
    delete btn;
}

void test_button_multiple_short_presses() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    for (int i = 0; i < 3; i++) {
        simulateShortPress(100);
        simulateRelease();
        button_handler::ButtonEvent evt = btn->getEvent();
        TEST_ASSERT_EQUAL(button_handler::ButtonEvent::SHORT_PRESS, evt);
    }
    delete btn;
}

void test_button_debounce_rejection() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    mock_pin_state = false;
    mock_time += 10;
    btn->update();
    mock_time += 20;
    mock_pin_state = true;
    btn->update();
    mock_time += 10;
    mock_pin_state = false;
    btn->update();
    mock_time += 100;
    btn->update();
    mock_pin_state = true;
    mock_time += 50;
    btn->update();
    button_handler::ButtonEvent evt = btn->getEvent();
    TEST_ASSERT_EQUAL(button_handler::ButtonEvent::NONE, evt);
    delete btn;
}

void test_button_is_pressed() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    TEST_ASSERT_FALSE(btn->isPressed());
    mock_pin_state = false;
    btn->update();  // Detect press at time 0
    mock_time += 60;
    btn->update();  // After 60ms, should be in PRESSED state
    TEST_ASSERT_TRUE(btn->isPressed());
    mock_pin_state = true;
    mock_time += 60;
    btn->update();
    TEST_ASSERT_FALSE(btn->isPressed());
    delete btn;
}

void test_button_press_duration() {
    btn = new button_handler::ButtonHandler(4, 0, 50, 1000);
    mock_time = 0;
    mock_pin_state = true;
    btn->begin();
    mock_pin_state = false;
    btn->update();  // Detect press at time 0
    mock_time += 60;
    btn->update();  // After 60ms, should be in PRESSED state
    // press_start_time is set to 60 (when entering PRESSED), so duration is 0 at this point
    TEST_ASSERT_UINT32_WITHIN(50, 0, btn->getPressDuration());
    mock_time += 200;
    btn->update();
    TEST_ASSERT_UINT32_WITHIN(50, 200, btn->getPressDuration());
    mock_pin_state = true;
    mock_time += 60;
    btn->update();
    TEST_ASSERT_EQUAL_UINT32(0, btn->getPressDuration());
    delete btn;
}
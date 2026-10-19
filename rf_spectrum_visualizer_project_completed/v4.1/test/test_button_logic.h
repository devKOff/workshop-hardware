#ifndef TEST_BUTTON_LOGIC_H
#define TEST_BUTTON_LOGIC_H

#include <unity.h>
#include "test_common.h"

void test_button_short_press();
void test_button_long_press();
void test_button_press_too_short();
void test_button_multiple_short_presses();
void test_button_debounce_rejection();
void test_button_is_pressed();
void test_button_press_duration();

#endif
#ifndef TEST_RADIO_CONTROLLER_H
#define TEST_RADIO_CONTROLLER_H

#include <unity.h>
#include "test_common.h"

void test_radio_constructor_defaults();
void test_radio_begin();
void test_radio_start_burst_before_init();
void test_radio_start_burst_invalid_channel();
void test_radio_start_burst_zero_packets();
void test_radio_start_burst_too_many_packets();
void test_radio_abort_burst_when_idle();
void test_radio_generate_random_channel_range();
void test_radio_state_transitions();

#endif
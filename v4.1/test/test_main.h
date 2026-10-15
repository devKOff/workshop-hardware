#ifndef TEST_MAIN_H
#define TEST_MAIN_H

#include <unity.h>
#include "test_common.h"

void test_main_full_packet_workflow();
void test_main_channel_frequency_consistency();
void test_main_button_event_enum_values();
void test_main_radio_state_enum_values();
void test_main_radio_error_enum_values();
void test_main_logger_levels();
void test_main_firmware_version_string();
void test_main_packet_magic_bytes();
void test_main_pipe_address();

#endif
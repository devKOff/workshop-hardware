#include <unity.h>
#include "test_config.h"
#include "test_button_logic.h"
#include "test_packet_protocol.h"
#include "test_radio_controller.h"
#include "test_main.h"

uint32_t mock_time = 0;
bool mock_pin_state = true;

uint32_t millis_mock() { return mock_time; }

void setUp() {}
void tearDown() {}

int main() {
    UNITY_BEGIN();

    RUN_TEST(test_config_channel_to_frequency_mapping);
    RUN_TEST(test_config_channel_validation);
    RUN_TEST(test_config_constants);
    RUN_TEST(test_config_rf_config);

    RUN_TEST(test_button_short_press);
    RUN_TEST(test_button_long_press);
    RUN_TEST(test_button_press_too_short);
    RUN_TEST(test_button_multiple_short_presses);
    RUN_TEST(test_button_debounce_rejection);
    RUN_TEST(test_button_is_pressed);
    RUN_TEST(test_button_press_duration);

    RUN_TEST(test_packet_size);
    RUN_TEST(test_packet_creation);
    RUN_TEST(test_packet_validation_valid);
    RUN_TEST(test_packet_validation_invalid_magic);
    RUN_TEST(test_packet_validation_invalid_version);
    RUN_TEST(test_packet_validation_invalid_channel);
    RUN_TEST(test_packet_validation_mismatched_frequency);
    RUN_TEST(test_packet_edge_channels);
    RUN_TEST(test_packet_sequence_increment);
    RUN_TEST(test_packet_structure_alignment);
    RUN_TEST(test_multiple_packets_same_burst);

    RUN_TEST(test_radio_constructor_defaults);
    RUN_TEST(test_radio_begin);
    RUN_TEST(test_radio_start_burst_before_init);
    RUN_TEST(test_radio_start_burst_invalid_channel);
    RUN_TEST(test_radio_start_burst_zero_packets);
    RUN_TEST(test_radio_start_burst_too_many_packets);
    RUN_TEST(test_radio_abort_burst_when_idle);
    RUN_TEST(test_radio_generate_random_channel_range);
    RUN_TEST(test_radio_state_transitions);

    RUN_TEST(test_main_full_packet_workflow);
    RUN_TEST(test_main_channel_frequency_consistency);
    RUN_TEST(test_main_button_event_enum_values);
    RUN_TEST(test_main_radio_state_enum_values);
    RUN_TEST(test_main_radio_error_enum_values);
    RUN_TEST(test_main_logger_levels);
    RUN_TEST(test_main_firmware_version_string);
    RUN_TEST(test_main_packet_magic_bytes);
    RUN_TEST(test_main_pipe_address);

    return UNITY_END();
}
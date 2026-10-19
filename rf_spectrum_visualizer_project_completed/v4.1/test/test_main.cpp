#include "test_main.h"

void test_main_full_packet_workflow() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 42);
    TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt));
    TEST_ASSERT_EQUAL_UINT32(2442, pkt.frequency_mhz);

    pkt.sequence = 100;
    pkt.channel = 100;
    pkt.frequency_mhz = config::channelToFrequencyMHz(100);
    TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt));
}

void test_main_channel_frequency_consistency() {
    for (uint8_t ch = 0; ch <= 125; ch++) {
        uint32_t freq = config::channelToFrequencyMHz(ch);
        TEST_ASSERT_EQUAL_UINT32(2400 + ch, freq);

        packet_protocol::TestPacket pkt;
        packet_protocol::createPacket(pkt, 1, 1, ch);
        TEST_ASSERT_EQUAL_UINT32(freq, pkt.frequency_mhz);
        TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt));
    }
}

void test_main_button_event_enum_values() {
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(button_handler::ButtonEvent::NONE));
    TEST_ASSERT_EQUAL_UINT8(1, static_cast<uint8_t>(button_handler::ButtonEvent::SHORT_PRESS));
    TEST_ASSERT_EQUAL_UINT8(2, static_cast<uint8_t>(button_handler::ButtonEvent::LONG_PRESS));
}

void test_main_radio_state_enum_values() {
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(radio_controller::RadioState::UNINITIALIZED));
    TEST_ASSERT_EQUAL_UINT8(1, static_cast<uint8_t>(radio_controller::RadioState::INITIALIZING));
    TEST_ASSERT_EQUAL_UINT8(2, static_cast<uint8_t>(radio_controller::RadioState::READY));
    TEST_ASSERT_EQUAL_UINT8(3, static_cast<uint8_t>(radio_controller::RadioState::TRANSMITTING));
    TEST_ASSERT_EQUAL_UINT8(4, static_cast<uint8_t>(radio_controller::RadioState::ERROR_STATE));
}

void test_main_radio_error_enum_values() {
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(radio_controller::RadioError::NONE));
    TEST_ASSERT_EQUAL_UINT8(1, static_cast<uint8_t>(radio_controller::RadioError::INIT_FAILED));
    TEST_ASSERT_EQUAL_UINT8(2, static_cast<uint8_t>(radio_controller::RadioError::WRITE_FAILED));
    TEST_ASSERT_EQUAL_UINT8(3, static_cast<uint8_t>(radio_controller::RadioError::INVALID_CHANNEL));
    TEST_ASSERT_EQUAL_UINT8(4, static_cast<uint8_t>(radio_controller::RadioError::TIMEOUT));
    TEST_ASSERT_EQUAL_UINT8(5, static_cast<uint8_t>(radio_controller::RadioError::HARDWARE_FAULT));
}

void test_main_logger_levels() {
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(logger::LogLevel::SILENT));
    TEST_ASSERT_EQUAL_UINT8(1, static_cast<uint8_t>(logger::LogLevel::ERROR));
    TEST_ASSERT_EQUAL_UINT8(2, static_cast<uint8_t>(logger::LogLevel::WARN));
    TEST_ASSERT_EQUAL_UINT8(3, static_cast<uint8_t>(logger::LogLevel::INFO));
    TEST_ASSERT_EQUAL_UINT8(4, static_cast<uint8_t>(logger::LogLevel::DEBUG));
    TEST_ASSERT_EQUAL_UINT8(5, static_cast<uint8_t>(logger::LogLevel::VERBOSE));
}

void test_main_firmware_version_string() {
    TEST_ASSERT_EQUAL_STRING("V4.1", config::FIRMWARE_VERSION);
    TEST_ASSERT_EQUAL_STRING("ESP32 Random-Channel RF Test Generator", config::PROJECT_NAME);
}

void test_main_packet_magic_bytes() {
    TEST_ASSERT_EQUAL_UINT32(0x45535034, packet_protocol::MAGIC_BYTES);
}

void test_main_pipe_address() {
    TEST_ASSERT_EQUAL_UINT32(0xE7E7E7E7, static_cast<uint32_t>(config::PIPE_ADDRESS & 0xFFFFFFFF));
    TEST_ASSERT_EQUAL_UINT32(0xE7, static_cast<uint32_t>(config::PIPE_ADDRESS >> 32));
}
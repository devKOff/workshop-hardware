#include "test_config.h"

void test_config_channel_to_frequency_mapping() {
    TEST_ASSERT_EQUAL_UINT32(2400, config::channelToFrequencyMHz(0));
    TEST_ASSERT_EQUAL_UINT32(2401, config::channelToFrequencyMHz(1));
    TEST_ASSERT_EQUAL_UINT32(2442, config::channelToFrequencyMHz(42));
    TEST_ASSERT_EQUAL_UINT32(2475, config::channelToFrequencyMHz(75));
    TEST_ASSERT_EQUAL_UINT32(2525, config::channelToFrequencyMHz(125));
}

void test_config_channel_validation() {
    TEST_ASSERT_TRUE(config::isValidChannel(0));
    TEST_ASSERT_TRUE(config::isValidChannel(42));
    TEST_ASSERT_TRUE(config::isValidChannel(125));
    TEST_ASSERT_FALSE(config::isValidChannel(126));
    TEST_ASSERT_FALSE(config::isValidChannel(255));
}

void test_config_constants() {
    TEST_ASSERT_EQUAL_UINT8(25, config::PIN_NRF_CE);
    TEST_ASSERT_EQUAL_UINT8(5, config::PIN_NRF_CSN);
    TEST_ASSERT_EQUAL_UINT8(4, config::PIN_BUTTON);
    TEST_ASSERT_EQUAL_UINT8(2, config::PIN_STATUS_LED);
    TEST_ASSERT_EQUAL_UINT16(50, config::BUTTON_DEBOUNCE_MS);
    TEST_ASSERT_EQUAL_UINT16(1000, config::BUTTON_LONG_PRESS_MS);
    TEST_ASSERT_EQUAL_UINT8(20, config::DEFAULT_PACKETS_PER_BURST);
    TEST_ASSERT_EQUAL_UINT32(0xE7E7E7E7, static_cast<uint32_t>(config::PIPE_ADDRESS & 0xFFFFFFFF));
    TEST_ASSERT_EQUAL_UINT32(0xE7, static_cast<uint32_t>(config::PIPE_ADDRESS >> 32));
    TEST_ASSERT_EQUAL_STRING("V4.1", config::FIRMWARE_VERSION);
}

void test_config_rf_config() {
    TEST_ASSERT_EQUAL_UINT8(2, config::RF_CRC_LENGTH);
}
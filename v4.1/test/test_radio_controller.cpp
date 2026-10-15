#include "test_radio_controller.h"

static radio_controller::RadioController* radio = nullptr;

void test_radio_constructor_defaults() {
    if (radio) delete radio;
    radio = new radio_controller::RadioController();
    TEST_ASSERT_EQUAL(radio_controller::RadioState::UNINITIALIZED, radio->getState());
    TEST_ASSERT_EQUAL(radio_controller::RadioError::NONE, radio->getLastError());
    TEST_ASSERT_EQUAL_UINT16(0, radio->getPacketsSent());
    TEST_ASSERT_EQUAL_UINT16(0, radio->getPacketsTotal());
    TEST_ASSERT_EQUAL_UINT8(0, radio->getCurrentChannel());
    TEST_ASSERT_EQUAL_UINT16(0, radio->getCurrentBurstId());
    TEST_ASSERT_FALSE(radio->isBusy());
    TEST_ASSERT_FALSE(radio->isHealthy());
}

void test_radio_begin() {
    radio->setMockEntropy(0);
    bool result = radio->begin();
    TEST_ASSERT_TRUE(result);
    TEST_ASSERT_EQUAL(radio_controller::RadioState::READY, radio->getState());
}

void test_radio_start_burst_before_init() {
    if (radio) delete radio;
    radio = new radio_controller::RadioController();
    bool result = radio->startBurst(42);
    TEST_ASSERT_FALSE(result);
    TEST_ASSERT_EQUAL(radio_controller::RadioError::INVALID_CHANNEL, radio->getLastError());
}

void test_radio_start_burst_invalid_channel() {
    radio->begin();
    bool result = radio->startBurst(200);
    TEST_ASSERT_FALSE(result);
    TEST_ASSERT_EQUAL(radio_controller::RadioError::INVALID_CHANNEL, radio->getLastError());
}

void test_radio_start_burst_zero_packets() {
    radio->begin();
    bool result = radio->startBurst(10, 0);
    TEST_ASSERT_FALSE(result);
}

void test_radio_start_burst_too_many_packets() {
    radio->begin();
    bool result = radio->startBurst(10, 300);
    TEST_ASSERT_FALSE(result);
}

void test_radio_abort_burst_when_idle() {
    radio->begin();
    radio->abortBurst();
    TEST_ASSERT_EQUAL(radio_controller::RadioState::READY, radio->getState());
}

void test_radio_generate_random_channel_range() {
    radio->begin();
    radio->setMockEntropy(0);
    for (int i = 0; i < 100; i++) {
        uint8_t ch = radio->generateRandomChannel();
        TEST_ASSERT_TRUE(config::isValidChannel(ch));
    }
}

void test_radio_state_transitions() {
    radio->begin();
    TEST_ASSERT_EQUAL(radio_controller::RadioState::READY, radio->getState());
    radio->end();
    TEST_ASSERT_EQUAL(radio_controller::RadioState::UNINITIALIZED, radio->getState());
}
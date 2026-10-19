#include "radio_controller.h"
#include "config.h"
#include "test_support.h"
#include <cassert>
#include <cstdio>

using namespace radio;
using namespace config;

void testMockInitSuccess() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    assert(radio.begin());
    assert(radio.getState() == RadioState::IDLE);
    radio.end();
    assert(radio.getState() == RadioState::UNINITIALIZED);
    printf("testMockInitSuccess: PASSED\n");
}

void testMockInitFailure() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setFailInit(true);
    radio.setStatusCallback([](const char*, bool){});

    assert(!radio.begin());
    assert(radio.getState() == RadioState::ERROR);
    printf("testMockInitFailure: PASSED\n");
}

void testMockChannelConfig() {
    RadioConfig cfg{};
    cfg.channel_min = 10;
    cfg.channel_max = 80;
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();

    assert(radio.startBurst(10, 1, 10, 10));
    assert(radio.getCurrentChannel() == 10);
    assert(radio.getState() == RadioState::BURST_IN_PROGRESS);
    radio.abortBurst();
    assert(radio.getState() == RadioState::IDLE);

    assert(radio.startBurst(80, 2, 10, 10));
    assert(radio.getCurrentChannel() == 80);
    radio.abortBurst();

    assert(!radio.startBurst(5, 3, 10, 10));
    assert(!radio.startBurst(90, 4, 10, 10));
    printf("testMockChannelConfig: PASSED\n");
}

void testMockBoundedPacketCount() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    radio.startBurst(42, 1, 5, 10);

    for (int i = 0; i < 3; ++i) {
        radio.update();
    }
    assert(radio.getPacketsSent() == 0);

    test_support::set_millis(0);
    while (test_support::millis() < 50) {
        test_support::advance_millis(10);
        radio.update();
    }
    assert(radio.getPacketsSent() == 5);
    assert(radio.getState() == RadioState::IDLE);
    printf("testMockBoundedPacketCount: PASSED\n");
}

void testMockBurstTermination() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    radio.startBurst(42, 1, 10, 10);

    radio.abortBurst();
    assert(radio.getState() == RadioState::IDLE);
    uint16_t sent_at_abort = radio.getPacketsSent();

    radio.update();
    assert(radio.getPacketsSent() == sent_at_abort);
    printf("testMockBurstTermination: PASSED\n");
}

void testMockTransmitFailures() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setFailSend(true);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    radio.startBurst(42, 1, 5, 10);

    for (int i = 0; i < 10; ++i) {
        radio.update();
    }
    assert(radio.getPacketsSent() == 0);
    printf("testMockTransmitFailures: PASSED\n");
}

void testMockRecoveryToIdle() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    radio.startBurst(42, 1, 5, 10);

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        test_support::advance_millis(10);
        radio.update();
    }
    assert(radio.getState() == RadioState::IDLE);

    radio.startBurst(43, 2, 3, 10);
    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        test_support::advance_millis(10);
        radio.update();
    }
    assert(radio.getState() == RadioState::IDLE);
    printf("testMockRecoveryToIdle: PASSED\n");
}

void testMockNoWritesAfterBurstComplete() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    radio.startBurst(42, 1, 2, 10);

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        test_support::advance_millis(10);
        radio.update();
    }
    uint16_t final_sent = radio.getPacketsSent();

    for (int i = 0; i < 10; ++i) {
        test_support::advance_millis(10);
        radio.update();
    }
    assert(radio.getPacketsSent() == final_sent);
    printf("testMockNoWritesAfterBurstComplete: PASSED\n");
}

void testMockNoTransmitOnConfigFail() {
    RadioConfig cfg{};
    cfg.channel_min = 50;
    cfg.channel_max = 10;
    MockRadioController radio(cfg);
    radio.setStatusCallback([](const char*, bool){});

    radio.begin();
    assert(!radio.startBurst(10, 1, 5, 10));
    assert(radio.getState() == RadioState::IDLE);
    printf("testMockNoTransmitOnConfigFail: PASSED\n");
}

void testMockSafeBehaviorAfterError() {
    RadioConfig cfg{};
    MockRadioController radio(cfg);
    radio.setFailInit(true);
    radio.setStatusCallback([](const char*, bool){});

    assert(!radio.begin());
    assert(radio.getState() == RadioState::ERROR);

    assert(!radio.startBurst(42, 1, 5, 10));
    radio.update();
    assert(radio.getState() == RadioState::ERROR);
    printf("testMockSafeBehaviorAfterError: PASSED\n");
}

void testChannelToFrequency() {
    assert(RadioController::channelToFrequencyMHz(0) == 2400);
    assert(RadioController::channelToFrequencyMHz(1) == 2401);
    assert(RadioController::channelToFrequencyMHz(42) == 2442);
    assert(RadioController::channelToFrequencyMHz(125) == 2525);
    printf("testChannelToFrequency: PASSED\n");
}

void testIsValidChannel() {
    RadioConfig cfg{};
    cfg.channel_min = 10;
    cfg.channel_max = 80;
    MockRadioController radio(cfg);

    assert(!radio.isValidChannel(5));
    assert(radio.isValidChannel(10));
    assert(radio.isValidChannel(45));
    assert(radio.isValidChannel(80));
    assert(!radio.isValidChannel(85));
    printf("testIsValidChannel: PASSED\n");
}

int main() {
    testMockInitSuccess();
    testMockInitFailure();
    testMockChannelConfig();
    testMockBoundedPacketCount();
    testMockBurstTermination();
    testMockTransmitFailures();
    testMockRecoveryToIdle();
    testMockNoWritesAfterBurstComplete();
    testMockNoTransmitOnConfigFail();
    testMockSafeBehaviorAfterError();
    testChannelToFrequency();
    testIsValidChannel();
    printf("\nAll radio controller tests PASSED\n");
    return 0;
}
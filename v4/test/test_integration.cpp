#include "radio_controller.h"
#include "button_handler.h"
#include "config.h"
#include "packet_protocol.h"
#include <cassert>
#include <cstdio>
#include <vector>

using namespace radio;
using namespace button;
using namespace config;
using namespace packet;

void testButtonEventToRadioBurst() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.status_callback_ = [](const char*, bool){};
    radio.begin();

    ButtonConfig bcfg{};
    bcfg.debounce_ms = 10;
    MockButtonHandler button(bcfg);

    uint32_t burst_count = 0;
    uint8_t last_channel = 0;

    button.begin([&]() {
        burst_count++;
        uint8_t channel = 10 + (burst_count % 50);
        last_channel = channel;
        radio.startBurst(channel, burst_count, 3, 5);
    });

    button.setRawState(false);
    button.setDebouncedState(false);
    button.setLastChangeTime(millis());

    for (int i = 0; i < 3; ++i) {
        button.update();
    }

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        radio.update();
    }
    assert(radio.getState() == RadioState::IDLE);
    assert(radio.getPacketsSent() == 3);
    assert(burst_count == 1);

    button.setRawState(true);
    button.setLastChangeTime(millis() + 100);
    button.update();

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        radio.update();
    }
    assert(radio.getState() == RadioState::IDLE);
    assert(radio.getPacketsSent() == 6);
    assert(burst_count == 2);
    assert(last_channel != 10 || burst_count == 1);
    printf("testButtonEventToRadioBurst: PASSED\n");
}

void testMultipleSequentialButtonPresses() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.status_callback_ = [](const char*, bool){};
    radio.begin();

    ButtonConfig bcfg{};
    bcfg.debounce_ms = 10;
    MockButtonHandler button(bcfg);

    std::vector<uint8_t> channels;
    button.begin([&]() {
        channels.push_back(20 + (channels.size() % 30));
        radio.startBurst(channels.back(), channels.size(), 2, 5);
    });

    button.setRawState(false);
    button.setDebouncedState(false);
    button.setLastChangeTime(millis());

    for (int press = 0; press < 5; ++press) {
        button.update();
        button.setRawState(true);
        button.setLastChangeTime(millis() + 50 + press * 100);
        button.update();

        while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
            radio.update();
        }
    }

    assert(channels.size() == 5);
    assert(radio.getState() == RadioState::IDLE);
    printf("testMultipleSequentialButtonPresses: PASSED\n");
}

void testRadioInitFailureHandling() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.setFailInit(true);
    radio.status_callback_ = [](const char*, bool){};

    assert(!radio.begin());
    assert(radio.getState() == RadioState::ERROR);

    ButtonConfig bcfg{};
    bcfg.debounce_ms = 10;
    MockButtonHandler button(bcfg);
    bool burst_attempted = false;
    button.begin([&]() {
        burst_attempted = true;
        radio.startBurst(42, 1, 5, 10);
    });

    button.setRawState(false);
    button.setDebouncedState(false);
    button.setLastChangeTime(millis());
    button.update();
    button.setRawState(true);
    button.setLastChangeTime(millis() + 100);
    button.update();

    assert(!burst_attempted || radio.getState() == RadioState::ERROR);
    printf("testRadioInitFailureHandling: PASSED\n");
}

void testRepeatedErrorAndRecovery() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.status_callback_ = [](const char*, bool){};
    radio.begin();

    ButtonConfig bcfg{};
    bcfg.debounce_ms = 10;
    MockButtonHandler button(bcfg);
    int burst_count = 0;

    button.begin([&]() {
        burst_count++;
        if (burst_count == 2) {
            radio.setFailSend(true);
        } else {
            radio.setFailSend(false);
        }
        radio.startBurst(42, burst_count, 3, 5);
    });

    button.setRawState(false);
    button.setDebouncedState(false);
    button.setLastChangeTime(millis());

    for (int press = 0; press < 3; ++press) {
        button.update();
        button.setRawState(true);
        button.setLastChangeTime(millis() + 50 + press * 100);
        button.update();

        while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
            radio.update();
        }
    }

    assert(burst_count == 3);
    assert(radio.getState() == RadioState::IDLE);
    printf("testRepeatedErrorAndRecovery: PASSED\n");
}

void testConfigurationChanges() {
    RadioConfig rcfg{};
    rcfg.channel_min = 5;
    rcfg.channel_max = 20;
    MockRadioController radio(rcfg);
    radio.status_callback_ = [](const char*, bool){};
    radio.begin();

    assert(radio.startBurst(5, 1, 1, 1));
    radio.abortBurst();

    assert(radio.startBurst(20, 2, 1, 1));
    radio.abortBurst();

    assert(!radio.startBurst(4, 3, 1, 1));
    assert(!radio.startBurst(21, 4, 1, 1));
    printf("testConfigurationChanges: PASSED\n");
}

void testLoggingCorrectness() {
    RadioConfig rcfg{};
    std::vector<std::pair<const char*, bool>> log_entries;
    MockRadioController radio(rcfg);
    radio.status_callback_ = [&](const char* msg, bool success) {
        log_entries.emplace_back(msg, success);
    };

    radio.begin();
    bool found_init = false;
    for (const auto& entry : log_entries) {
        if (strstr(entry.first, "initialization") && entry.second) {
            found_init = true;
            break;
        }
    }
    assert(found_init);

    log_entries.clear();
    radio.startBurst(42, 1, 2, 5);
    bool found_burst = false;
    for (const auto& entry : log_entries) {
        if (strstr(entry.first, "Burst started") && entry.second) {
            found_burst = true;
            break;
        }
    }
    assert(found_burst);

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        radio.update();
    }

    log_entries.clear();
    bool found_complete = false;
    for (const auto& entry : log_entries) {
        if (strstr(entry.first, "Burst complete") && entry.second) {
            found_complete = true;
            break;
        }
    }
    assert(found_complete);
    printf("testLoggingCorrectness: PASSED\n");
}

void testStateMachineTransitions() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.status_callback_ = [](const char*, bool){};

    assert(radio.getState() == RadioState::UNINITIALIZED);
    radio.begin();
    assert(radio.getState() == RadioState::IDLE);
    radio.startBurst(42, 1, 1, 1);
    assert(radio.getState() == RadioState::BURST_IN_PROGRESS);

    while (radio.getState() == RadioState::BURST_IN_PROGRESS) {
        radio.update();
    }
    assert(radio.getState() == RadioState::IDLE);

    radio.end();
    assert(radio.getState() == RadioState::UNINITIALIZED);
    printf("testStateMachineTransitions: PASSED\n");
}

void testNoAccidentalInfiniteLoops() {
    RadioConfig rcfg{};
    MockRadioController radio(rcfg);
    radio.setMaxPacketsSent(100);
    radio.status_callback_ = [](const char*, bool){};
    radio.begin();

    radio.startBurst(42, 1, 50, 1);

    int update_count = 0;
    while (radio.getState() == RadioState::BURST_IN_PROGRESS && update_count < 1000) {
        radio.update();
        update_count++;
    }

    assert(radio.getState() == RadioState::IDLE);
    assert(update_count < 1000);
    printf("testNoAccidentalInfiniteLoops: PASSED\n");
}

void testPacketProtocolIntegration() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = CURRENT_VERSION;
    pkt.burst_id = 12345;
    pkt.sequence = 1;
    pkt.channel = 42;
    fillTestPayload(pkt.payload, sizeof(pkt.payload), pkt.sequence, pkt.burst_id);
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    assert(serializePacket(pkt, buffer, sizeof(buffer), out_size));

    TestPacket pkt2{};
    assert(deserializePacket(buffer, out_size, pkt2));
    assert(pkt2.burst_id == 12345);
    assert(pkt2.channel == 42);
    assert(out_size <= MAX_PAYLOAD_SIZE);
    printf("testPacketProtocolIntegration: PASSED\n");
}

int main() {
    testButtonEventToRadioBurst();
    testMultipleSequentialButtonPresses();
    testRadioInitFailureHandling();
    testRepeatedErrorAndRecovery();
    testConfigurationChanges();
    testLoggingCorrectness();
    testStateMachineTransitions();
    testNoAccidentalInfiniteLoops();
    testPacketProtocolIntegration();
    printf("\nAll integration tests PASSED\n");
    return 0;
}
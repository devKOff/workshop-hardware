#include <Arduino.h>
#include "config.h"
#include "button_handler.h"
#include "radio_controller.h"
#include "logger.h"
#include "packet_protocol.h"

using namespace config;
using namespace button_handler;
using namespace radio_controller;
using namespace logger;

enum class FirmwareState : uint8_t {
    INITIALIZING = 0,
    IDLE,
    BURST_IN_PROGRESS,
    ERROR_STATE
};

static FirmwareState current_state = FirmwareState::INITIALIZING;
static FirmwareState previous_state = FirmwareState::INITIALIZING;

static ButtonHandler button;
static RadioController radio;

static uint32_t state_entry_time = 0;
static uint32_t last_status_print = 0;
static bool led_state = false;
static uint32_t last_led_toggle = 0;

void setState(FirmwareState new_state) {
    if (current_state != new_state) {
        previous_state = current_state;
        current_state = new_state;
        state_entry_time = millis();
        Logger::instance().logStateChange(
            [](FirmwareState s) -> const char* {
                switch (s) {
                    case FirmwareState::INITIALIZING: return "INITIALIZING";
                    case FirmwareState::IDLE: return "IDLE";
                    case FirmwareState::BURST_IN_PROGRESS: return "BURST_IN_PROGRESS";
                    case FirmwareState::ERROR_STATE: return "ERROR_STATE";
                }
                return "UNKNOWN";
            }(previous_state),
            [](FirmwareState s) -> const char* {
                switch (s) {
                    case FirmwareState::INITIALIZING: return "INITIALIZING";
                    case FirmwareState::IDLE: return "IDLE";
                    case FirmwareState::BURST_IN_PROGRESS: return "BURST_IN_PROGRESS";
                    case FirmwareState::ERROR_STATE: return "ERROR_STATE";
                }
                return "UNKNOWN";
            }(new_state)
        );
    }
}

void updateStatusLed() {
    uint32_t now = millis();
    uint32_t interval = 1000;

    switch (current_state) {
        case FirmwareState::INITIALIZING:
            interval = 100;
            break;
        case FirmwareState::IDLE:
            interval = 1000;
            break;
        case FirmwareState::BURST_IN_PROGRESS:
            interval = 50;
            break;
        case FirmwareState::ERROR_STATE:
            interval = 200;
            break;
        default:
            interval = 1000;
            break;
    }

    if (now - last_led_toggle >= interval) {
        led_state = !led_state;
        digitalWrite(PIN_STATUS_LED, led_state);
        last_led_toggle = now;
    }
}

void printPeriodicStatus() {
    uint32_t now = millis();
    if (now - last_status_print >= 5000) {
        LOG_INFO("MAIN", "State: %s | Radio: %s | Packets: %u/%u | Ch: %u | Free Heap: %u",
                 [](FirmwareState s) -> const char* {
                     switch (s) {
                         case FirmwareState::INITIALIZING: return "INIT";
                         case FirmwareState::IDLE: return "IDLE";
                         case FirmwareState::BURST_IN_PROGRESS: return "TX";
                         case FirmwareState::ERROR_STATE: return "ERR";
                     }
                     return "???";
                 }(current_state),
                 radio.isHealthy() ? "OK" : "FAULT",
                 radio.getPacketsSent(), radio.getPacketsTotal(),
                 radio.getCurrentChannel(),
                 ESP.getFreeHeap());
        last_status_print = now;
    }
}

void handleInitializing() {
    LOG_INFO("MAIN", "Initializing %s %s", PROJECT_NAME, FIRMWARE_VERSION);

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    button.begin();
    LOG_INFO("MAIN", "Button handler initialized on GPIO %u", PIN_BUTTON);

    if (!radio.begin()) {
        LOG_ERROR("MAIN", "Radio initialization failed: %d", static_cast<uint8_t>(radio.getLastError()));
        setState(FirmwareState::ERROR_STATE);
        return;
    }
    LOG_INFO("MAIN", "Radio initialized successfully");

    setState(FirmwareState::IDLE);
}

void handleIdle() {
    button.update();
    ButtonEvent event = button.getEvent();

    if (event == ButtonEvent::SHORT_PRESS) {
        uint8_t channel = radio.generateRandomChannel();
        LOG_INFO("MAIN", "Short press - Starting burst on random channel %u (%u MHz)",
                 channel, channelToFrequencyMHz(channel));

        if (radio.startBurst(channel)) {
            setState(FirmwareState::BURST_IN_PROGRESS);
        } else {
            LOG_ERROR("MAIN", "Failed to start burst: %d", static_cast<uint8_t>(radio.getLastError()));
        }
    } else if (event == ButtonEvent::LONG_PRESS) {
        LOG_INFO("MAIN", "Long press - Starting burst on default channel %u", RF_CHANNEL_DEFAULT);
        if (radio.startBurst(config::RF_CHANNEL_DEFAULT)) {
            setState(FirmwareState::BURST_IN_PROGRESS);
        } else {
            LOG_ERROR("MAIN", "Failed to start burst: %d", static_cast<uint8_t>(radio.getLastError()));
        }
    }

    radio.update();

    if (millis() - state_entry_time > config::STATE_TIMEOUT_MS) {
        LOG_WARN("MAIN", "IDLE state timeout, system healthy");
        state_entry_time = millis();
    }
}

void handleBurstInProgress() {
    radio.update();

    if (!radio.isBusy()) {
        LOG_INFO("MAIN", "Burst %u completed: %u/%u packets sent",
                 radio.getCurrentBurstId(), radio.getPacketsSent(), radio.getPacketsTotal());
        setState(FirmwareState::IDLE);
    }

    uint32_t elapsed = millis() - state_entry_time;
    if (elapsed > config::WATCHDOG_TIMEOUT_MS) {
        LOG_ERROR("MAIN", "Burst watchdog timeout (%u ms), aborting", elapsed);
        radio.abortBurst();
        setState(FirmwareState::ERROR_STATE);
    }
}

void handleErrorState() {
    radio.update();

    button.update();
    if (button.getEvent() == ButtonEvent::LONG_PRESS) {
        LOG_INFO("MAIN", "Long press in ERROR_STATE - attempting recovery");
        if (radio.begin()) {
            LOG_INFO("MAIN", "Radio re-initialized successfully");
            setState(FirmwareState::IDLE);
        } else {
            LOG_ERROR("MAIN", "Radio re-initialization failed");
        }
    }
}

void setup() {
    Serial.begin(config::SERIAL_BAUD);
    while (!Serial && millis() < 2000) { delay(10); }

    Logger::instance().begin(config::SERIAL_BAUD, LogLevel::INFO);
    LOG_INFO("MAIN", "=== %s %s Starting ===", PROJECT_NAME, FIRMWARE_VERSION);
    LOG_INFO("MAIN", "Pinout: CE=%u CSN=%u BTN=%u LED=%u", PIN_NRF_CE, PIN_NRF_CSN, PIN_BUTTON, PIN_STATUS_LED);
    LOG_INFO("MAIN", "Channel Range: %u-%u | Default Packets/Burst: %u",
             DEFAULT_CHANNEL_MIN, DEFAULT_CHANNEL_MAX, DEFAULT_PACKETS_PER_BURST);
}

void loop() {
    updateStatusLed();
    printPeriodicStatus();

    switch (current_state) {
        case FirmwareState::INITIALIZING:
            handleInitializing();
            break;
        case FirmwareState::IDLE:
            handleIdle();
            break;
        case FirmwareState::BURST_IN_PROGRESS:
            handleBurstInProgress();
            break;
        case FirmwareState::ERROR_STATE:
            handleErrorState();
            break;
    }

    yield();
}
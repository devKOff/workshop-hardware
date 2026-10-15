#include "config.h"
#include "button_handler.h"
#include "radio_controller.h"
#include "logger.h"
#include "packet_protocol.h"
#include <Arduino.h>

// Forward declarations from main.cpp
void onButtonPress();
void statusCallback(const char*, bool);
uint8_t selectRandomChannel();

// Global instances (from main.cpp)
static config::AppConfig g_config;
static button::ButtonHandler g_button(g_config.button);
static radio::RadioController g_radio(g_config.radio);
static uint32_t g_burst_id = 0;
static bool g_burst_requested = false;
static uint8_t g_selected_channel = 0;

void setup() {
    g_config = config::getDefaultConfig();
    if (!config::validateAppConfig(g_config)) {
        Serial.begin(115200);
        while (!Serial && millis() < 2000) {}
        Serial.println("[ERROR] Invalid configuration");
        while (true) {}
    }

    logger::begin(g_config.logging.baud_rate, logger::Level::INFO);

    pinMode(g_config.led.pin, OUTPUT);
    digitalWrite(g_config.led.pin, g_config.led.active_high ? LOW : HIGH);

    randomSeed(analogRead(g_config.random_seed_entropy_pin) ^ micros());

    g_radio.begin();
    g_radio.setStatusCallback(statusCallback);
    g_button.begin(onButtonPress);

    logger::infoWaitingForButton();
}

void loop() {
    g_button.update();
    g_radio.update();

    if (g_burst_requested) {
        g_burst_requested = false;
        g_burst_id++;
        g_selected_channel = selectRandomChannel();
        uint32_t freq_mhz = radio::RadioController::channelToFrequencyMHz(g_selected_channel);

        logger::testBurstStart(g_burst_id);
        logger::testChannelSelected(g_selected_channel, freq_mhz);

        if (g_config.led.enabled) {
            digitalWrite(g_config.led.pin, g_config.led.active_high ? HIGH : LOW);
        }

        bool started = g_radio.startBurst(
            g_selected_channel,
            g_burst_id,
            g_config.radio.packets_per_burst,
            g_config.radio.packet_interval_ms
        );

        if (!started) {
            logger::log(logger::Level::ERROR, "Failed to start burst on channel %u", g_selected_channel);
            if (g_config.led.enabled) {
                digitalWrite(g_config.led.pin, g_config.led.active_high ? LOW : HIGH);
            }
        }
    }

    if (g_radio.getState() == radio::RadioState::IDLE && g_radio.getPacketsSent() > 0) {
        logger::testPacketStats(g_radio.getPacketsSent(), g_radio.getPacketsAcked());
        logger::testBurstComplete();
        logger::infoRadioIdle();
        logger::infoWaitingForButton();

        if (g_config.led.enabled) {
            digitalWrite(g_config.led.pin, g_config.led.active_high ? LOW : HIGH);
        }
    }
}

void onButtonPress() {
    g_burst_requested = true;
}

void statusCallback(const char* message, bool success) {
    logger::log(success ? logger::Level::INFO : logger::Level::ERROR, "%s", message);
}

uint8_t selectRandomChannel() {
    uint8_t range = g_config.radio.channel_max - g_config.radio.channel_min + 1;
    uint32_t random_val = random(range);
    return g_config.radio.channel_min + static_cast<uint8_t>(random_val);
}
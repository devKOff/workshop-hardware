#pragma once

#include <Arduino.h>
#include <RF24.h>
#include <cstdint>

namespace config {

constexpr uint8_t PIN_NRF_CE   = 25;
constexpr uint8_t PIN_NRF_CSN  = 5;
constexpr uint8_t PIN_NRF_SCK  = 18;
constexpr uint8_t PIN_NRF_MOSI = 23;
constexpr uint8_t PIN_NRF_MISO = 19;
constexpr uint8_t PIN_BUTTON   = 4;
constexpr uint8_t PIN_STATUS_LED = 2;

constexpr uint8_t BUTTON_ACTIVE_LEVEL = LOW;

constexpr uint32_t SERIAL_BAUD = 115200;

constexpr uint16_t BUTTON_DEBOUNCE_MS = 50;
constexpr uint16_t BUTTON_LONG_PRESS_MS = 1000;

constexpr uint8_t DEFAULT_CHANNEL_MIN = 0;
constexpr uint8_t DEFAULT_CHANNEL_MAX = 125;
constexpr uint8_t DEFAULT_PACKETS_PER_BURST = 20;
constexpr uint16_t DEFAULT_INTER_PACKET_DELAY_US = 1000;

constexpr uint8_t RF_CHANNEL_DEFAULT = 2;
constexpr rf24_pa_dbm_e RF_PA_LEVEL = RF24_PA_LOW;
constexpr rf24_datarate_e RF_DATA_RATE = RF24_1MBPS;
constexpr uint8_t RF_CRC_LENGTH = 2;

constexpr uint32_t WATCHDOG_TIMEOUT_MS = 5000;
constexpr uint32_t STATE_TIMEOUT_MS = 10000;

constexpr uint64_t PIPE_ADDRESS = 0xE7E7E7E7E7LL;

constexpr const char* FIRMWARE_VERSION = "V4.1";
constexpr const char* PROJECT_NAME = "ESP32 Random-Channel RF Test Generator";

inline uint32_t channelToFrequencyMHz(uint8_t channel) {
    return 2400u + static_cast<uint32_t>(channel);
}

inline bool isValidChannel(uint8_t channel) {
    return channel <= DEFAULT_CHANNEL_MAX;
}

} // namespace config
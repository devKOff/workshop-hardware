#pragma once

#include <cstdint>

namespace config {

struct RadioConfig {
    uint8_t ce_pin = 25;
    uint8_t csn_pin = 5;
    uint8_t sck_pin = 18;
    uint8_t mosi_pin = 23;
    uint8_t miso_pin = 19;
    uint8_t channel_min = 0;
    uint8_t channel_max = 125;
    int8_t tx_power_dbm = -12;
    uint8_t data_rate = 2;
    uint8_t payload_size = 32;
    uint16_t packets_per_burst = 20;
    uint16_t packet_interval_ms = 10;
    bool auto_ack = false;
    bool dynamic_payloads = false;
};

struct ButtonConfig {
    uint8_t pin = 4;
    uint16_t debounce_ms = 50;
    bool active_low = true;
};

struct LedConfig {
    uint8_t pin = 2;
    bool enabled = true;
    bool active_high = true;
};

struct LoggingConfig {
    uint32_t baud_rate = 115200;
    bool enabled = true;
};

struct AppConfig {
    RadioConfig radio;
    ButtonConfig button;
    LedConfig led;
    LoggingConfig logging;
    uint32_t random_seed_entropy_pin = 36;
};

constexpr uint8_t MIN_CHANNEL = 0;
constexpr uint8_t MAX_CHANNEL = 125;
constexpr uint16_t MIN_PACKETS_PER_BURST = 1;
constexpr uint16_t MAX_PACKETS_PER_BURST = 1000;
constexpr uint16_t MIN_PACKET_INTERVAL_MS = 1;
constexpr uint16_t MAX_PACKET_INTERVAL_MS = 10000;
constexpr int8_t MIN_TX_POWER_DBM = -18;
constexpr int8_t MAX_TX_POWER_DBM = 0;
constexpr uint8_t MAX_PAYLOAD_SIZE = 32;
constexpr uint8_t PROTOCOL_VERSION = 1;
constexpr uint16_t MAGIC_IDENTIFIER = 0x5246;

bool validateRadioConfig(const RadioConfig& cfg);
bool validateButtonConfig(const ButtonConfig& cfg);
bool validateAppConfig(const AppConfig& cfg);

const AppConfig& getDefaultConfig();
AppConfig& getMutableConfig();

} // namespace config
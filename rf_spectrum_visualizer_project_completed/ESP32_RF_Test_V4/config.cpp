#include "config.h"

namespace config {

namespace {
AppConfig g_config;
bool g_config_initialized = false;
}

const AppConfig& getDefaultConfig() {
    if (!g_config_initialized) {
        g_config = AppConfig{};
        g_config_initialized = true;
    }
    return g_config;
}

AppConfig& getMutableConfig() {
    if (!g_config_initialized) {
        g_config = AppConfig{};
        g_config_initialized = true;
    }
    return g_config;
}

bool validateRadioConfig(const RadioConfig& cfg) {
    if (cfg.channel_min > cfg.channel_max) return false;
    if (static_cast<int>(cfg.channel_min) < MIN_CHANNEL || static_cast<int>(cfg.channel_max) > MAX_CHANNEL) return false;
    if (cfg.packets_per_burst < MIN_PACKETS_PER_BURST || cfg.packets_per_burst > MAX_PACKETS_PER_BURST) return false;
    if (cfg.packet_interval_ms < MIN_PACKET_INTERVAL_MS || cfg.packet_interval_ms > MAX_PACKET_INTERVAL_MS) return false;
    if (cfg.tx_power_dbm < MIN_TX_POWER_DBM || cfg.tx_power_dbm > MAX_TX_POWER_DBM) return false;
    if (cfg.payload_size > MAX_PAYLOAD_SIZE || cfg.payload_size == 0) return false;
    if (cfg.data_rate > 2) return false;
    return true;
}

bool validateButtonConfig(const ButtonConfig& cfg) {
    if (cfg.debounce_ms == 0 || cfg.debounce_ms > 1000) return false;
    return true;
}

bool validateAppConfig(const AppConfig& cfg) {
    return validateRadioConfig(cfg.radio) && validateButtonConfig(cfg.button);
}

} // namespace config
#include "logger.h"
#include "Arduino.h"

namespace logger {

static Level g_level = Level::INFO;
static bool g_initialized = false;

void begin(uint32_t baud_rate, Level level) {
    Serial.begin(baud_rate);
    while (!Serial && millis() < 2000) {}
    g_level = level;
    g_initialized = true;
    logRaw(Level::INFO, "=== ESP32 Random-Channel RF Test Generator V4 ===");
    logRaw(Level::INFO, "Build: " __DATE__ " " __TIME__);
}

void setLevel(Level level) {
    g_level = level;
}

Level getLevel() {
    return g_level;
}

void log(Level level, const char* format, ...) {
    if (level > g_level || !g_initialized) return;

    const char* prefix = "";
    switch (level) {
        case Level::ERROR: prefix = "[ERROR] "; break;
        case Level::WARN:  prefix = "[WARN]  "; break;
        case Level::INFO:  prefix = "[INFO]  "; break;
        case Level::DEBUG: prefix = "[DEBUG] "; break;
        case Level::TEST:  prefix = "[TEST]  "; break;
        default: break;
    }

    char buffer[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);

    Serial.print(prefix);
    Serial.println(buffer);
}

void logRaw(Level level, const char* message) {
    if (level > g_level || !g_initialized) return;
    Serial.println(message);
}

void testBurstStart(uint32_t burst_id) {
    log(Level::TEST, "Burst ID: %lu", burst_id);
}

void testChannelSelected(uint8_t channel, uint32_t frequency_mhz) {
    log(Level::TEST, "Selected channel: %u", channel);
    log(Level::TEST, "Center frequency: %lu MHz", frequency_mhz);
}

void testPacketStats(uint16_t attempted, uint16_t acked) {
    log(Level::TEST, "Packets attempted: %u", attempted);
    if (acked > 0) {
        log(Level::TEST, "Packets acknowledged: %u", acked);
    } else {
        log(Level::TEST, "Packets acknowledged: N/A (auto-ack disabled)");
    }
}

void testBurstComplete() {
    log(Level::TEST, "Burst complete");
}

void infoRadioIdle() {
    log(Level::INFO, "Radio returned to idle");
}

void infoWaitingForButton() {
    log(Level::INFO, "Waiting for button press");
}

} // namespace logger
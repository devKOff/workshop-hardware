#include "logger.h"
#include "packet_protocol.h"

namespace logger {

void Logger::begin(uint32_t baud, LogLevel level) {
    if (!initialized_) {
        Serial.begin(baud);
        while (!Serial && millis() < 1000) { delay(10); }
        initialized_ = true;
    }
    level_ = level;
    LOG_INFO("LOG", "Logger initialized at %u baud, level %d", baud, static_cast<uint8_t>(level));
}

void Logger::setLevel(LogLevel level) { level_ = level; }
LogLevel Logger::getLevel() const { return level_; }

void Logger::log(LogLevel msg_level, const char* tag, const char* format, va_list args) {
    if (!initialized_ || msg_level > level_) return;

    printTimestamp();
    Serial.printf("[%s][%s] ", levelToString(msg_level), tag);
    char buffer[256];
    vsnprintf(buffer, sizeof(buffer), format, args);
    Serial.println(buffer);
}

void Logger::error(const char* tag, const char* format, ...) {
    va_list args;
    va_start(args, format);
    log(LogLevel::ERROR, tag, format, args);
    va_end(args);
}

void Logger::warn(const char* tag, const char* format, ...) {
    va_list args;
    va_start(args, format);
    log(LogLevel::WARN, tag, format, args);
    va_end(args);
}

void Logger::info(const char* tag, const char* format, ...) {
    va_list args;
    va_start(args, format);
    log(LogLevel::INFO, tag, format, args);
    va_end(args);
}

void Logger::debug(const char* tag, const char* format, ...) {
    va_list args;
    va_start(args, format);
    log(LogLevel::DEBUG, tag, format, args);
    va_end(args);
}

void Logger::verbose(const char* tag, const char* format, ...) {
    va_list args;
    va_start(args, format);
    log(LogLevel::VERBOSE, tag, format, args);
    va_end(args);
}

void Logger::logStateChange(const char* from, const char* to) {
    if (!initialized_ || level_ < LogLevel::INFO) return;
    printTimestamp();
    Serial.printf("[INFO][STATE] Transition: %s -> %s\n", from, to);
}

void Logger::logPacket(const packet_protocol::TestPacket& packet, bool tx) {
    if (!initialized_ || level_ < LogLevel::DEBUG) return;
    printTimestamp();
    Serial.printf("[DEBUG][PKT] %s: Magic=0x%08X Ver=%u Burst=%u Seq=%u Ch=%u Freq=%u\n",
                  tx ? "TX" : "RX", packet.magic, packet.version, packet.burst_id,
                  packet.sequence, packet.channel, packet.frequency_mhz);
}

void Logger::logBurstStart(uint16_t burst_id, uint8_t channel, uint16_t count) {
    if (!initialized_ || level_ < LogLevel::INFO) return;
    printTimestamp();
    Serial.printf("[INFO][BURST] Start: ID=%u Ch=%u (%u MHz) Count=%u\n",
                  burst_id, channel, config::channelToFrequencyMHz(channel), count);
}

void Logger::logBurstComplete(uint16_t burst_id, uint16_t sent, uint16_t total) {
    if (!initialized_ || level_ < LogLevel::INFO) return;
    printTimestamp();
    Serial.printf("[INFO][BURST] Complete: ID=%u Sent=%u/%u (%.1f%%)\n",
                  burst_id, sent, total, total > 0 ? (100.0 * sent / total) : 0.0);
}

void Logger::logButtonEvent(const char* event) {
    if (!initialized_ || level_ < LogLevel::INFO) return;
    printTimestamp();
    Serial.printf("[INFO][BTN] %s\n", event);
}

void Logger::printTimestamp() {
    uint32_t ms = millis();
    uint32_t secs = ms / 1000;
    uint32_t mins = secs / 60;
    uint32_t hours = mins / 60;
    Serial.printf("[%02u:%02u:%02u.%03u] ", hours % 24, mins % 60, secs % 60, ms % 1000);
}

const char* Logger::levelToString(LogLevel level) const {
    switch (level) {
        case LogLevel::SILENT: return "SILENT";
        case LogLevel::ERROR: return "ERROR";
        case LogLevel::WARN: return "WARN";
        case LogLevel::INFO: return "INFO";
        case LogLevel::DEBUG: return "DEBUG";
        case LogLevel::VERBOSE: return "VERBOSE";
        default: return "UNKNOWN";
    }
}

} // namespace logger
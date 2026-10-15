#pragma once

#include <Arduino.h>
#include <cstdint>
#include <cstdio>
#include "config.h"
#include "packet_protocol.h"

namespace logger {

enum class LogLevel : uint8_t {
    SILENT = 0,
    ERROR = 1,
    WARN = 2,
    INFO = 3,
    DEBUG = 4,
    VERBOSE = 5
};

class Logger {
public:
    static Logger& instance() {
        static Logger logger;
        return logger;
    }

    void begin(uint32_t baud = config::SERIAL_BAUD, LogLevel level = LogLevel::INFO);
    void setLevel(LogLevel level);
    LogLevel getLevel() const;

    void error(const char* tag, const char* format, ...);
    void warn(const char* tag, const char* format, ...);
    void info(const char* tag, const char* format, ...);
    void debug(const char* tag, const char* format, ...);
    void verbose(const char* tag, const char* format, ...);

    void logStateChange(const char* from, const char* to);
    void logPacket(const packet_protocol::TestPacket& packet, bool tx);
    void logBurstStart(uint16_t burst_id, uint8_t channel, uint16_t count);
    void logBurstComplete(uint16_t burst_id, uint16_t sent, uint16_t total);
    void logButtonEvent(const char* event);

private:
    Logger() : level_(LogLevel::INFO), initialized_(false) {}
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    void log(LogLevel msg_level, const char* tag, const char* format, va_list args);
    void printTimestamp();
    const char* levelToString(LogLevel level) const;

    LogLevel level_;
    bool initialized_;
};

#define LOG_ERROR(tag, ...)   logger::Logger::instance().error(tag, __VA_ARGS__)
#define LOG_WARN(tag, ...)    logger::Logger::instance().warn(tag, __VA_ARGS__)
#define LOG_INFO(tag, ...)    logger::Logger::instance().info(tag, __VA_ARGS__)
#define LOG_DEBUG(tag, ...)   logger::Logger::instance().debug(tag, __VA_ARGS__)
#define LOG_VERBOSE(tag, ...) logger::Logger::instance().verbose(tag, __VA_ARGS__)

} // namespace logger
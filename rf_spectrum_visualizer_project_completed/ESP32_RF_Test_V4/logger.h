#pragma once

#include <cstdint>
#include <cstdio>

namespace logger {

enum class Level : uint8_t {
    NONE = 0,
    ERROR = 1,
    WARN = 2,
    INFO = 3,
    DEBUG = 4,
    TEST = 5
};

void begin(uint32_t baud_rate, Level level = Level::INFO);
void setLevel(Level level);
Level getLevel();

void log(Level level, const char* format, ...);
void logRaw(Level level, const char* message);

void testBurstStart(uint32_t burst_id);
void testChannelSelected(uint8_t channel, uint32_t frequency_mhz);
void testPacketStats(uint16_t attempted, uint16_t acked);
void testBurstComplete();
void infoRadioIdle();
void infoWaitingForButton();

} // namespace logger
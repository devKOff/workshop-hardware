#pragma once

#include <cstdint>
#include <cstddef>
#include "config.h"

namespace packet {

struct alignas(1) TestPacket {
    uint16_t magic;
    uint8_t version;
    uint8_t reserved;
    uint32_t burst_id;
    uint16_t sequence;
    uint8_t channel;
    uint8_t payload[19];
    uint16_t crc16;
};

static_assert(sizeof(TestPacket) <= config::MAX_PAYLOAD_SIZE, "TestPacket exceeds maximum payload size");

constexpr uint16_t MAGIC_VALUE = 0x5246;
constexpr uint8_t CURRENT_VERSION = config::PROTOCOL_VERSION;
constexpr size_t PAYLOAD_DATA_SIZE = sizeof(TestPacket) - 2;

uint16_t computeCRC16(const uint8_t* data, size_t length);
bool serializePacket(const TestPacket& packet, uint8_t* buffer, size_t buffer_size, size_t& out_size);
bool deserializePacket(const uint8_t* buffer, size_t buffer_size, TestPacket& packet);
void fillTestPayload(uint8_t* payload, size_t size, uint16_t sequence, uint32_t burst_id);

} // namespace packet
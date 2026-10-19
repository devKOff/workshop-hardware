#include "packet_protocol.h"

namespace packet {

uint16_t computeCRC16(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (uint8_t j = 0; j < 8; ++j) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

bool serializePacket(const TestPacket& packet, uint8_t* buffer, size_t buffer_size, size_t& out_size) {
    if (buffer_size < sizeof(TestPacket)) return false;
    const uint8_t* src = reinterpret_cast<const uint8_t*>(&packet);
    for (size_t i = 0; i < sizeof(TestPacket); ++i) {
        buffer[i] = src[i];
    }
    out_size = sizeof(TestPacket);
    return true;
}

bool deserializePacket(const uint8_t* buffer, size_t buffer_size, TestPacket& packet) {
    if (buffer_size < sizeof(TestPacket)) return false;
    uint8_t* dst = reinterpret_cast<uint8_t*>(&packet);
    for (size_t i = 0; i < sizeof(TestPacket); ++i) {
        dst[i] = buffer[i];
    }
    if (packet.magic != MAGIC_VALUE) return false;
    if (packet.version != CURRENT_VERSION) return false;
    uint16_t computed_crc = computeCRC16(buffer, buffer_size - 2);
    return computed_crc == packet.crc16;
}

void fillTestPayload(uint8_t* payload, size_t size, uint16_t sequence, uint32_t burst_id) {
    for (size_t i = 0; i < size; ++i) {
        payload[i] = static_cast<uint8_t>((burst_id >> (8 * (i % 4))) ^ (sequence >> (8 * (i % 2))) ^ (i * 0x31));
    }
}

} // namespace packet
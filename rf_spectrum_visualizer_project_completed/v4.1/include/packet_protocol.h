#pragma once

#include <cstdint>
#include <cstring>
#include "config.h"

namespace packet_protocol {

constexpr uint32_t MAGIC_BYTES = 0x45535034;
constexpr uint8_t PROTOCOL_VERSION = 1;
constexpr size_t MAX_PAYLOAD_SIZE = 32;

struct __attribute__((packed)) TestPacket {
    uint32_t magic;
    uint8_t version;
    uint16_t burst_id;
    uint16_t sequence;
    uint8_t channel;
    uint32_t frequency_mhz;
    uint8_t padding[MAX_PAYLOAD_SIZE - 14];

    TestPacket() : magic(0), version(0), burst_id(0), sequence(0),
                   channel(0), frequency_mhz(0) {
        memset(padding, 0, sizeof(padding));
    }
};

constexpr size_t PACKET_SIZE = sizeof(TestPacket);
static_assert(PACKET_SIZE <= MAX_PAYLOAD_SIZE, "Packet too large");

inline void createPacket(TestPacket& packet, uint16_t burst_id, uint16_t sequence,
                         uint8_t channel) {
    packet.magic = MAGIC_BYTES;
    packet.version = PROTOCOL_VERSION;
    packet.burst_id = burst_id;
    packet.sequence = sequence;
    packet.channel = channel;
    packet.frequency_mhz = config::channelToFrequencyMHz(channel);
    memset(packet.padding, 0xAA, sizeof(packet.padding));
}

inline bool validatePacket(const TestPacket& packet) {
    return packet.magic == MAGIC_BYTES &&
           packet.version == PROTOCOL_VERSION &&
           config::isValidChannel(packet.channel) &&
           packet.frequency_mhz == config::channelToFrequencyMHz(packet.channel);
}

inline void printPacket(const TestPacket& packet) {
    Serial.printf("[PKT] Magic: 0x%08X | Ver: %u | Burst: %u | Seq: %u | Ch: %u | Freq: %u MHz\n",
                  packet.magic, packet.version, packet.burst_id, packet.sequence,
                  packet.channel, packet.frequency_mhz);
}

} // namespace packet_protocol
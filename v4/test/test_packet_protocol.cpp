#include "packet_protocol.h"
#include "config.h"
#include <cassert>
#include <cstdio>
#include <cstring>

using namespace packet;
using namespace config;

void testPacketSize() {
    assert(sizeof(TestPacket) <= MAX_PAYLOAD_SIZE);
    printf("testPacketSize: PASSED (size=%zu, max=%d)\n", sizeof(TestPacket), MAX_PAYLOAD_SIZE);
}

void testSerializeDeserialize() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = CURRENT_VERSION;
    pkt.reserved = 0;
    pkt.burst_id = 42;
    pkt.sequence = 123;
    pkt.channel = 64;
    fillTestPayload(pkt.payload, sizeof(pkt.payload), pkt.sequence, pkt.burst_id);
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    assert(serializePacket(pkt, buffer, sizeof(buffer), out_size));
    assert(out_size == sizeof(TestPacket));

    TestPacket pkt2{};
    assert(deserializePacket(buffer, out_size, pkt2));
    assert(pkt2.magic == pkt.magic);
    assert(pkt2.version == pkt.version);
    assert(pkt2.burst_id == pkt.burst_id);
    assert(pkt2.sequence == pkt.sequence);
    assert(pkt2.channel == pkt.channel);
    assert(memcmp(pkt2.payload, pkt.payload, sizeof(pkt.payload)) == 0);
    printf("testSerializeDeserialize: PASSED\n");
}

void testDeserializeInvalidMagic() {
    TestPacket pkt{};
    pkt.magic = 0x1234;
    pkt.version = CURRENT_VERSION;
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    serializePacket(pkt, buffer, sizeof(buffer), out_size);

    TestPacket pkt2{};
    assert(!deserializePacket(buffer, out_size, pkt2));
    printf("testDeserializeInvalidMagic: PASSED\n");
}

void testDeserializeInvalidVersion() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = 99;
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    serializePacket(pkt, buffer, sizeof(buffer), out_size);

    TestPacket pkt2{};
    assert(!deserializePacket(buffer, out_size, pkt2));
    printf("testDeserializeInvalidVersion: PASSED\n");
}

void testDeserializeTruncated() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = CURRENT_VERSION;
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    serializePacket(pkt, buffer, sizeof(buffer), out_size);

    TestPacket pkt2{};
    assert(!deserializePacket(buffer, out_size - 1, pkt2));
    printf("testDeserializeTruncated: PASSED\n");
}

void testDeserializeCorruptedCRC() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = CURRENT_VERSION;
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    serializePacket(pkt, buffer, sizeof(buffer), out_size);

    buffer[out_size - 1] ^= 0xFF;

    TestPacket pkt2{};
    assert(!deserializePacket(buffer, out_size, pkt2));
    printf("testDeserializeCorruptedCRC: PASSED\n");
}

void testCRC16Consistency() {
    uint8_t data[] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
    uint16_t crc1 = computeCRC16(data, sizeof(data));
    uint16_t crc2 = computeCRC16(data, sizeof(data));
    assert(crc1 == crc2);
    assert(crc1 != 0);
    printf("testCRC16Consistency: PASSED (crc=0x%04X)\n", crc1);
}

void testFillTestPayload() {
    uint8_t payload1[24];
    uint8_t payload2[24];
    fillTestPayload(payload1, sizeof(payload1), 10, 100);
    fillTestPayload(payload2, sizeof(payload2), 10, 100);
    assert(memcmp(payload1, payload2, sizeof(payload1)) == 0);

    uint8_t payload3[24];
    fillTestPayload(payload3, sizeof(payload3), 11, 100);
    assert(memcmp(payload1, payload3, sizeof(payload1)) != 0);
    printf("testFillTestPayload: PASSED\n");
}

void testBoundaryValues() {
    TestPacket pkt{};
    pkt.magic = MAGIC_VALUE;
    pkt.version = CURRENT_VERSION;
    pkt.burst_id = 0xFFFFFFFF;
    pkt.sequence = 0xFFFF;
    pkt.channel = 125;
    fillTestPayload(pkt.payload, sizeof(pkt.payload), pkt.sequence, pkt.burst_id);
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    uint8_t buffer[MAX_PAYLOAD_SIZE];
    size_t out_size = 0;
    assert(serializePacket(pkt, buffer, sizeof(buffer), out_size));

    TestPacket pkt2{};
    assert(deserializePacket(buffer, out_size, pkt2));
    assert(pkt2.burst_id == 0xFFFFFFFF);
    assert(pkt2.sequence == 0xFFFF);
    assert(pkt2.channel == 125);
    printf("testBoundaryValues: PASSED\n");
}

int main() {
    testPacketSize();
    testSerializeDeserialize();
    testDeserializeInvalidMagic();
    testDeserializeInvalidVersion();
    testDeserializeTruncated();
    testDeserializeCorruptedCRC();
    testCRC16Consistency();
    testFillTestPayload();
    testBoundaryValues();
    printf("\nAll packet protocol tests PASSED\n");
    return 0;
}
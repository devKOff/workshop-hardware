#include "test_packet_protocol.h"

void test_packet_size() {
    TEST_ASSERT_EQUAL_UINT16(32, sizeof(packet_protocol::TestPacket));
    TEST_ASSERT_TRUE(sizeof(packet_protocol::TestPacket) <= packet_protocol::MAX_PAYLOAD_SIZE);
}

void test_packet_creation() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 0x1234, 0x0001, 42);

    TEST_ASSERT_EQUAL_UINT32(packet_protocol::MAGIC_BYTES, pkt.magic);
    TEST_ASSERT_EQUAL_UINT8(packet_protocol::PROTOCOL_VERSION, pkt.version);
    TEST_ASSERT_EQUAL_UINT16(0x1234, pkt.burst_id);
    TEST_ASSERT_EQUAL_UINT16(0x0001, pkt.sequence);
    TEST_ASSERT_EQUAL_UINT8(42, pkt.channel);
    TEST_ASSERT_EQUAL_UINT32(2442, pkt.frequency_mhz);

    for (size_t i = 0; i < sizeof(pkt.padding); i++) {
        TEST_ASSERT_EQUAL_UINT8(0xAA, pkt.padding[i]);
    }
}

void test_packet_validation_valid() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 10);
    TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt));
}

void test_packet_validation_invalid_magic() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 10);
    pkt.magic = 0xDEADBEEF;
    TEST_ASSERT_FALSE(packet_protocol::validatePacket(pkt));
}

void test_packet_validation_invalid_version() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 10);
    pkt.version = 99;
    TEST_ASSERT_FALSE(packet_protocol::validatePacket(pkt));
}

void test_packet_validation_invalid_channel() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 10);
    pkt.channel = 200;
    TEST_ASSERT_FALSE(packet_protocol::validatePacket(pkt));
}

void test_packet_validation_mismatched_frequency() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 1, 1, 10);
    pkt.frequency_mhz = 9999;
    TEST_ASSERT_FALSE(packet_protocol::validatePacket(pkt));
}

void test_packet_edge_channels() {
    packet_protocol::TestPacket pkt0, pkt125;
    packet_protocol::createPacket(pkt0, 1, 1, 0);
    packet_protocol::createPacket(pkt125, 1, 1, 125);
    TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt0));
    TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkt125));
    TEST_ASSERT_EQUAL_UINT32(2400, pkt0.frequency_mhz);
    TEST_ASSERT_EQUAL_UINT32(2525, pkt125.frequency_mhz);
}

void test_packet_sequence_increment() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 5, 0, 7);
    TEST_ASSERT_EQUAL_UINT16(0, pkt.sequence);

    packet_protocol::createPacket(pkt, 5, 1, 7);
    TEST_ASSERT_EQUAL_UINT16(1, pkt.sequence);

    packet_protocol::createPacket(pkt, 5, 65535, 7);
    TEST_ASSERT_EQUAL_UINT16(65535, pkt.sequence);
}

void test_packet_structure_alignment() {
    packet_protocol::TestPacket pkt;
    packet_protocol::createPacket(pkt, 0xABCD, 0x0005, 88);

    uint8_t* bytes = reinterpret_cast<uint8_t*>(&pkt);
    TEST_ASSERT_EQUAL_UINT8(0x34, bytes[0]);
    TEST_ASSERT_EQUAL_UINT8(0x50, bytes[1]);
    TEST_ASSERT_EQUAL_UINT8(0x53, bytes[2]);
    TEST_ASSERT_EQUAL_UINT8(0x45, bytes[3]);
    TEST_ASSERT_EQUAL_UINT8(packet_protocol::PROTOCOL_VERSION, bytes[4]);
    TEST_ASSERT_EQUAL_UINT8(0xCD, bytes[5]);
    TEST_ASSERT_EQUAL_UINT8(0xAB, bytes[6]);
    TEST_ASSERT_EQUAL_UINT8(0x05, bytes[7]);
    TEST_ASSERT_EQUAL_UINT8(0x00, bytes[8]);
    TEST_ASSERT_EQUAL_UINT8(88, bytes[9]);  // channel at offset 9
}

void test_multiple_packets_same_burst() {
    packet_protocol::TestPacket pkts[5];
    for (int i = 0; i < 5; i++) {
        packet_protocol::createPacket(pkts[i], 100, i, 50 + i);
        TEST_ASSERT_EQUAL_UINT16(100, pkts[i].burst_id);
        TEST_ASSERT_EQUAL_UINT16(i, pkts[i].sequence);
        TEST_ASSERT_EQUAL_UINT8(50 + i, pkts[i].channel);
        TEST_ASSERT_TRUE(packet_protocol::validatePacket(pkts[i]));
    }
}
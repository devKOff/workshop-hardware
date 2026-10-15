#ifndef TEST_PACKET_PROTOCOL_H
#define TEST_PACKET_PROTOCOL_H

#include <unity.h>
#include "test_common.h"

void test_packet_size();
void test_packet_creation();
void test_packet_validation_valid();
void test_packet_validation_invalid_magic();
void test_packet_validation_invalid_version();
void test_packet_validation_invalid_channel();
void test_packet_validation_mismatched_frequency();
void test_packet_edge_channels();
void test_packet_sequence_increment();
void test_packet_structure_alignment();
void test_multiple_packets_same_burst();

#endif
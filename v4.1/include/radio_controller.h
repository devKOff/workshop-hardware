#pragma once

#include <Arduino.h>
#include <RF24.h>
#include <cstdint>
#include "config.h"
#include "packet_protocol.h"

namespace radio_controller {

enum class RadioState : uint8_t {
    UNINITIALIZED = 0,
    INITIALIZING,
    READY,
    TRANSMITTING,
    ERROR_STATE
};

enum class RadioError : uint8_t {
    NONE = 0,
    INIT_FAILED,
    WRITE_FAILED,
    INVALID_CHANNEL,
    TIMEOUT,
    HARDWARE_FAULT
};

class RadioController {
public:
    RadioController(uint8_t ce_pin = config::PIN_NRF_CE,
                    uint8_t csn_pin = config::PIN_NRF_CSN);

    bool begin();
    void end();
    void update();

    bool startBurst(uint8_t channel, uint16_t packets = config::DEFAULT_PACKETS_PER_BURST,
                    uint16_t inter_packet_delay_us = config::DEFAULT_INTER_PACKET_DELAY_US);
    void abortBurst();

    RadioState getState() const;
    RadioError getLastError() const;
    uint16_t getPacketsSent() const;
    uint16_t getPacketsTotal() const;
    uint8_t getCurrentChannel() const;
    uint16_t getCurrentBurstId() const;

    bool isBusy() const;
    bool isHealthy() const;
    uint8_t generateRandomChannel();

private:
    RF24 radio_;
    RadioState state_;
    RadioError last_error_;

    uint8_t current_channel_;
    uint16_t packets_total_;
    uint16_t packets_sent_;
    uint16_t inter_packet_delay_us_;
    uint16_t current_burst_id_;
    uint32_t last_packet_time_;

    packet_protocol::TestPacket tx_packet_;

    bool initializeRadio();
    bool configureChannel(uint8_t channel);
    bool sendPacket();
    void setError(RadioError error);
    void resetBurstCounters();
};

} // namespace radio_controller
#pragma once

#include <cstdint>
#include <functional>
#include "config.h"
#include "packet_protocol.h"

namespace radio {

enum class RadioState {
    UNINITIALIZED,
    INITIALIZING,
    IDLE,
    BURST_IN_PROGRESS,
    ERROR
};

class RadioController {
public:
    using StatusCallback = std::function<void(const char*, bool)>;

    explicit RadioController(const config::RadioConfig& cfg);
    ~RadioController();

    RadioController(const RadioController&) = delete;
    RadioController& operator=(const RadioController&) = delete;
    RadioController(RadioController&&) = delete;
    RadioController& operator=(RadioController&&) = delete;

    bool begin();
    void end();
    bool startBurst(uint8_t channel, uint32_t burst_id, uint16_t packet_count, uint16_t interval_ms);
    void update();
    void abortBurst();
    RadioState getState() const;
    uint8_t getCurrentChannel() const;
    uint32_t getBurstId() const;
    uint16_t getPacketsSent() const;
    uint16_t getPacketsAcked() const;
    const char* getStateName() const;
    void setStatusCallback(StatusCallback cb);

    static uint32_t channelToFrequencyMHz(uint8_t channel);
    bool isValidChannel(uint8_t channel) const;

private:
    const config::RadioConfig& config_;
    StatusCallback status_callback_;
    RadioState state_ = RadioState::UNINITIALIZED;
    uint8_t current_channel_ = 0;
    uint32_t current_burst_id_ = 0;
    uint16_t packets_to_send_ = 0;
    uint16_t packets_sent_ = 0;
    uint16_t packets_acked_ = 0;
    uint16_t packet_interval_ms_ = 0;
    uint32_t last_packet_time_ = 0;
    uint16_t sequence_ = 0;
    void* radio_instance_ = nullptr;

    bool initializeRadio();
    void setChannel(uint8_t channel);
    bool sendPacket();
    void transitionTo(RadioState new_state);
    void reportStatus(const char* message, bool success);
};

class MockRadioController {
public:
    using StatusCallback = std::function<void(const char*, bool)>;

    explicit MockRadioController(const config::RadioConfig& cfg);
    ~MockRadioController() = default;

    bool begin();
    void end();
    bool startBurst(uint8_t channel, uint32_t burst_id, uint16_t packet_count, uint16_t interval_ms);
    void update();
    void abortBurst();
    RadioState getState() const;
    uint8_t getCurrentChannel() const;
    uint32_t getBurstId() const;
    uint16_t getPacketsSent() const;
    uint16_t getPacketsAcked() const;
    const char* getStateName() const;

    void setFailInit(bool fail);
    void setFailSend(bool fail);
    void setMaxPacketsSent(uint16_t max);
    void setStatusCallback(StatusCallback cb);
    bool isValidChannel(uint8_t channel) const;

private:
    const config::RadioConfig& config_;
    StatusCallback status_callback_;
    RadioState state_ = RadioState::UNINITIALIZED;
    uint8_t current_channel_ = 0;
    uint32_t current_burst_id_ = 0;
    uint16_t packets_to_send_ = 0;
    uint16_t packets_sent_ = 0;
    uint16_t packets_acked_ = 0;
    uint16_t packet_interval_ms_ = 0;
    uint32_t last_packet_time_ = 0;
    uint16_t sequence_ = 0;
    bool fail_init_ = false;
    bool fail_send_ = false;
    uint16_t max_packets_sent_ = 0xFFFF;

    void transitionTo(RadioState new_state);
    void reportStatus(const char* message, bool success);
};

} // namespace radio
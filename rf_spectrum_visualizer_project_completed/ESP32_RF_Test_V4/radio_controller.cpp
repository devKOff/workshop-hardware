#include "radio_controller.h"
#include "config.h"
#include "packet_protocol.h"
#include "Arduino.h"
#include <SPI.h>
#include <RF24.h>

namespace radio {

RadioController::RadioController(const config::RadioConfig& cfg)
    : config_(cfg), state_(RadioState::UNINITIALIZED), radio_instance_(nullptr) {}

RadioController::~RadioController() {
    end();
}

bool RadioController::begin() {
    if (state_ != RadioState::UNINITIALIZED) return false;
    transitionTo(RadioState::INITIALIZING);

    SPI.begin(config_.sck_pin, config_.miso_pin, config_.mosi_pin, config_.csn_pin);

    auto* radio = new (std::nothrow) RF24(config_.ce_pin, config_.csn_pin);
    if (!radio) {
        reportStatus("Failed to allocate RF24 object", false);
        transitionTo(RadioState::ERROR);
        return false;
    }
    radio_instance_ = radio;

    if (!radio->begin()) {
        reportStatus("RF24 hardware not responding", false);
        delete radio;
        radio_instance_ = nullptr;
        transitionTo(RadioState::ERROR);
        return false;
    }

    radio->setPALevel(static_cast<rf24_pa_dbm_e>(config_.tx_power_dbm));
    radio->setDataRate(static_cast<rf24_datarate_e>(config_.data_rate));
    radio->setPayloadSize(config_.payload_size);
    radio->enableDynamicPayloads();
    radio->enableAckPayload();

    if (!config_.auto_ack) {
        radio->setAutoAck(false);
    }

    radio->setCRCLength(RF24_CRC_16);
    radio->setRetries(3, 5);
    radio->powerDown();

    transitionTo(RadioState::IDLE);
    reportStatus("Radio initialization successful", true);
    return true;
}

void RadioController::end() {
    if (radio_instance_) {
        auto* radio = static_cast<RF24*>(radio_instance_);
        radio->powerDown();
        delete radio;
        radio_instance_ = nullptr;
    }
    transitionTo(RadioState::UNINITIALIZED);
}

bool RadioController::startBurst(uint8_t channel, uint32_t burst_id, uint16_t packet_count, uint16_t interval_ms) {
    if (state_ != RadioState::IDLE) return false;
    if (!isValidChannel(channel)) return false;
    if (packet_count == 0) return false;

    auto* radio = static_cast<RF24*>(radio_instance_);
    if (!radio) return false;

    current_channel_ = channel;
    current_burst_id_ = burst_id;
    packets_to_send_ = packet_count;
    packets_sent_ = 0;
    packets_acked_ = 0;
    packet_interval_ms_ = interval_ms;
    sequence_ = 0;
    last_packet_time_ = 0;

    setChannel(channel);
    radio->powerUp();
    radio->flush_tx();

    transitionTo(RadioState::BURST_IN_PROGRESS);
    reportStatus("Burst started", true);
    return true;
}

void RadioController::update() {
    if (state_ != RadioState::BURST_IN_PROGRESS) return;
    if (packets_sent_ >= packets_to_send_) {
        abortBurst();
        return;
    }

    uint32_t now = millis();
    if (now - last_packet_time_ >= packet_interval_ms_) {
        if (sendPacket()) {
            packets_sent_++;
            sequence_++;
            last_packet_time_ = now;
        } else {
            reportStatus("Packet send failed", false);
        }
    }
}

void RadioController::abortBurst() {
    if (state_ != RadioState::BURST_IN_PROGRESS) return;

    auto* radio = static_cast<RF24*>(radio_instance_);
    if (radio) {
        radio->flush_tx();
        radio->powerDown();
    }

    reportStatus("Burst complete", true);
    transitionTo(RadioState::IDLE);
}

RadioState RadioController::getState() const {
    return state_;
}

uint8_t RadioController::getCurrentChannel() const {
    return current_channel_;
}

uint32_t RadioController::getBurstId() const {
    return current_burst_id_;
}

uint16_t RadioController::getPacketsSent() const {
    return packets_sent_;
}

uint16_t RadioController::getPacketsAcked() const {
    return packets_acked_;
}

const char* RadioController::getStateName() const {
    switch (state_) {
        case RadioState::UNINITIALIZED: return "UNINITIALIZED";
        case RadioState::INITIALIZING: return "INITIALIZING";
        case RadioState::IDLE: return "IDLE";
        case RadioState::BURST_IN_PROGRESS: return "BURST_IN_PROGRESS";
        case RadioState::ERROR: return "ERROR";
        default: return "UNKNOWN";
    }
}

uint32_t RadioController::channelToFrequencyMHz(uint8_t channel) {
    return 2400 + channel;
}

bool RadioController::isValidChannel(uint8_t channel) const {
    return channel >= config_.channel_min && channel <= config_.channel_max;
}

bool RadioController::initializeRadio() {
    return begin();
}

void RadioController::setChannel(uint8_t channel) {
    auto* radio = static_cast<RF24*>(radio_instance_);
    if (radio) {
        radio->setChannel(channel);
    }
}

bool RadioController::sendPacket() {
    auto* radio = static_cast<RF24*>(radio_instance_);
    if (!radio) return false;

    packet::TestPacket pkt{};
    pkt.magic = packet::MAGIC_VALUE;
    pkt.version = packet::CURRENT_VERSION;
    pkt.reserved = 0;
    pkt.burst_id = current_burst_id_;
    pkt.sequence = sequence_;
    pkt.channel = current_channel_;
    packet::fillTestPayload(pkt.payload, sizeof(pkt.payload), sequence_, current_burst_id_);
    uint8_t* pkt_bytes = reinterpret_cast<uint8_t*>(&pkt);
    pkt.crc16 = packet::computeCRC16(pkt_bytes, sizeof(pkt) - 2);

    bool result = radio->write(&pkt, sizeof(pkt));
    if (result && config_.auto_ack) {
        packets_acked_++;
    }
    return result;
}

void RadioController::transitionTo(RadioState new_state) {
    state_ = new_state;
}

void RadioController::reportStatus(const char* message, bool success) {
    if (status_callback_) {
        status_callback_(message, success);
    }
}

void RadioController::setStatusCallback(StatusCallback cb) {
    status_callback_ = cb;
}

MockRadioController::MockRadioController(const config::RadioConfig& cfg)
    : config_(cfg), state_(RadioState::UNINITIALIZED) {}

bool MockRadioController::begin() {
    if (fail_init_) {
        transitionTo(RadioState::ERROR);
        reportStatus("Mock: Init failed (simulated)", false);
        return false;
    }
    transitionTo(RadioState::IDLE);
    reportStatus("Mock: Radio initialization successful", true);
    return true;
}

void MockRadioController::end() {
    transitionTo(RadioState::UNINITIALIZED);
}

bool MockRadioController::startBurst(uint8_t channel, uint32_t burst_id, uint16_t packet_count, uint16_t interval_ms) {
    if (state_ != RadioState::IDLE) return false;
    if (channel < config_.channel_min || channel > config_.channel_max) return false;
    if (packet_count == 0) return false;

    current_channel_ = channel;
    current_burst_id_ = burst_id;
    packets_to_send_ = packet_count;
    packets_sent_ = 0;
    packets_acked_ = 0;
    packet_interval_ms_ = interval_ms;
    sequence_ = 0;
    last_packet_time_ = 0;

    transitionTo(RadioState::BURST_IN_PROGRESS);
    reportStatus("Mock: Burst started", true);
    return true;
}

void MockRadioController::update() {
    if (state_ != RadioState::BURST_IN_PROGRESS) return;
    if (packets_sent_ >= packets_to_send_) {
        abortBurst();
        return;
    }

    uint32_t now = millis();
    if (now - last_packet_time_ >= packet_interval_ms_) {
        if (fail_send_) {
            reportStatus("Mock: Packet send failed (simulated)", false);
            return;
        }
        if (max_packets_sent_ != 0xFFFF && packets_sent_ >= max_packets_sent_) {
            abortBurst();
            return;
        }
        packets_sent_++;
        sequence_++;
        last_packet_time_ = now;
    }
}

void MockRadioController::abortBurst() {
    if (state_ != RadioState::BURST_IN_PROGRESS) return;
    reportStatus("Mock: Burst complete", true);
    transitionTo(RadioState::IDLE);
}

RadioState MockRadioController::getState() const {
    return state_;
}

uint8_t MockRadioController::getCurrentChannel() const {
    return current_channel_;
}

uint32_t MockRadioController::getBurstId() const {
    return current_burst_id_;
}

uint16_t MockRadioController::getPacketsSent() const {
    return packets_sent_;
}

uint16_t MockRadioController::getPacketsAcked() const {
    return packets_acked_;
}

const char* MockRadioController::getStateName() const {
    switch (state_) {
        case RadioState::UNINITIALIZED: return "UNINITIALIZED";
        case RadioState::INITIALIZING: return "INITIALIZING";
        case RadioState::IDLE: return "IDLE";
        case RadioState::BURST_IN_PROGRESS: return "BURST_IN_PROGRESS";
        case RadioState::ERROR: return "ERROR";
        default: return "UNKNOWN";
    }
}

void MockRadioController::setFailInit(bool fail) {
    fail_init_ = fail;
}

void MockRadioController::setFailSend(bool fail) {
    fail_send_ = fail;
}

void MockRadioController::setMaxPacketsSent(uint16_t max) {
    max_packets_sent_ = max;
}

void MockRadioController::setStatusCallback(StatusCallback cb) {
    status_callback_ = cb;
}

bool MockRadioController::isValidChannel(uint8_t channel) const {
    return channel >= config_.channel_min && channel <= config_.channel_max;
}

void MockRadioController::transitionTo(RadioState new_state) {
    state_ = new_state;
}

void MockRadioController::reportStatus(const char* message, bool success) {
    if (status_callback_) {
        status_callback_(message, success);
    }
}

} // namespace radio
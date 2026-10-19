#include "radio_controller.h"
#include "logger.h"

using namespace logger;

namespace radio_controller {

RadioController::RadioController(uint8_t ce_pin, uint8_t csn_pin)
    : radio_(ce_pin, csn_pin), state_(RadioState::UNINITIALIZED),
      last_error_(RadioError::NONE), current_channel_(0), packets_total_(0),
      packets_sent_(0), inter_packet_delay_us_(config::DEFAULT_INTER_PACKET_DELAY_US),
      current_burst_id_(0), last_packet_time_(0) {}

bool RadioController::begin() {
    state_ = RadioState::INITIALIZING;
    last_error_ = RadioError::NONE;

    if (!initializeRadio()) {
        setError(RadioError::INIT_FAILED);
        return false;
    }

    state_ = RadioState::READY;
    LOG_INFO("RADIO", "Radio controller initialized (CE=%u, CSN=%u)", 
             config::PIN_NRF_CE, config::PIN_NRF_CSN);
    return true;
}

void RadioController::end() {
    radio_.powerDown();
    state_ = RadioState::UNINITIALIZED;
    LOG_INFO("RADIO", "Radio controller shut down");
}

void RadioController::update() {
    if (state_ == RadioState::TRANSMITTING) {
        uint32_t now = micros();
        if (now - last_packet_time_ >= inter_packet_delay_us_) {
            if (packets_sent_ < packets_total_) {
                if (!sendPacket()) {
                    LOG_ERROR("RADIO", "Packet send failed at sequence %u", packets_sent_);
                    setError(RadioError::WRITE_FAILED);
                    abortBurst();
                    return;
                }
                packets_sent_++;
                last_packet_time_ = now;

                if (packets_sent_ % 5 == 0) {
                    LOG_DEBUG("RADIO", "Progress: %u/%u packets", packets_sent_, packets_total_);
                }
            } else {
                LOG_INFO("RADIO", "Burst %u complete: %u packets sent", current_burst_id_, packets_sent_);
                radio_.powerDown();
                state_ = RadioState::READY;
            }
        }
    }
}

bool RadioController::startBurst(uint8_t channel, uint16_t packets, uint16_t inter_packet_delay_us) {
    if (state_ != RadioState::READY) {
        LOG_WARN("RADIO", "Cannot start burst: radio not ready (state=%d)", static_cast<uint8_t>(state_));
        setError(RadioError::INVALID_CHANNEL);
        return false;
    }

    if (!config::isValidChannel(channel)) {
        LOG_ERROR("RADIO", "Invalid channel %u (valid: %u-%u)", channel,
                  config::DEFAULT_CHANNEL_MIN, config::DEFAULT_CHANNEL_MAX);
        setError(RadioError::INVALID_CHANNEL);
        return false;
    }

    if (packets == 0 || packets > 255) {
        LOG_ERROR("RADIO", "Invalid packet count %u (must be 1-255)", packets);
        setError(RadioError::INVALID_CHANNEL);
        return false;
    }

    if (!configureChannel(channel)) {
        return false;
    }

    current_channel_ = channel;
    packets_total_ = packets;
    inter_packet_delay_us_ = inter_packet_delay_us;
    current_burst_id_++;
    packets_sent_ = 0;
    last_packet_time_ = 0;

    packet_protocol::createPacket(tx_packet_, current_burst_id_, 0, channel);

    radio_.powerUp();
    radio_.flush_tx();
    radio_.flush_rx();

    state_ = RadioState::TRANSMITTING;
    last_error_ = RadioError::NONE;

    LOG_INFO("RADIO", "Burst %u started: Ch=%u (%u MHz), Packets=%u, Delay=%u us",
             current_burst_id_, channel, config::channelToFrequencyMHz(channel),
             packets, inter_packet_delay_us);

    return true;
}

void RadioController::abortBurst() {
    if (state_ == RadioState::TRANSMITTING) {
        radio_.powerDown();
        LOG_WARN("RADIO", "Burst %u aborted: %u/%u packets sent",
                 current_burst_id_, packets_sent_, packets_total_);
        state_ = RadioState::READY;
    }
}

RadioState RadioController::getState() const { return state_; }
RadioError RadioController::getLastError() const { return last_error_; }
uint16_t RadioController::getPacketsSent() const { return packets_sent_; }
uint16_t RadioController::getPacketsTotal() const { return packets_total_; }
uint8_t RadioController::getCurrentChannel() const { return current_channel_; }
uint16_t RadioController::getCurrentBurstId() const { return current_burst_id_; }

bool RadioController::isBusy() const { return state_ == RadioState::TRANSMITTING; }
bool RadioController::isHealthy() const { return state_ != RadioState::ERROR_STATE && last_error_ == RadioError::NONE; }

bool RadioController::initializeRadio() {
    if (!radio_.begin()) {
        LOG_ERROR("RADIO", "RF24 hardware initialization failed");
        return false;
    }

    radio_.setPALevel(config::RF_PA_LEVEL);
    radio_.setDataRate(config::RF_DATA_RATE);
    radio_.setCRCLength(static_cast<rf24_crclength_e>(config::RF_CRC_LENGTH));
    radio_.setAutoAck(false);
    radio_.setRetries(0, 0);
    radio_.setPayloadSize(packet_protocol::PACKET_SIZE);
    radio_.openWritingPipe(config::PIPE_ADDRESS);
    radio_.stopListening();
    radio_.powerDown();

    LOG_DEBUG("RADIO", "RF24 configured: PA=%d, Rate=%d, CRC=%d, Payload=%u",
              config::RF_PA_LEVEL, config::RF_DATA_RATE, config::RF_CRC_LENGTH,
              packet_protocol::PACKET_SIZE);
    return true;
}

bool RadioController::configureChannel(uint8_t channel) {
    if (!config::isValidChannel(channel)) {
        setError(RadioError::INVALID_CHANNEL);
        return false;
    }
    radio_.setChannel(channel);
    return true;
}

bool RadioController::sendPacket() {
    tx_packet_.sequence = packets_sent_;
    tx_packet_.frequency_mhz = config::channelToFrequencyMHz(current_channel_);

    bool result = radio_.write(&tx_packet_, packet_protocol::PACKET_SIZE);

    if (result) {
        LOG_VERBOSE("RADIO", "TX: Burst=%u Seq=%u Ch=%u Freq=%u MHz",
                    tx_packet_.burst_id, tx_packet_.sequence,
                    tx_packet_.channel, tx_packet_.frequency_mhz);
    }
    return result;
}

void RadioController::setError(RadioError error) {
    last_error_ = error;
    state_ = RadioState::ERROR_STATE;
    LOG_ERROR("RADIO", "Error set: %d", static_cast<uint8_t>(error));
}

void RadioController::resetBurstCounters() {
    packets_sent_ = 0;
    packets_total_ = 0;
    current_burst_id_ = 0;
}

uint8_t RadioController::generateRandomChannel() {
    uint32_t entropy = micros() ^ (ESP.getCycleCount() & 0xFFFF);
    uint8_t channel = config::DEFAULT_CHANNEL_MIN +
                      static_cast<uint8_t>(entropy % (config::DEFAULT_CHANNEL_MAX - config::DEFAULT_CHANNEL_MIN + 1));
    return channel;
}

} // namespace radio_controller
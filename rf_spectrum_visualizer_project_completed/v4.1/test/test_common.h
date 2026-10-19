#ifndef TEST_COMMON_H
#define TEST_COMMON_H

#include <cstdint>
#include <cstring>

uint32_t millis_mock();
extern uint32_t mock_time;
extern bool mock_pin_state;

namespace config {
constexpr uint8_t PIN_NRF_CE = 25;
constexpr uint8_t PIN_NRF_CSN = 5;
constexpr uint8_t PIN_NRF_SCK = 18;
constexpr uint8_t PIN_NRF_MOSI = 23;
constexpr uint8_t PIN_NRF_MISO = 19;
constexpr uint8_t PIN_BUTTON = 4;
constexpr uint8_t PIN_STATUS_LED = 2;
constexpr uint8_t BUTTON_ACTIVE_LEVEL = 0;
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint16_t BUTTON_DEBOUNCE_MS = 50;
constexpr uint16_t BUTTON_LONG_PRESS_MS = 1000;
constexpr uint8_t DEFAULT_CHANNEL_MIN = 0;
constexpr uint8_t DEFAULT_CHANNEL_MAX = 125;
constexpr uint8_t DEFAULT_PACKETS_PER_BURST = 20;
constexpr uint16_t DEFAULT_INTER_PACKET_DELAY_US = 1000;
constexpr uint8_t RF_CHANNEL_DEFAULT = 2;
constexpr uint8_t RF_CRC_LENGTH = 2;
constexpr uint32_t WATCHDOG_TIMEOUT_MS = 5000;
constexpr uint32_t STATE_TIMEOUT_MS = 10000;
constexpr uint64_t PIPE_ADDRESS = 0xE7E7E7E7E7LL;
constexpr const char* FIRMWARE_VERSION = "V4.1";
constexpr const char* PROJECT_NAME = "ESP32 Random-Channel RF Test Generator";
inline uint32_t channelToFrequencyMHz(uint8_t channel) { return 2400u + static_cast<uint32_t>(channel); }
inline bool isValidChannel(uint8_t channel) { return channel <= DEFAULT_CHANNEL_MAX; }
}

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
}

namespace button_handler {
enum class ButtonEvent : uint8_t { NONE = 0, SHORT_PRESS, LONG_PRESS };
enum class ButtonState : uint8_t { IDLE = 0, DEBOUNCE_PRESS, PRESSED, DEBOUNCE_RELEASE, LONG_PRESS_DETECTED };

class ButtonHandler {
public:
    ButtonHandler(uint8_t pin = 4, uint8_t active_level = 0,
                  uint16_t debounce_ms = 50, uint16_t long_press_ms = 1000)
        : pin_(pin), active_level_(active_level), debounce_ms_(debounce_ms),
          long_press_ms_(long_press_ms), state_(ButtonState::IDLE),
          pending_event_(ButtonEvent::NONE), last_change_time_(0),
          press_start_time_(0), last_raw_state_(false) {}

    void begin() {
        last_raw_state_ = readRawState();
        last_change_time_ = 0;
        state_ = ButtonState::IDLE;
        pending_event_ = ButtonEvent::NONE;
    }

    void update() {
        uint32_t now = ::millis_mock();
        bool raw_state = readRawState();

        if (raw_state != last_raw_state_) {
            last_change_time_ = now;
            last_raw_state_ = raw_state;
        }

        switch (state_) {
            case ButtonState::IDLE:
                if (raw_state) transitionTo(ButtonState::DEBOUNCE_PRESS);
                break;
            case ButtonState::DEBOUNCE_PRESS:
                if (!raw_state) transitionTo(ButtonState::IDLE);
                else if (now - last_change_time_ >= debounce_ms_) {
                    press_start_time_ = now;
                    transitionTo(ButtonState::PRESSED);
                }
                break;
            case ButtonState::PRESSED:
                if (!raw_state) transitionTo(ButtonState::DEBOUNCE_RELEASE);
                else if (now - press_start_time_ >= long_press_ms_) {
                    pending_event_ = ButtonEvent::LONG_PRESS;
                    transitionTo(ButtonState::LONG_PRESS_DETECTED);
                }
                break;
            case ButtonState::DEBOUNCE_RELEASE:
                if (raw_state) transitionTo(ButtonState::PRESSED);
                else if (now - last_change_time_ >= debounce_ms_) {
                    if (pending_event_ != ButtonEvent::LONG_PRESS)
                        pending_event_ = ButtonEvent::SHORT_PRESS;
                    transitionTo(ButtonState::IDLE);
                }
                break;
            case ButtonState::LONG_PRESS_DETECTED:
                if (!raw_state) transitionTo(ButtonState::DEBOUNCE_RELEASE);
                break;
        }
    }

    ButtonEvent getEvent() {
        ButtonEvent event = pending_event_;
        pending_event_ = ButtonEvent::NONE;
        return event;
    }

    bool isPressed() const {
        return state_ == ButtonState::PRESSED || state_ == ButtonState::LONG_PRESS_DETECTED;
    }

    uint32_t getPressDuration() const {
        if (state_ == ButtonState::PRESSED || state_ == ButtonState::LONG_PRESS_DETECTED)
            return ::millis_mock() - press_start_time_;
        return 0;
    }

private:
    const uint8_t pin_;
    const uint8_t active_level_;
    const uint16_t debounce_ms_;
    const uint16_t long_press_ms_;
    ButtonState state_;
    ButtonEvent pending_event_;
    uint32_t last_change_time_;
    uint32_t press_start_time_;
    bool last_raw_state_;

    bool readRawState() const { return ::mock_pin_state == false; }
    void transitionTo(ButtonState new_state) { state_ = new_state; last_change_time_ = ::millis_mock(); }
};
}

namespace radio_controller {
enum class RadioState : uint8_t { UNINITIALIZED = 0, INITIALIZING, READY, TRANSMITTING, ERROR_STATE };
enum class RadioError : uint8_t { NONE = 0, INIT_FAILED, WRITE_FAILED, INVALID_CHANNEL, TIMEOUT, HARDWARE_FAULT };

class RadioController {
public:
    RadioController(uint8_t /*ce_pin*/ = config::PIN_NRF_CE,
                    uint8_t /*csn_pin*/ = config::PIN_NRF_CSN)
        : state_(RadioState::UNINITIALIZED), last_error_(RadioError::NONE),
          current_channel_(0), packets_total_(0), packets_sent_(0),
          inter_packet_delay_us_(config::DEFAULT_INTER_PACKET_DELAY_US),
          current_burst_id_(0), last_packet_time_(0), mock_entropy_(0) {}

    bool begin() {
        state_ = RadioState::INITIALIZING;
        last_error_ = RadioError::NONE;
        return initializeRadio();
    }

    void end() { state_ = RadioState::UNINITIALIZED; }
    void update() {}

    bool startBurst(uint8_t channel, uint16_t packets = config::DEFAULT_PACKETS_PER_BURST,
                    uint16_t inter_packet_delay_us = config::DEFAULT_INTER_PACKET_DELAY_US) {
        if (state_ != RadioState::READY) { setError(RadioError::INVALID_CHANNEL); return false; }
        if (!config::isValidChannel(channel)) { setError(RadioError::INVALID_CHANNEL); return false; }
        if (packets == 0 || packets > 255) { setError(RadioError::INVALID_CHANNEL); return false; }
        current_channel_ = channel;
        packets_total_ = packets;
        inter_packet_delay_us_ = inter_packet_delay_us;
        current_burst_id_++;
        packets_sent_ = 0;
        state_ = RadioState::TRANSMITTING;
        last_error_ = RadioError::NONE;
        return true;
    }

    void abortBurst() { if (state_ == RadioState::TRANSMITTING) state_ = RadioState::READY; }

    RadioState getState() const { return state_; }
    RadioError getLastError() const { return last_error_; }
    uint16_t getPacketsSent() const { return packets_sent_; }
    uint16_t getPacketsTotal() const { return packets_total_; }
    uint8_t getCurrentChannel() const { return current_channel_; }
    uint16_t getCurrentBurstId() const { return current_burst_id_; }
    bool isBusy() const { return state_ == RadioState::TRANSMITTING; }
    bool isHealthy() const { return state_ == RadioState::READY && last_error_ == RadioError::NONE; }
    uint8_t generateRandomChannel() {
        return config::DEFAULT_CHANNEL_MIN + (mock_entropy_++ % (config::DEFAULT_CHANNEL_MAX - config::DEFAULT_CHANNEL_MIN + 1));
    }
    void setMockEntropy(uint32_t e) { mock_entropy_ = e; }

private:
    RadioState state_;
    RadioError last_error_;
    uint8_t current_channel_;
    uint16_t packets_total_;
    uint16_t packets_sent_;
    uint16_t inter_packet_delay_us_;
    uint16_t current_burst_id_;
    uint32_t last_packet_time_;
    packet_protocol::TestPacket tx_packet_;
    uint32_t mock_entropy_;

    bool initializeRadio() { state_ = RadioState::READY; return true; }
    void setError(RadioError error) { last_error_ = error; state_ = RadioState::ERROR_STATE; }
};
}

namespace logger {
enum class LogLevel : uint8_t { SILENT = 0, ERROR = 1, WARN = 2, INFO = 3, DEBUG = 4, VERBOSE = 5 };
}

#endif
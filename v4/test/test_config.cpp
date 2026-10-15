#include "config.h"
#include <cassert>
#include <cstdio>

using namespace config;

void testDefaultConfig() {
    const AppConfig& cfg = getDefaultConfig();
    assert(cfg.radio.channel_min == MIN_CHANNEL);
    assert(cfg.radio.channel_max == MAX_CHANNEL);
    assert(cfg.radio.packets_per_burst == 20);
    assert(cfg.radio.packet_interval_ms == 10);
    assert(cfg.radio.tx_power_dbm == -12);
    assert(cfg.radio.payload_size == 32);
    assert(cfg.button.pin == 4);
    assert(cfg.button.debounce_ms == 50);
    assert(cfg.led.pin == 2);
    assert(cfg.logging.baud_rate == 115200);
    printf("testDefaultConfig: PASSED\n");
}

void testValidateRadioConfigValid() {
    RadioConfig cfg{};
    cfg.channel_min = 10;
    cfg.channel_max = 80;
    cfg.packets_per_burst = 50;
    cfg.packet_interval_ms = 20;
    cfg.tx_power_dbm = -6;
    cfg.payload_size = 32;
    assert(validateRadioConfig(cfg));
    printf("testValidateRadioConfigValid: PASSED\n");
}

void testValidateRadioConfigInvalidMinMax() {
    RadioConfig cfg{};
    cfg.channel_min = 50;
    cfg.channel_max = 10;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigInvalidMinMax: PASSED\n");
}

void testValidateRadioConfigOutOfBounds() {
    RadioConfig cfg{};
    cfg.channel_min = 0;
    cfg.channel_max = 130;
    assert(!validateRadioConfig(cfg));
    cfg.channel_min = 255;
    cfg.channel_max = 255;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigOutOfBounds: PASSED\n");
}

void testValidateRadioConfigInvalidPackets() {
    RadioConfig cfg{};
    cfg.packets_per_burst = 0;
    assert(!validateRadioConfig(cfg));
    cfg.packets_per_burst = 2000;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigInvalidPackets: PASSED\n");
}

void testValidateRadioConfigInvalidInterval() {
    RadioConfig cfg{};
    cfg.packet_interval_ms = 0;
    assert(!validateRadioConfig(cfg));
    cfg.packet_interval_ms = 20000;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigInvalidInterval: PASSED\n");
}

void testValidateRadioConfigInvalidPower() {
    RadioConfig cfg{};
    cfg.tx_power_dbm = -20;
    assert(!validateRadioConfig(cfg));
    cfg.tx_power_dbm = 5;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigInvalidPower: PASSED\n");
}

void testValidateRadioConfigInvalidPayload() {
    RadioConfig cfg{};
    cfg.payload_size = 0;
    assert(!validateRadioConfig(cfg));
    cfg.payload_size = 33;
    assert(!validateRadioConfig(cfg));
    printf("testValidateRadioConfigInvalidPayload: PASSED\n");
}

void testValidateButtonConfig() {
    ButtonConfig cfg{};
    cfg.debounce_ms = 50;
    assert(validateButtonConfig(cfg));
    cfg.debounce_ms = 0;
    assert(!validateButtonConfig(cfg));
    cfg.debounce_ms = 2000;
    assert(!validateButtonConfig(cfg));
    printf("testValidateButtonConfig: PASSED\n");
}

void testValidateAppConfig() {
    AppConfig cfg = getDefaultConfig();
    assert(validateAppConfig(cfg));
    cfg.radio.channel_min = 100;
    cfg.radio.channel_max = 50;
    assert(!validateAppConfig(cfg));
    printf("testValidateAppConfig: PASSED\n");
}

void testMutableConfig() {
    AppConfig& cfg = getMutableConfig();
    cfg.radio.channel_min = 5;
    cfg.radio.channel_max = 100;
    const AppConfig& cfg2 = getDefaultConfig();
    assert(cfg2.radio.channel_min == 5);
    assert(cfg2.radio.channel_max == 100);
    printf("testMutableConfig: PASSED\n");
}

int main() {
    testDefaultConfig();
    testValidateRadioConfigValid();
    testValidateRadioConfigInvalidMinMax();
    testValidateRadioConfigOutOfBounds();
    testValidateRadioConfigInvalidPackets();
    testValidateRadioConfigInvalidInterval();
    testValidateRadioConfigInvalidPower();
    testValidateRadioConfigInvalidPayload();
    testValidateButtonConfig();
    testValidateAppConfig();
    testMutableConfig();
    printf("\nAll config tests PASSED\n");
    return 0;
}
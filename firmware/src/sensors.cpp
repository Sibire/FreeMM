#include "sensors.h"
#include "config.h"
#include <Wire.h>

bool selectMuxChannel(uint8_t channel) {
    if (channel > 7) return false;
    Wire.beginTransmission(ADDR_MUX);
    Wire.write(1 << channel);
    return Wire.endTransmission() == 0;
}

float readAngleRaw() {
    Wire.beginTransmission(ADDR_AS5600);
    Wire.write(REG_RAW_ANGLE);
    if (Wire.endTransmission(false) != 0) return -1.0f;

    Wire.requestFrom((uint8_t)ADDR_AS5600, (uint8_t)2);
    if (Wire.available() < 2) return -1.0f;

    uint16_t highByte = Wire.read();
    uint16_t lowByte = Wire.read();
    uint16_t raw = ((highByte & 0x0F) << 8) | lowByte;  // 12-bit value

    return raw * 360.0f / 4096.0f;
}

uint8_t readAGC() {
    Wire.beginTransmission(ADDR_AS5600);
    Wire.write(REG_AGC);
    if (Wire.endTransmission(false) != 0) return 0;

    Wire.requestFrom((uint8_t)ADDR_AS5600, (uint8_t)1);
    if (Wire.available() < 1) return 0;

    return Wire.read();
}

bool sensorPresent(uint8_t channel) {
    if (!selectMuxChannel(channel)) return false;
    Wire.beginTransmission(ADDR_AS5600);
    return Wire.endTransmission() == 0;
}

bool initSensors() {
    Wire.begin(PIN_SDA, PIN_SCL);
    Wire.setClock(100000);  // 100kHz I2C

    // Verify mux is responding
    Wire.beginTransmission(ADDR_MUX);
    if (Wire.endTransmission() != 0) {
        Serial.println("# ERROR: TCA9548A mux not found at 0x70");
        return false;
    }
    Serial.println("# TCA9548A mux found");

    // Check each joint sensor
    for (uint8_t ch = 0; ch < NUM_JOINTS; ch++) {
        if (sensorPresent(ch)) {
            uint8_t agc = readAGC();
            Serial.printf("# J%d (CH%d): AS5600 OK, AGC=%d\n", ch + 1, ch, agc);
        } else {
            Serial.printf("# J%d (CH%d): AS5600 NOT FOUND\n", ch + 1, ch);
        }
    }
    return true;
}

void readJointAngles(float angles[5]) {
    for (uint8_t ch = 0; ch < NUM_JOINTS; ch++) {
        if (selectMuxChannel(ch)) {
            angles[ch] = readAngleRaw();
        } else {
            angles[ch] = -1.0f;  // Error
        }
    }
}

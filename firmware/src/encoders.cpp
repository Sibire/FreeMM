#include "encoders.h"
#include "config.h"
#include <Wire.h>

void selectMuxChannel(uint8_t channel) {
    Wire.beginTransmission(ADDR_TCA9548A);
    Wire.write(1 << channel);
    Wire.endTransmission();
}

uint16_t readAS5600Raw() {
    Wire.beginTransmission(ADDR_AS5600);
    Wire.write(REG_RAW_ANGLE);
    if (Wire.endTransmission(false) != 0) {
        return 0xFFFF; // error sentinel
    }

    Wire.requestFrom((uint8_t)ADDR_AS5600, (uint8_t)2);
    if (Wire.available() < 2) {
        return 0xFFFF; // error sentinel
    }

    uint16_t highByte = Wire.read();
    uint16_t lowByte  = Wire.read();
    uint16_t raw = ((highByte & 0x0F) << 8) | lowByte; // 12-bit value
    return raw;
}

uint8_t readAS5600AGC() {
    Wire.beginTransmission(ADDR_AS5600);
    Wire.write(REG_AGC);
    if (Wire.endTransmission(false) != 0) {
        return 0;
    }

    Wire.requestFrom((uint8_t)ADDR_AS5600, (uint8_t)1);
    if (Wire.available() < 1) {
        return 0;
    }

    return Wire.read();
}

void initEncoders() {
    Wire.begin(PIN_SDA, PIN_SCL);
    Wire.setClock(I2C_CLOCK);

    // Verify TCA9548A mux responds
    Wire.beginTransmission(ADDR_TCA9548A);
    if (Wire.endTransmission() != 0) {
        Serial.println("# ERROR: TCA9548A mux not found at 0x70");
    } else {
        Serial.println("# TCA9548A mux found");
    }

    // Scan channels 0-4 for AS5600 sensors
    for (uint8_t ch = 0; ch < NUM_JOINTS; ch++) {
        selectMuxChannel(ch);
        Wire.beginTransmission(ADDR_AS5600);
        if (Wire.endTransmission() == 0) {
            uint8_t agc = readAS5600AGC();
            Serial.printf("# J%d (CH%d): AS5600 OK, AGC=%d\n", ch + 1, ch, agc);
        } else {
            Serial.printf("# J%d (CH%d): AS5600 NOT FOUND\n", ch + 1, ch);
        }
    }
}

bool readAllJoints(float angles[5]) {
    for (uint8_t ch = 0; ch < NUM_JOINTS; ch++) {
        selectMuxChannel(ch);
        uint16_t raw = readAS5600Raw();
        if (raw == 0xFFFF) {
            return false;
        }
        angles[ch] = (float)raw * 2.0f * PI / 4096.0f;
    }
    return true;
}

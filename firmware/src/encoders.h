#pragma once

#include <Arduino.h>

// Initialize I2C at 400kHz, verify TCA9548A, scan channels 0-4 for AS5600
void initEncoders();

// Read all 5 joint angles in radians. Returns false if any read fails.
bool readAllJoints(float angles[5]);

// Select a mux channel on the TCA9548A (0-7)
void selectMuxChannel(uint8_t channel);

// Read raw 12-bit angle value from AS5600 on the currently selected mux channel
uint16_t readAS5600Raw();

// Read AGC register from AS5600 for diagnostics (ideal ~128)
uint8_t readAS5600AGC();

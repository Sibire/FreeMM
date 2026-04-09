#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

// Initialize I2C and verify mux + sensors
bool initSensors();

// Select a mux channel (0-7)
bool selectMuxChannel(uint8_t channel);

// Read raw 12-bit angle from AS5600 on the currently selected mux channel
// Returns angle in degrees (0-360)
float readAngleRaw();

// Read all 5 joint angles into the provided array (degrees)
void readJointAngles(float angles[5]);

// Read AGC value for diagnostics (0-255, ideal ~128)
uint8_t readAGC();

// Check if a sensor is responding on the given mux channel
bool sensorPresent(uint8_t channel);

#endif

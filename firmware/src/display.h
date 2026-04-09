#pragma once

#include <Arduino.h>
#include "kinematics.h"

// Initialize SSD1306 OLED at 0x3C on the main I2C bus
void initDisplay();

// Update the display with current state. Only redraws if 100ms+ since last update.
// mode: 0=IDLE, 1=POINT_SAMPLE, 2=TRACE_ACTIVE
void updateDisplay(const float angles[5], const Vec3& tip, int pointCount, int mode);

// Cycle through display pages (0=XYZ, 1=Angles, 2=Status)
void cycleDisplayPage();

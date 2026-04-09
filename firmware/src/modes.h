#pragma once

#include <Arduino.h>
#include "kinematics.h"

// Mode states
enum ModeState {
    MODE_IDLE          = 0,
    MODE_POINT_SAMPLE  = 1,
    MODE_TRACE_ACTIVE  = 2
};

// Initialize mode state machine (starts in IDLE)
void initModes();

// Run the mode state machine. Call once per loop after buttons and serial parsing.
// cmdChar: the serial command character received this loop (0 if none).
// sampleBtn: true if the sample/foot button had a falling edge this loop.
void handleModeLogic(const float angles[5], const FKResult& fk, char cmdChar, bool sampleBtn);

// Return the current mode (for display)
int getMode();

// Return total points sampled so far
int getPointCount();

// Reset point and trace counters
void resetCounters();

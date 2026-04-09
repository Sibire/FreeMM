#pragma once

#include <Arduino.h>

// Configure GPIO 25, 26, 27 as INPUT_PULLUP
void initButtons();

// Read all buttons and apply debounce. Call once per loop iteration.
void updateButtons();

// Returns true on falling edge of Sample button (GPIO 26) OR FootPedal (GPIO 25)
bool samplePressed();

// Returns true on falling edge of Mode button (GPIO 27)
bool modePressed();

#pragma once

#include <Arduino.h>

// --- Pin Assignments ---
#define PIN_SDA        21
#define PIN_SCL        22
#define PIN_BTN_SAMPLE 26
#define PIN_BTN_MODE   27
#define PIN_BTN_FOOT   25

// --- I2C Addresses ---
#define ADDR_TCA9548A  0x70
#define ADDR_AS5600    0x36
#define ADDR_OLED      0x3C

// --- AS5600 Registers ---
#define REG_RAW_ANGLE  0x0E   // 12-bit raw angle (2 bytes, big-endian)
#define REG_AGC        0x1A   // Automatic gain control

// --- Display ---
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64

// --- Link Lengths (mm) — measured from Fusion assembly ---
#define BASE_HEIGHT    38.0f
#define UPPER_ARM     330.1f
#define FOREARM       330.1f
#define WRIST_LINK     36.0f
#define PROBE_LEN      77.3f
#define BALL_RADIUS     0.5f

// --- Joint Count ---
#define NUM_JOINTS     5

// --- Serial ---
#define SERIAL_BAUD    115200

// --- I2C ---
#define I2C_CLOCK      400000

// --- Timing ---
#define OLED_UPDATE_INTERVAL_MS  100
#define DEBOUNCE_MS               20
#define TRACE_MIN_DIST_DEFAULT    1.0f  // mm

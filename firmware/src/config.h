#ifndef CONFIG_H
#define CONFIG_H

// --- Pin Assignments ---
#define PIN_SDA        21
#define PIN_SCL        22
#define PIN_BTN_SAMPLE 26
#define PIN_BTN_MODE   27
#define PIN_BTN_FOOT   25

// --- I2C Addresses ---
#define ADDR_MUX       0x70   // TCA9548A
#define ADDR_AS5600    0x36   // All AS5600 share this address (muxed)
#define ADDR_OLED      0x3C   // SSD1306 (on main bus, NOT through mux)

// --- AS5600 Registers ---
#define REG_RAW_ANGLE  0x0C   // 12-bit raw angle (2 bytes, big-endian)
#define REG_AGC        0x1A   // Automatic gain control

// --- Mux Channels ---
#define CH_J1  0
#define CH_J2  1
#define CH_J3  2
#define CH_J4  3
#define CH_J5  4
#define NUM_JOINTS 5

// --- Link Lengths (mm) — PLACEHOLDER, measure from Fusion assembly ---
#define BASE_HEIGHT  50.0f
#define UPPER_ARM   150.0f
#define FOREARM     130.0f
#define WRIST_LINK   30.0f
#define PROBE_LEN    20.0f
#define BALL_RADIUS   0.5f

// --- Joint Limits (degrees) ---
#define J1_MIN -180.0f
#define J1_MAX  180.0f
#define J2_MIN -105.0f
#define J2_MAX  105.0f
#define J3_MIN -145.0f
#define J3_MAX  145.0f
#define J4_MIN -180.0f
#define J4_MAX  180.0f
#define J5_MIN -145.0f
#define J5_MAX  145.0f

// --- Timing ---
#define ANGLE_STREAM_INTERVAL_MS 20   // ~50Hz angle streaming
#define DEBOUNCE_MS              50
#define TRACE_MIN_DISTANCE_DEFAULT 1.0f  // mm

// --- OLED ---
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64

#endif

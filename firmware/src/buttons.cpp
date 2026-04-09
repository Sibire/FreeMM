#include "buttons.h"
#include "config.h"

static bool s_samplePrev  = HIGH;
static bool s_modePrev    = HIGH;
static bool s_footPrev    = HIGH;

static unsigned long s_sampleLastChange = 0;
static unsigned long s_modeLastChange   = 0;
static unsigned long s_footLastChange   = 0;

static bool s_sampleEdge = false;
static bool s_modeEdge   = false;

void initButtons() {
    pinMode(PIN_BTN_SAMPLE, INPUT_PULLUP);
    pinMode(PIN_BTN_MODE,   INPUT_PULLUP);
    pinMode(PIN_BTN_FOOT,   INPUT_PULLUP);
}

void updateButtons() {
    unsigned long now = millis();
    s_sampleEdge = false;
    s_modeEdge   = false;

    // Sample button (GPIO 26)
    bool sampleNow = digitalRead(PIN_BTN_SAMPLE);
    if (sampleNow != s_samplePrev && (now - s_sampleLastChange) > DEBOUNCE_MS) {
        if (sampleNow == LOW) {
            s_sampleEdge = true;  // falling edge
        }
        s_samplePrev = sampleNow;
        s_sampleLastChange = now;
    }

    // Mode button (GPIO 27)
    bool modeNow = digitalRead(PIN_BTN_MODE);
    if (modeNow != s_modePrev && (now - s_modeLastChange) > DEBOUNCE_MS) {
        if (modeNow == LOW) {
            s_modeEdge = true;  // falling edge
        }
        s_modePrev = modeNow;
        s_modeLastChange = now;
    }

    // Foot pedal (GPIO 25) — treated same as sample button
    bool footNow = digitalRead(PIN_BTN_FOOT);
    if (footNow != s_footPrev && (now - s_footLastChange) > DEBOUNCE_MS) {
        if (footNow == LOW) {
            s_sampleEdge = true;  // falling edge, same as sample
        }
        s_footPrev = footNow;
        s_footLastChange = now;
    }
}

bool samplePressed() {
    return s_sampleEdge;
}

bool modePressed() {
    return s_modeEdge;
}

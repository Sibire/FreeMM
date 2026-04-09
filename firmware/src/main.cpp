#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "encoders.h"
#include "kinematics.h"
#include "serial_protocol.h"
#include "buttons.h"
#include "display.h"
#include "modes.h"

void setup() {
    Serial.begin(SERIAL_BAUD);

    // I2C is initialized inside initEncoders (Wire.begin + setClock)
    initEncoders();
    initDisplay();
    initButtons();
    initModes();

    sendStatus("DIYgitizer ready");
}

void loop() {
    float angles[5];

    if (!readAllJoints(angles)) {
        // Sensor read failed — skip this cycle
        return;
    }

    FKResult fk = computeFK(angles);

    // Continuous angle stream
    sendAngles(angles);

    // Read buttons
    updateButtons();
    bool sample = samplePressed();
    bool mode   = modePressed();

    // Check serial commands
    char cmd = parseCommand();

    // Cycle display page on mode button press
    if (mode) {
        cycleDisplayPage();
    }

    // Run mode state machine (handles 'p', 't', '1'/'2'/'3', 'r', and sample button)
    handleModeLogic(angles, fk, cmd, sample);

    // Update OLED (rate-limited internally to OLED_UPDATE_INTERVAL_MS)
    updateDisplay(angles, fk.tip, getPointCount(), getMode());
}

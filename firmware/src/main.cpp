#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SSD1306.h>
#include "config.h"
#include "sensors.h"
#include "kinematics.h"

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// --- State ---
enum Mode { MODE_CMM, MODE_TRACE, MODE_DIGITIZER, MODE_COUNT };
const char* MODE_NAMES[] = {"CMM", "TRACE", "DIGI"};

Mode currentMode = MODE_CMM;
float jointAngles[NUM_JOINTS] = {0};
Vec3 tipPos = {0, 0, 0};

// Point sampling
uint32_t pointIndex = 0;

// Trace state
bool tracing = false;
uint32_t traceIndex = 0;
uint8_t tracePlane = 1;          // 0=XY, 1=XZ, 2=YZ
float traceMinDist = TRACE_MIN_DISTANCE_DEFAULT;
Vec3 lastTracePos = {0, 0, 0};

// Timing
unsigned long lastStreamMs = 0;
unsigned long lastBtnSample = 0;
unsigned long lastBtnMode = 0;
unsigned long lastBtnFoot = 0;

// Button state
bool btnSamplePrev = HIGH;
bool btnModePrev = HIGH;
bool btnFootPrev = HIGH;

// --- Helpers ---

float dist3d(Vec3 a, Vec3 b) {
    float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return sqrtf(dx*dx + dy*dy + dz*dz);
}

void getTraceCoords(Vec3 pos, uint8_t plane, float &a, float &b) {
    switch (plane) {
        case 0: a = pos.x; b = pos.y; break;  // XY
        case 1: a = pos.x; b = pos.z; break;  // XZ
        case 2: a = pos.y; b = pos.z; break;  // YZ
    }
}

void samplePoint() {
    Serial.printf("POINT,%lu,%.2f,%.2f,%.2f\n", pointIndex, tipPos.x, tipPos.y, tipPos.z);
    pointIndex++;
}

void tracePoint() {
    if (dist3d(tipPos, lastTracePos) >= traceMinDist) {
        float a, b;
        getTraceCoords(tipPos, tracePlane, a, b);
        Serial.printf("TRACE,%lu,%.2f,%.2f\n", traceIndex, a, b);
        traceIndex++;
        lastTracePos = tipPos;
    }
}

void toggleTrace() {
    tracing = !tracing;
    if (tracing) {
        traceIndex = 0;
        lastTracePos = tipPos;
        const char* planeNames[] = {"XY", "XZ", "YZ"};
        Serial.printf("# TRACE START plane=%s\n", planeNames[tracePlane]);
    } else {
        Serial.println("# TRACE STOP");
    }
}

void cycleMode() {
    currentMode = (Mode)((currentMode + 1) % MODE_COUNT);
    Serial.printf("# MODE %s\n", MODE_NAMES[currentMode]);
}

// --- Serial Command Parsing ---

void parseSerialCommand() {
    while (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() == 0) continue;

        char c = cmd.charAt(0);
        switch (c) {
            case 'p': samplePoint(); break;
            case 't': toggleTrace(); break;
            case '1': tracePlane = 0; Serial.println("# PLANE XY"); break;
            case '2': tracePlane = 1; Serial.println("# PLANE XZ"); break;
            case '3': tracePlane = 2; Serial.println("# PLANE YZ"); break;
            case 'd':
                if (cmd.length() > 1) {
                    traceMinDist = cmd.substring(1).toFloat();
                    Serial.printf("# TRACE_DIST %.2f\n", traceMinDist);
                }
                break;
            case 'r':
                pointIndex = 0;
                traceIndex = 0;
                Serial.println("# RESET");
                break;
            default:
                Serial.printf("# UNKNOWN CMD: %s\n", cmd.c_str());
                break;
        }
    }
}

// --- Button Handling ---

void handleButtons() {
    unsigned long now = millis();

    // Sample button (GPIO 26) — press to sample point
    bool btnSample = digitalRead(PIN_BTN_SAMPLE);
    if (btnSample == LOW && btnSamplePrev == HIGH && (now - lastBtnSample) > DEBOUNCE_MS) {
        samplePoint();
        lastBtnSample = now;
    }
    btnSamplePrev = btnSample;

    // Mode button (GPIO 27) — press to cycle mode
    bool btnMode = digitalRead(PIN_BTN_MODE);
    if (btnMode == LOW && btnModePrev == HIGH && (now - lastBtnMode) > DEBOUNCE_MS) {
        cycleMode();
        lastBtnMode = now;
    }
    btnModePrev = btnMode;

    // Foot pedal (GPIO 25) — same as sample in CMM/DIGI, toggles trace in TRACE mode
    bool btnFoot = digitalRead(PIN_BTN_FOOT);
    if (btnFoot == LOW && btnFootPrev == HIGH && (now - lastBtnFoot) > DEBOUNCE_MS) {
        if (currentMode == MODE_TRACE) {
            toggleTrace();
        } else {
            samplePoint();
        }
        lastBtnFoot = now;
    }
    btnFootPrev = btnFoot;
}

// --- OLED Display ---

void updateDisplay() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    // Line 1: Mode + connection
    display.setCursor(0, 0);
    display.printf("[%s]", MODE_NAMES[currentMode]);
    if (tracing) {
        display.print(" TRACING");
    }

    // Line 2-3: XYZ position
    display.setCursor(0, 16);
    display.printf("X:%.1f Y:%.1f", tipPos.x, tipPos.y);
    display.setCursor(0, 28);
    display.printf("Z:%.1f", tipPos.z);

    // Line 4: Point count
    display.setCursor(0, 44);
    display.printf("Pts:%lu", pointIndex);
    if (tracing) {
        display.printf(" Tr:%lu", traceIndex);
    }

    display.display();
}

// --- Setup ---

void setup() {
    Serial.begin(115200);
    Serial.println("# DIYgitizer v1.0");

    // Buttons
    pinMode(PIN_BTN_SAMPLE, INPUT_PULLUP);
    pinMode(PIN_BTN_MODE, INPUT_PULLUP);
    pinMode(PIN_BTN_FOOT, INPUT_PULLUP);

    // OLED (on main I2C bus, before mux takes over)
    if (display.begin(SSD1306_SWITCHCAPVCC, ADDR_OLED)) {
        display.clearDisplay();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(0, 0);
        display.println("DIYgitizer");
        display.println("Starting...");
        display.display();
        Serial.println("# OLED OK");
    } else {
        Serial.println("# OLED FAIL");
    }

    // Sensors
    if (initSensors()) {
        Serial.println("# SENSORS OK");
    } else {
        Serial.println("# SENSORS FAIL — check wiring");
    }

    Serial.println("# READY");
}

// --- Main Loop ---

void loop() {
    // Read sensors and compute FK
    readJointAngles(jointAngles);
    tipPos = forwardKinematics(jointAngles);

    // Stream angles at ~50Hz
    unsigned long now = millis();
    if (now - lastStreamMs >= ANGLE_STREAM_INTERVAL_MS) {
        Serial.printf("ANGLES,%.2f,%.2f,%.2f,%.2f,%.2f\n",
            jointAngles[0], jointAngles[1], jointAngles[2],
            jointAngles[3], jointAngles[4]);
        lastStreamMs = now;
    }

    // Trace mode: emit points if moving
    if (tracing) {
        tracePoint();
    }

    // Handle serial commands from PC
    parseSerialCommand();

    // Handle physical buttons
    handleButtons();

    // Update OLED (~10Hz is fine, display is slow)
    static unsigned long lastDisplayMs = 0;
    if (now - lastDisplayMs >= 100) {
        updateDisplay();
        lastDisplayMs = now;
    }
}

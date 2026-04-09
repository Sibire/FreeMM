#include "display.h"
#include "config.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

static Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
static unsigned long s_lastUpdateMs = 0;
static int s_displayPage = 0;
static bool s_initialized = false;

void initDisplay() {
    if (oled.begin(SSD1306_SWITCHCAPVCC, ADDR_OLED)) {
        s_initialized = true;
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setTextColor(SSD1306_WHITE);
        oled.setCursor(0, 0);
        oled.println("DIYgitizer");
        oled.println("Starting...");
        oled.display();
    } else {
        Serial.println("# OLED init failed");
    }
}

// Cycle display page. Called externally when mode button pressed.
void cycleDisplayPage() {
    s_displayPage = (s_displayPage + 1) % 3;
}

static void drawPageXYZ(const Vec3& tip) {
    // Large-ish text for XYZ position
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.print("== POSITION (mm) ==");

    oled.setTextSize(2);
    oled.setCursor(0, 14);
    oled.printf("X:%.1f", tip.x);
    oled.setCursor(0, 32);
    oled.printf("Y:%.1f", tip.y);
    oled.setCursor(0, 50);
    oled.printf("Z:%.1f", tip.z);
}

static void drawPageAngles(const float angles[5]) {
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.print("== JOINT ANGLES ==");

    for (int i = 0; i < NUM_JOINTS; i++) {
        oled.setCursor(0, 12 + i * 10);
        float deg = angles[i] * 180.0f / PI;
        oled.printf("J%d: %7.2f deg", i + 1, deg);
    }
}

static void drawPageStatus(int pointCount, int mode) {
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.print("== STATUS ==");

    oled.setTextSize(2);
    oled.setCursor(0, 16);
    oled.printf("Pts:%d", pointCount);

    oled.setCursor(0, 40);
    oled.setTextSize(1);
    const char* modeNames[] = {"IDLE", "POINT", "TRACE"};
    if (mode >= 0 && mode <= 2) {
        oled.printf("Mode: %s", modeNames[mode]);
    } else {
        oled.printf("Mode: %d", mode);
    }
}

void updateDisplay(const float angles[5], const Vec3& tip, int pointCount, int mode) {
    if (!s_initialized) return;

    unsigned long now = millis();
    if (now - s_lastUpdateMs < OLED_UPDATE_INTERVAL_MS) return;
    s_lastUpdateMs = now;

    // The OLED is on the main I2C bus (not behind the TCA9548A mux).
    // The mux only routes its downstream channels; the OLED at 0x3C on the
    // main bus is always directly accessible regardless of the mux channel
    // selection. No special mux handling is needed here.

    oled.clearDisplay();

    switch (s_displayPage) {
        case 0:
            drawPageXYZ(tip);
            break;
        case 1:
            drawPageAngles(angles);
            break;
        case 2:
            drawPageStatus(pointCount, mode);
            break;
    }

    oled.display();
}

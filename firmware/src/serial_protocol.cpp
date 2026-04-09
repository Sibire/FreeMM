#include "serial_protocol.h"
#include "config.h"

static float s_traceMinDist = TRACE_MIN_DIST_DEFAULT;

void sendAngles(const float angles[5]) {
    // Convert radians to degrees for transmission
    Serial.printf("ANGLES,%.2f,%.2f,%.2f,%.2f,%.2f\n",
        angles[0] * 180.0f / PI,
        angles[1] * 180.0f / PI,
        angles[2] * 180.0f / PI,
        angles[3] * 180.0f / PI,
        angles[4] * 180.0f / PI);
}

void sendPoint(int idx, const Vec3& tip) {
    Serial.printf("POINT,%d,%.3f,%.3f,%.3f\n", idx, tip.x, tip.y, tip.z);
}

void sendTrace(int idx, float a, float b) {
    Serial.printf("TRACE,%d,%.3f,%.3f\n", idx, a, b);
}

void sendStatus(const char* msg) {
    Serial.printf("# %s\n", msg);
}

char parseCommand() {
    if (!Serial.available()) {
        return 0;
    }

    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) {
        return 0;
    }

    char cmd = line.charAt(0);

    if (cmd == 'd' && line.length() > 1) {
        float val = line.substring(1).toFloat();
        if (val > 0.0f) {
            s_traceMinDist = val;
            char buf[48];
            snprintf(buf, sizeof(buf), "TRACE_DIST %.2f", s_traceMinDist);
            sendStatus(buf);
        }
    }

    return cmd;
}

float getTraceMinDist() {
    return s_traceMinDist;
}

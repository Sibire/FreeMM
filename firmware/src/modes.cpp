#include "modes.h"
#include "config.h"
#include "serial_protocol.h"
#include <math.h>

static ModeState s_mode = MODE_IDLE;
static int s_pointCount = 0;
static int s_traceCount = 0;
static Vec3 s_lastTracePos = {0.0f, 0.0f, 0.0f};
static uint8_t s_tracePlane = 1; // 0=XY, 1=XZ, 2=YZ

static float dist3d(const Vec3& a, const Vec3& b) {
    float dx = a.x - b.x;
    float dy = a.y - b.y;
    float dz = a.z - b.z;
    return sqrtf(dx * dx + dy * dy + dz * dz);
}

static void getTraceCoords(const Vec3& pos, uint8_t plane, float& a, float& b) {
    switch (plane) {
        case 0: a = pos.x; b = pos.y; break; // XY
        case 1: a = pos.x; b = pos.z; break; // XZ
        case 2: a = pos.y; b = pos.z; break; // YZ
        default: a = pos.x; b = pos.z; break;
    }
}

void initModes() {
    s_mode = MODE_IDLE;
    s_pointCount = 0;
    s_traceCount = 0;
    s_lastTracePos = {0.0f, 0.0f, 0.0f};
    s_tracePlane = 1;
}

void handleModeLogic(const float angles[5], const FKResult& fk, char cmdChar, bool sampleBtn) {
    // Handle trace plane selection commands regardless of mode
    if (cmdChar == '1') { s_tracePlane = 0; sendStatus("PLANE XY"); }
    if (cmdChar == '2') { s_tracePlane = 1; sendStatus("PLANE XZ"); }
    if (cmdChar == '3') { s_tracePlane = 2; sendStatus("PLANE YZ"); }

    // Handle reset command
    if (cmdChar == 'r') {
        resetCounters();
        sendStatus("RESET");
    }

    switch (s_mode) {
        case MODE_IDLE:
            // Sample a point on button press or 'p' command
            if (sampleBtn || cmdChar == 'p') {
                sendPoint(s_pointCount, fk.tip);
                s_pointCount++;
            }
            // Start tracing on 't' command
            if (cmdChar == 't') {
                s_mode = MODE_TRACE_ACTIVE;
                s_traceCount = 0;
                s_lastTracePos = fk.tip;
                sendStatus("TRACE START");
            }
            break;

        case MODE_TRACE_ACTIVE:
            // Emit trace point if moved far enough
            {
                float minDist = getTraceMinDist();
                if (dist3d(fk.tip, s_lastTracePos) >= minDist) {
                    float a, b;
                    getTraceCoords(fk.tip, s_tracePlane, a, b);
                    sendTrace(s_traceCount, a, b);
                    s_traceCount++;
                    s_lastTracePos = fk.tip;
                }
            }
            // Stop tracing on 't' command or sample button
            if (cmdChar == 't' || sampleBtn) {
                s_mode = MODE_IDLE;
                sendStatus("TRACE STOP");
            }
            break;

        default:
            s_mode = MODE_IDLE;
            break;
    }
}

int getMode() {
    return (int)s_mode;
}

int getPointCount() {
    return s_pointCount;
}

void resetCounters() {
    s_pointCount = 0;
    s_traceCount = 0;
}

#include "kinematics.h"
#include "config.h"
#include <math.h>

#define DEG2RAD (M_PI / 180.0f)

void forwardKinematicsFull(const float angles[5], Vec3 positions[6]) {
    float j1 = angles[0] * DEG2RAD;
    float j2 = angles[1] * DEG2RAD;
    float j3 = angles[2] * DEG2RAD;
    float j4 = angles[3] * DEG2RAD;
    float j5 = angles[4] * DEG2RAD;

    float c1 = cosf(j1), s1 = sinf(j1);

    // Base (origin at desk surface, Z up)
    positions[0] = {0, 0, 0};

    // Shoulder (top of base plate)
    positions[1] = {0, 0, BASE_HEIGHT};

    // Elbow (end of upper arm)
    float c2 = cosf(j2), s2 = sinf(j2);
    positions[2] = {
        UPPER_ARM * c2 * c1,
        UPPER_ARM * c2 * s1,
        BASE_HEIGHT + UPPER_ARM * s2
    };

    // Wrist (end of forearm)
    float pitch23 = j2 + j3;
    float cp23 = cosf(pitch23), sp23 = sinf(pitch23);
    positions[3] = {
        positions[2].x + FOREARM * cp23 * c1,
        positions[2].y + FOREARM * cp23 * s1,
        positions[2].z + FOREARM * sp23
    };

    // J5 pivot point (end of wrist link)
    float pitch234 = pitch23 + j4;
    float cp234 = cosf(pitch234), sp234 = sinf(pitch234);
    positions[4] = {
        positions[3].x + WRIST_LINK * cp234 * c1,
        positions[3].y + WRIST_LINK * cp234 * s1,
        positions[3].z + WRIST_LINK * sp234
    };

    // Probe tip — J5 pitches perpendicular to the main arm plane
    // Forward direction (in main arm plane):
    float fwd_x = cp234 * c1;
    float fwd_y = cp234 * s1;
    float fwd_z = sp234;
    // Lateral direction (perpendicular to arm plane):
    float lat_x = -s1;
    float lat_y = c1;
    float lat_z = 0;
    // Probe direction = rotate fwd by j5 toward lateral
    float c5 = cosf(j5), s5 = sinf(j5);
    float pd_x = c5 * fwd_x + s5 * lat_x;
    float pd_y = c5 * fwd_y + s5 * lat_y;
    float pd_z = c5 * fwd_z + s5 * lat_z;

    positions[5] = {
        positions[4].x + PROBE_LEN * pd_x,
        positions[4].y + PROBE_LEN * pd_y,
        positions[4].z + PROBE_LEN * pd_z
    };
}

Vec3 forwardKinematics(const float angles[5]) {
    Vec3 positions[6];
    forwardKinematicsFull(angles, positions);
    return positions[5];  // Probe tip
}

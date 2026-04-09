#include "kinematics.h"
#include "config.h"
#include <math.h>

FKResult computeFK(const float angles[5]) {
    float j1 = angles[0];
    float j2 = angles[1];
    float j3 = angles[2];
    float j4 = angles[3];
    float j5 = angles[4];

    float c1 = cosf(j1), s1 = sinf(j1);

    FKResult fk;

    // Base: origin at desk surface
    fk.base = {0.0f, 0.0f, 0.0f};

    // Shoulder: top of base column
    fk.shoulder = {0.0f, 0.0f, BASE_HEIGHT};

    // Elbow: end of upper arm
    float c2 = cosf(j2), s2 = sinf(j2);
    fk.elbow = {
        fk.shoulder.x + UPPER_ARM * c2 * c1,
        fk.shoulder.y + UPPER_ARM * c2 * s1,
        fk.shoulder.z + UPPER_ARM * s2
    };

    // Wrist: end of forearm
    float pitch23 = j2 + j3;
    float cp23 = cosf(pitch23), sp23 = sinf(pitch23);
    fk.wrist = {
        fk.elbow.x + FOREARM * cp23 * c1,
        fk.elbow.y + FOREARM * cp23 * s1,
        fk.elbow.z + FOREARM * sp23
    };

    // J5 pivot: end of wrist link
    float pitch234 = pitch23 + j4;
    float cp234 = cosf(pitch234), sp234 = sinf(pitch234);
    fk.j5pos = {
        fk.wrist.x + WRIST_LINK * cp234 * c1,
        fk.wrist.y + WRIST_LINK * cp234 * s1,
        fk.wrist.z + WRIST_LINK * sp234
    };

    // Probe tip: J5 pitches perpendicular to the main arm plane
    // Forward direction (in main arm plane)
    float fwd_x = cp234 * c1;
    float fwd_y = cp234 * s1;
    float fwd_z = sp234;

    // Lateral direction (perpendicular to arm plane)
    float lat_x = -s1;
    float lat_y =  c1;
    float lat_z =  0.0f;

    // Probe direction: rotate forward by j5 toward lateral
    float c5 = cosf(j5), s5 = sinf(j5);
    float pd_x = c5 * fwd_x + s5 * lat_x;
    float pd_y = c5 * fwd_y + s5 * lat_y;
    float pd_z = c5 * fwd_z + s5 * lat_z;

    fk.tip = {
        fk.j5pos.x + PROBE_LEN * pd_x,
        fk.j5pos.y + PROBE_LEN * pd_y,
        fk.j5pos.z + PROBE_LEN * pd_z
    };

    return fk;
}

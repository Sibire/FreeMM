#ifndef KINEMATICS_H
#define KINEMATICS_H

#include <Arduino.h>

struct Vec3 {
    float x, y, z;
};

// Compute probe tip position from 5 joint angles (in degrees)
Vec3 forwardKinematics(const float angles[5]);

// Compute all intermediate joint positions (for diagnostics/display)
// positions[0]=base, [1]=shoulder, [2]=elbow, [3]=wrist, [4]=j5, [5]=tip
void forwardKinematicsFull(const float angles[5], Vec3 positions[6]);

#endif

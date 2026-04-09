#pragma once

#include <Arduino.h>

struct Vec3 {
    float x, y, z;
};

struct FKResult {
    Vec3 base;
    Vec3 shoulder;
    Vec3 elbow;
    Vec3 wrist;
    Vec3 j5pos;
    Vec3 tip;
};

// Compute full forward kinematics from 5 joint angles (in radians).
// Returns all intermediate joint positions and the probe tip.
FKResult computeFK(const float angles[5]);

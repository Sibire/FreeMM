#pragma once

#include <Arduino.h>
#include "kinematics.h"

// Send all 5 joint angles as degrees: ANGLES,j1,j2,j3,j4,j5\n
void sendAngles(const float angles[5]);

// Send a sampled point: POINT,idx,x,y,z\n
void sendPoint(int idx, const Vec3& tip);

// Send a trace point: TRACE,idx,a,b\n
void sendTrace(int idx, float a, float b);

// Send a status message: # msg\n
void sendStatus(const char* msg);

// Check Serial for incoming command char. Returns 0 if none.
// For 'd' command, also parses the float value (retrieve with getTraceMinDist).
char parseCommand();

// Return the last parsed trace min distance value
float getTraceMinDist();

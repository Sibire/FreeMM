"""5-DOF forward kinematics — Python mirror of firmware/src/kinematics.cpp"""

import math
import numpy as np

# Link lengths (mm) — PLACEHOLDER, measure from Fusion assembly
BASE_HEIGHT = 50.0
UPPER_ARM = 150.0
FOREARM = 130.0
WRIST_LINK = 30.0
PROBE_LEN = 20.0
BALL_RADIUS = 0.5

# Joint limits (degrees)
JOINT_LIMITS = [
    (-180, 180),   # J1: base yaw
    (-105, 105),   # J2: shoulder pitch
    (-145, 145),   # J3: elbow pitch
    (-180, 180),   # J4: wrist pitch
    (-145, 145),   # J5: wrist pitch 2 (perpendicular)
]


def forward_kinematics(angles_deg):
    """Compute probe tip XYZ from 5 joint angles in degrees.

    Returns dict with keys: base, shoulder, elbow, wrist, j5, tip
    Each value is a numpy array [x, y, z].
    """
    j1, j2, j3, j4, j5 = [math.radians(a) for a in angles_deg]

    c1, s1 = math.cos(j1), math.sin(j1)

    # Base
    base = np.array([0.0, 0.0, 0.0])

    # Shoulder
    shoulder = np.array([0.0, 0.0, BASE_HEIGHT])

    # Elbow
    c2, s2 = math.cos(j2), math.sin(j2)
    elbow = shoulder + UPPER_ARM * np.array([c2 * c1, c2 * s1, s2])

    # Wrist
    pitch23 = j2 + j3
    cp23, sp23 = math.cos(pitch23), math.sin(pitch23)
    wrist = elbow + FOREARM * np.array([cp23 * c1, cp23 * s1, sp23])

    # J5 pivot
    pitch234 = pitch23 + j4
    cp234, sp234 = math.cos(pitch234), math.sin(pitch234)
    j5pos = wrist + WRIST_LINK * np.array([cp234 * c1, cp234 * s1, sp234])

    # Probe tip — J5 pitches perpendicular to main arm plane
    fwd = np.array([cp234 * c1, cp234 * s1, sp234])
    lat = np.array([-s1, c1, 0.0])
    c5, s5 = math.cos(j5), math.sin(j5)
    probe_dir = c5 * fwd + s5 * lat
    tip = j5pos + PROBE_LEN * probe_dir

    return {
        'base': base,
        'shoulder': shoulder,
        'elbow': elbow,
        'wrist': wrist,
        'j5': j5pos,
        'tip': tip,
    }


def tip_position(angles_deg):
    """Convenience: just the tip XYZ as numpy array."""
    return forward_kinematics(angles_deg)['tip']

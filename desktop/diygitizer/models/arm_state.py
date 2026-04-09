"""Arm kinematic state — joint angles, FK computation, joint positions."""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from diygitizer.config import (
    BASE_HEIGHT,
    UPPER_ARM,
    FOREARM,
    WRIST_LINK,
    PROBE_LEN,
)


@dataclass
class ArmState:
    """Snapshot of the arm's joint angles and computed tip position.

    Joint angles are stored in **radians** internally.
    Call :meth:`compute_fk` after setting j1-j5 to recompute tip
    position and the full joint-position chain.
    """
    j1: float = 0.0
    j2: float = 0.0
    j3: float = 0.0
    j4: float = 0.0
    j5: float = 0.0

    # Computed by compute_fk()
    tip_x: float = 0.0
    tip_y: float = 0.0
    tip_z: float = 0.0

    # Full joint chain for arm visualisation:
    #   [base, shoulder, elbow, wrist, j5pos, tip]  each as (x, y, z)
    joint_positions: Optional[List[Tuple[float, float, float]]] = None

    def compute_fk(self):
        """Forward kinematics — mirrors the firmware exactly.

        Must be called after updating j1-j5 (in radians).
        Populates tip_x/y/z and joint_positions.
        """
        c1 = math.cos(self.j1)
        s1 = math.sin(self.j1)

        # Base / shoulder
        base = (0.0, 0.0, BASE_HEIGHT)
        shoulder = base  # shoulder is at base height

        # Elbow
        c2 = math.cos(self.j2)
        s2 = math.sin(self.j2)
        elbow_x = UPPER_ARM * c2 * c1
        elbow_y = UPPER_ARM * c2 * s1
        elbow_z = BASE_HEIGHT + UPPER_ARM * s2

        # Wrist
        pitch23 = self.j2 + self.j3
        cp23 = math.cos(pitch23)
        sp23 = math.sin(pitch23)
        wrist_x = elbow_x + FOREARM * cp23 * c1
        wrist_y = elbow_y + FOREARM * cp23 * s1
        wrist_z = elbow_z + FOREARM * sp23

        # J5 pivot
        pitch234 = pitch23 + self.j4
        cp234 = math.cos(pitch234)
        sp234 = math.sin(pitch234)
        j5x = wrist_x + WRIST_LINK * cp234 * c1
        j5y = wrist_y + WRIST_LINK * cp234 * s1
        j5z = wrist_z + WRIST_LINK * sp234

        # Probe tip — J5 rotates the probe perpendicular to the main arm plane
        fwd_x = cp234 * c1
        fwd_y = cp234 * s1
        fwd_z = sp234

        lat_x = -s1
        lat_y = c1
        lat_z = 0.0

        c5 = math.cos(self.j5)
        s5 = math.sin(self.j5)

        probe_dir_x = c5 * fwd_x + s5 * lat_x
        probe_dir_y = c5 * fwd_y + s5 * lat_y
        probe_dir_z = c5 * fwd_z + s5 * lat_z

        self.tip_x = j5x + PROBE_LEN * probe_dir_x
        self.tip_y = j5y + PROBE_LEN * probe_dir_y
        self.tip_z = j5z + PROBE_LEN * probe_dir_z

        self.joint_positions = [
            base,
            shoulder,
            (elbow_x, elbow_y, elbow_z),
            (wrist_x, wrist_y, wrist_z),
            (j5x, j5y, j5z),
            (self.tip_x, self.tip_y, self.tip_z),
        ]

    @classmethod
    def from_degrees(cls, j1_deg, j2_deg, j3_deg, j4_deg, j5_deg):
        """Create an ArmState from joint angles given in degrees and compute FK."""
        state = cls(
            j1=math.radians(j1_deg),
            j2=math.radians(j2_deg),
            j3=math.radians(j3_deg),
            j4=math.radians(j4_deg),
            j5=math.radians(j5_deg),
        )
        state.compute_fk()
        return state

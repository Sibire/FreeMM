"""Calibration solver for DIYgitizer arm.

Three calibration modes, all feeding the same FK-based optimizer:

1. Block calibration — touch faces of a 1-2-3 block from multiple poses.
   Known face distances constrain the solution.
2. Repeatability calibration — touch one sharp point from many different
   arm configurations.  All FK outputs should collapse to one point.
3. Surface calibration — touch a flat surface from many poses.  All FK
   outputs should be coplanar.

The optimizer adjusts 10 parameters:
  - 5 joint angle offsets (radians, added to raw encoder readings)
  - 5 link lengths (mm, replacing the config defaults)

to minimize the residual error across all captured data.
"""

import json
import math
from datetime import datetime
from dataclasses import dataclass, field, asdict

import numpy as np
from scipy.optimize import least_squares

from diygitizer.config import (
    BASE_HEIGHT, UPPER_ARM, FOREARM, WRIST_LINK, PROBE_LEN,
)


# ── Reference objects ─────────────────────────────────────────────────

BLOCK_123_MM = (25.4, 50.8, 76.2)  # 1", 2", 3"

FACE_PAIRS = [
    ('top', 'bottom', 25.4),   # Z thickness
    ('left', 'right', 50.8),   # X width
    ('front', 'back', 76.2),   # Y depth
]

FACE_ORDER = ['top', 'bottom', 'front', 'back', 'left', 'right']


# ── Parametric FK (pure numpy, no global state) ──────────────────────

def fk_numpy(angles_rad, link_lengths):
    """Compute tip position from raw angles + link lengths.

    Args:
        angles_rad: array of 5 joint angles in radians
        link_lengths: (base_height, upper_arm, forearm, wrist_link, probe_len)

    Returns:
        np.array([x, y, z])
    """
    j1, j2, j3, j4, j5 = angles_rad
    bh, ua, fa, wl, pl = link_lengths

    c1, s1 = math.cos(j1), math.sin(j1)
    c2, s2 = math.cos(j2), math.sin(j2)

    ex = ua * c2 * c1
    ey = ua * c2 * s1
    ez = bh + ua * s2

    p23 = j2 + j3
    cp23, sp23 = math.cos(p23), math.sin(p23)
    wx = ex + fa * cp23 * c1
    wy = ey + fa * cp23 * s1
    wz = ez + fa * sp23

    p234 = p23 + j4
    cp234, sp234 = math.cos(p234), math.sin(p234)
    jx = wx + wl * cp234 * c1
    jy = wy + wl * cp234 * s1
    jz = wz + wl * sp234

    c5, s5 = math.cos(j5), math.sin(j5)
    dx = c5 * cp234 * c1 + s5 * (-s1)
    dy = c5 * cp234 * s1 + s5 * c1
    dz = c5 * sp234

    return np.array([jx + pl * dx, jy + pl * dy, jz + pl * dz])


def fk_batch(all_angles_rad, offsets, link_lengths):
    """Compute FK for multiple angle sets with offsets applied.

    Args:
        all_angles_rad: Nx5 array of raw joint angles
        offsets: array of 5 joint offsets (added to raw angles)
        link_lengths: tuple of 5 link lengths

    Returns:
        Nx3 array of tip positions
    """
    n = len(all_angles_rad)
    result = np.empty((n, 3))
    for i in range(n):
        corrected = all_angles_rad[i] + offsets
        result[i] = fk_numpy(corrected, link_lengths)
    return result


# ── Plane fitting ─────────────────────────────────────────────────────

def fit_plane(points):
    """Fit plane to Nx3 points via SVD.  Returns (normal, d, centroid)."""
    centroid = np.mean(points, axis=0)
    _, _, Vt = np.linalg.svd(points - centroid, full_matrices=False)
    normal = Vt[2]
    d = np.dot(normal, centroid)
    return normal, d, centroid


def plane_distance(n1, d1, n2, d2):
    """Distance between two parallel planes."""
    if np.dot(n1, n2) < 0:
        d2 = -d2
    return abs(d1 - d2)


# ── Calibration data containers ──────────────────────────────────────

@dataclass
class CalibrationCapture:
    """One captured calibration point: raw angles + metadata."""
    angles_rad: np.ndarray     # shape (5,) — raw encoder angles
    label: str = ""            # e.g. 'top', 'point_1', 'surface'
    group: str = ""            # calibration mode: 'block', 'repeat', 'surface'


@dataclass
class CalibrationResult:
    timestamp: str = ""
    reference: str = ""
    link_lengths: dict = field(default_factory=dict)
    joint_offsets_deg: list = field(default_factory=lambda: [0.0] * 5)
    scale_factors: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    residual_error_mm: float = 0.0
    face_errors: dict = field(default_factory=dict)
    repeatability_mm: float = 0.0
    flatness_mm: float = 0.0
    iterations: int = 0


# ── Cost functions ────────────────────────────────────────────────────

def _block_residuals(params, captures, block_dims):
    """Residuals for block calibration.

    For each face pair, the distance between the fitted planes of the
    FK-computed points should match the known block dimension.
    Additionally, points on the same face should be coplanar (low scatter).
    """
    offsets = params[:5]
    lengths = params[5:]

    # Group captures by face label
    face_points = {}
    for cap in captures:
        corrected = cap.angles_rad + offsets
        pt = fk_numpy(corrected, lengths)
        face_points.setdefault(cap.label, []).append(pt)

    residuals = []

    # Face-to-face distance errors
    for face_a, face_b, expected in FACE_PAIRS:
        if face_a not in face_points or face_b not in face_points:
            continue
        pts_a = np.array(face_points[face_a])
        pts_b = np.array(face_points[face_b])
        if len(pts_a) < 3 or len(pts_b) < 3:
            continue

        na, da, _ = fit_plane(pts_a)
        nb, db, _ = fit_plane(pts_b)
        measured = plane_distance(na, da, nb, db)
        # Weight distance error heavily (in mm)
        residuals.append((measured - expected) * 5.0)

    # Per-face flatness: each point's distance to fitted plane
    for face, pts_list in face_points.items():
        pts = np.array(pts_list)
        if len(pts) < 3:
            continue
        normal, d, _ = fit_plane(pts)
        distances = np.abs(pts @ normal - d)
        residuals.extend(distances.tolist())

    # Perpendicularity: adjacent faces should be 90 degrees
    adjacent = [
        ('top', 'front'), ('top', 'left'), ('top', 'right'), ('top', 'back'),
        ('front', 'left'), ('front', 'right'),
    ]
    for a, b in adjacent:
        if a in face_points and b in face_points:
            pts_a = np.array(face_points[a])
            pts_b = np.array(face_points[b])
            if len(pts_a) >= 3 and len(pts_b) >= 3:
                na, _, _ = fit_plane(pts_a)
                nb, _, _ = fit_plane(pts_b)
                dot = abs(np.dot(na, nb))
                # dot should be 0 for perpendicular; penalize deviation
                residuals.append(dot * 10.0)

    return np.array(residuals) if residuals else np.array([0.0])


def _repeat_residuals(params, captures):
    """Residuals for repeatability calibration.

    All captures should FK to the same point.  Residuals are the
    distance from each point to the centroid.
    """
    offsets = params[:5]
    lengths = params[5:]

    points = []
    for cap in captures:
        corrected = cap.angles_rad + offsets
        points.append(fk_numpy(corrected, lengths))

    points = np.array(points)
    centroid = np.mean(points, axis=0)
    diffs = points - centroid
    # Each component (x, y, z) of each point's deviation is a residual
    return diffs.ravel()


def _surface_residuals(params, captures):
    """Residuals for surface calibration.

    All captures should be coplanar.  Residuals are distances to the
    best-fit plane.
    """
    offsets = params[:5]
    lengths = params[5:]

    points = []
    for cap in captures:
        corrected = cap.angles_rad + offsets
        points.append(fk_numpy(corrected, lengths))

    points = np.array(points)
    if len(points) < 3:
        return np.array([0.0])

    normal, d, _ = fit_plane(points)
    distances = points @ normal - d
    return distances


# ── Combined optimizer ────────────────────────────────────────────────

def optimize(captures, block_dims=BLOCK_123_MM):
    """Run the combined calibration optimizer.

    Accepts captures from any combination of the three modes.
    Returns a CalibrationResult with optimized link lengths and
    joint offsets.

    Args:
        captures: list of CalibrationCapture
        block_dims: (thickness, width, depth) for block mode

    Returns:
        CalibrationResult
    """
    # Split captures by group
    block_caps = [c for c in captures if c.group == 'block']
    repeat_caps = [c for c in captures if c.group == 'repeat']
    surface_caps = [c for c in captures if c.group == 'surface']

    # Initial parameter vector: [5 offsets (rad), 5 link lengths (mm)]
    x0 = np.array([
        0.0, 0.0, 0.0, 0.0, 0.0,          # joint offsets
        BASE_HEIGHT, UPPER_ARM, FOREARM, WRIST_LINK, PROBE_LEN,
    ])

    # Bounds: offsets within ±5 degrees, link lengths within ±5% of nominal.
    # Nominal lengths are from Fusion CAD — they're already close.  The
    # offsets and small length tweaks handle print tolerances and slop.
    offset_bound = math.radians(5.0)
    length_margin = 0.05  # 5%
    lb = np.array([
        -offset_bound, -offset_bound, -offset_bound,
        -offset_bound, -offset_bound,
        BASE_HEIGHT * (1 - length_margin),
        UPPER_ARM * (1 - length_margin),
        FOREARM * (1 - length_margin),
        WRIST_LINK * (1 - length_margin),
        PROBE_LEN * (1 - length_margin),
    ])
    ub = np.array([
        offset_bound, offset_bound, offset_bound,
        offset_bound, offset_bound,
        BASE_HEIGHT * (1 + length_margin),
        UPPER_ARM * (1 + length_margin),
        FOREARM * (1 + length_margin),
        WRIST_LINK * (1 + length_margin),
        PROBE_LEN * (1 + length_margin),
    ])

    def combined_residuals(params):
        all_res = []
        if block_caps:
            all_res.append(_block_residuals(params, block_caps, block_dims))
        if repeat_caps:
            all_res.append(_repeat_residuals(params, repeat_caps))
        if surface_caps:
            all_res.append(_surface_residuals(params, surface_caps))

        # Regularization: soft penalty for deviating from nominal.
        # Prevents degenerate solutions where large offset changes
        # mask large length changes.  Scaled so that a 1-degree offset
        # or 1mm length change each contribute ~0.5 to the residual.
        reg = np.zeros(10)
        reg[:5] = (params[:5] - x0[:5]) * (0.5 / math.radians(1.0))  # per degree
        reg[5:] = (params[5:] - x0[5:]) * 0.5                        # per mm
        all_res.append(reg)

        if len(all_res) <= 1:
            return np.array([0.0])
        return np.concatenate(all_res)

    result_opt = least_squares(
        combined_residuals, x0,
        bounds=(lb, ub),
        method='trf',
        max_nfev=5000,
        ftol=1e-10,
        xtol=1e-10,
    )

    # Extract results
    offsets = result_opt.x[:5]
    lengths = result_opt.x[5:]

    cal = CalibrationResult()
    cal.timestamp = datetime.now().isoformat()
    cal.joint_offsets_deg = [round(float(math.degrees(o)), 4) for o in offsets]
    cal.link_lengths = {
        'base_height': round(float(lengths[0]), 2),
        'upper_arm':   round(float(lengths[1]), 2),
        'forearm':     round(float(lengths[2]), 2),
        'wrist_link':  round(float(lengths[3]), 2),
        'probe_len':   round(float(lengths[4]), 2),
    }
    cal.iterations = result_opt.nfev

    # Compute per-mode metrics
    if block_caps:
        cal.reference = f"1-2-3 block ({block_dims[0]} x {block_dims[1]} x {block_dims[2]}mm)"
        cal.face_errors = _compute_block_errors(offsets, lengths, block_caps, block_dims)
        dist_errors = [abs(v['error']) for v in cal.face_errors.values()]
        if dist_errors:
            cal.residual_error_mm = round(
                math.sqrt(sum(e**2 for e in dist_errors) / len(dist_errors)), 3
            )

    if repeat_caps:
        points = fk_batch(
            np.array([c.angles_rad for c in repeat_caps]), offsets, lengths
        )
        centroid = np.mean(points, axis=0)
        dists = np.linalg.norm(points - centroid, axis=1)
        cal.repeatability_mm = round(float(dists.max()), 3)

    if surface_caps:
        points = fk_batch(
            np.array([c.angles_rad for c in surface_caps]), offsets, lengths
        )
        if len(points) >= 3:
            normal, d, _ = fit_plane(points)
            distances = np.abs(points @ normal - d)
            cal.flatness_mm = round(float(distances.max()), 3)

    # Scale factors (legacy compat — derived from link length changes)
    cal.scale_factors = [
        round(lengths[1] / UPPER_ARM, 6),
        round(lengths[2] / FOREARM, 6),
        round(lengths[0] / BASE_HEIGHT, 6),
    ]

    return cal


def _compute_block_errors(offsets, lengths, captures, block_dims):
    """Compute face-pair distance errors after calibration."""
    face_points = {}
    for cap in captures:
        corrected = cap.angles_rad + offsets
        pt = fk_numpy(corrected, lengths)
        face_points.setdefault(cap.label, []).append(pt)

    errors = {}
    for face_a, face_b, expected in FACE_PAIRS:
        if face_a not in face_points or face_b not in face_points:
            continue
        pts_a = np.array(face_points[face_a])
        pts_b = np.array(face_points[face_b])
        if len(pts_a) < 3 or len(pts_b) < 3:
            continue
        na, da, _ = fit_plane(pts_a)
        nb, db, _ = fit_plane(pts_b)
        measured = plane_distance(na, da, nb, db)
        errors[f"{face_a}-{face_b}"] = {
            'expected': expected,
            'measured': round(measured, 3),
            'error': round(measured - expected, 3),
        }
    return errors


# ── Apply calibration to live data ────────────────────────────────────

def apply_calibration_angles(angles_rad, calibration):
    """Apply joint offsets to raw encoder angles.

    Args:
        angles_rad: array of 5 raw joint angles
        calibration: CalibrationResult

    Returns:
        corrected angles (radians)
    """
    offsets = np.array([math.radians(o) for o in calibration.joint_offsets_deg])
    return np.array(angles_rad) + offsets


def get_calibrated_lengths(calibration):
    """Get link lengths from calibration result.

    Returns:
        (base_height, upper_arm, forearm, wrist_link, probe_len)
    """
    ll = calibration.link_lengths
    if not ll:
        return (BASE_HEIGHT, UPPER_ARM, FOREARM, WRIST_LINK, PROBE_LEN)
    return (
        ll.get('base_height', BASE_HEIGHT),
        ll.get('upper_arm', UPPER_ARM),
        ll.get('forearm', FOREARM),
        ll.get('wrist_link', WRIST_LINK),
        ll.get('probe_len', PROBE_LEN),
    )


def apply_calibration(point, calibration):
    """Legacy: apply scale factors to a point. Prefer angle-level correction."""
    x, y, z = point
    sx, sy, sz = calibration.scale_factors
    return (x * sx, y * sy, z * sz)


# ── Save / Load ───────────────────────────────────────────────────────

def save_calibration(result, filepath):
    """Save calibration to JSON."""
    data = asdict(result)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_calibration(filepath):
    """Load calibration from JSON."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return CalibrationResult(**data)

"""3D scan session data model."""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class ScanSession:
    """A 3D digitiser scan session.

    *points* is an Nx3 numpy array of XYZ coordinates.
    *mesh_vertices* / *mesh_faces* are populated after surface reconstruction.
    *features* holds detected 3D geometric features.
    """
    points: np.ndarray = field(default_factory=lambda: np.empty((0, 3)))
    mesh_vertices: Optional[np.ndarray] = None
    mesh_faces: Optional[np.ndarray] = None
    features: Optional[List] = None

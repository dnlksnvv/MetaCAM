from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Aperture:
    type: str
    size: float = 0.0
    w: float = 0.0
    h: float = 0.0
    n: int = 0
    rot: float = 0.0


def parse_aperture_def(ap_type: str, params: str) -> Aperture:
    ap_type = ap_type.strip()
    params = params.strip()
    if ap_type.startswith("C"):
        parts = params.split("X")
        d = float(parts[0].strip())
        return Aperture("C", size=d)
    if ap_type.startswith("R"):
        parts = params.split("X")
        if len(parts) < 2:
            raise ValueError("R aperture needs wXh")
        w = float(parts[0].strip())
        h = float(parts[1].strip())
        return Aperture("R", w=w, h=h, size=math.hypot(w, h))
    if ap_type.startswith("O"):
        parts = params.split("X")
        if len(parts) < 2:
            raise ValueError("O aperture needs wXh")
        w = float(parts[0].strip())
        h = float(parts[1].strip())
        return Aperture("O", w=w, h=h, size=math.hypot(w, h))
    if ap_type.startswith("P"):
        parts = params.split("X")
        if len(parts) < 2:
            raise ValueError("P aperture needs diamXn")
        d = float(parts[0].strip())
        n = int(parts[1].strip())
        rot = float(parts[2].strip()) if len(parts) >= 3 else 0.0
        return Aperture("P", size=d, w=d, n=n, rot=rot)
    raise ValueError(f"unsupported aperture type {ap_type!r}")

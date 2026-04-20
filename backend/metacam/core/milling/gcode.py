from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from metacam.core.domain.models import Bounds, Point, Stroke


@dataclass
class MillingParams:
    """
    Simplified Milling/CNCJob parameters (FlatCAM-like).

    Units: mm, absolute coordinates, XY plane.
    """

    tool_diameter: float = 0.5
    cut_z: float = -0.05
    travel_z: float = 2.0
    feedrate_xy: float = 120.0
    feedrate_z: float = 60.0
    spindle_speed: float = 0.0
    dwell: bool = False
    dwell_time: float = 1.0
    toolchange_z: float = 15.0
    end_move_z: float = 15.0
    preprocessor: str = "default"


def _fmt(x: float) -> str:
    # Candle/GRBL typically likes dot decimals.
    return f"{x:.4f}".rstrip("0").rstrip(".") if abs(x) < 1e6 else f"{x:.4f}"


def _bounds_from_strokes(strokes: Iterable[Stroke], pad: float = 0.0) -> Bounds:
    inf = float("inf")
    b = Bounds(inf, inf, -inf, -inf)
    n = 0
    for s in strokes:
        for p in s.points:
            n += 1
            b.min_x = min(b.min_x, p.x)
            b.min_y = min(b.min_y, p.y)
            b.max_x = max(b.max_x, p.x)
            b.max_y = max(b.max_y, p.y)
    if n == 0:
        return Bounds(0, 0, 0, 0)
    return Bounds(b.min_x - pad, b.min_y - pad, b.max_x + pad, b.max_y + pad)


def generate_cncjob_gcode(lines: list[Stroke], params: MillingParams) -> tuple[str, Bounds, list[Stroke]]:
    """
    Convert polylines to a basic GRBL-friendly G-code program.

    Strategy:
    - G21/G90/G17, raise to travel_z
    - For each polyline: rapid XY at travel_z, plunge to cut_z (Fz), feed along points (Fxy), retract to travel_z
    - Optional spindle M3 S..., optional dwell at start of program
    - End: retract to end_move_z, M5, M2
    """
    if params.tool_diameter <= 0:
        raise ValueError("milling: tool_diameter must be > 0")

    out: list[str] = []
    out.append("(metacam_py CNCJob)")
    out.append("(units: mm, abs)")
    out.append("G21")
    out.append("G90")
    out.append("G17")
    out.append(f"G0 Z{_fmt(params.travel_z)}")

    if params.spindle_speed and params.spindle_speed > 0:
        out.append(f"M3 S{_fmt(params.spindle_speed)}")
        if params.dwell:
            out.append(f"G4 P{_fmt(params.dwell_time)}")

    # Preview strokes for rendering (same geometry as input toolpath)
    preview_lines = [Stroke(width=max(params.tool_diameter * 0.12, 0.02), points=s.points, clear=False) for s in lines]
    bounds = _bounds_from_strokes(preview_lines, pad=params.tool_diameter / 2)

    for ln in lines:
        pts = ln.points
        if not pts or len(pts) < 2:
            continue
        p0: Point = pts[0]
        out.append(f"G0 X{_fmt(p0.x)} Y{_fmt(p0.y)}")
        out.append(f"G1 Z{_fmt(params.cut_z)} F{_fmt(params.feedrate_z)}")
        out.append(f"F{_fmt(params.feedrate_xy)}")
        for p in pts[1:]:
            out.append(f"G1 X{_fmt(p.x)} Y{_fmt(p.y)}")
        out.append(f"G0 Z{_fmt(params.travel_z)}")

    out.append(f"G0 Z{_fmt(params.end_move_z)}")
    out.append("M5")
    out.append("M2")
    return "\n".join(out) + "\n", bounds, preview_lines


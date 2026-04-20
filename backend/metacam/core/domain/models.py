from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _parse_float(v: Any, default: float) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).lower().strip()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    return default


def _normalize_ncc_overlap(raw: float) -> float:
    """
    FlatCAM stores ``tools_ncc_overlap`` as percent (e.g. 40) and divides by 100
    before ``clear_polygon2``. Values in (0, 1] are treated as fraction already.
    """
    if raw > 1.0 + 1e-9:
        return raw / 100.0
    return raw


def _parse_method(v: Any) -> str:
    """FlatCAM ``tools_ncc_method``: 0 standard, 1 seed, 2 lines, 3 combo."""
    if v is None:
        return "seed"
    if isinstance(v, int):
        return {0: "standard", 1: "seed", 2: "lines", 3: "combo"}.get(v, "seed")
    s = str(v).strip().lower()
    if s in ("0", "1", "2", "3"):
        return {0: "standard", 1: "seed", 2: "lines", 3: "combo"}[int(s)]
    if s in ("standard", "seed", "lines", "combo"):
        return s
    return "seed"


def _parse_selection(v: Any) -> str:
    """FlatCAM ``tools_ncc_ref``: 0 itself, 1 area, 2 reference."""
    if v is None:
        return "itself"
    if isinstance(v, int):
        return {0: "itself", 1: "area", 2: "reference"}.get(v, "itself")
    s = str(v).strip().lower()
    if s in ("0", "1", "2"):
        return {0: "itself", 1: "area", 2: "reference"}[int(s)]
    if s in ("itself", "area", "reference"):
        return s
    return "itself"


@dataclass
class Point:
    x: float
    y: float

    def as_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def as_dict(self) -> dict[str, float]:
        return {"minX": self.min_x, "minY": self.min_y, "maxX": self.max_x, "maxY": self.max_y}


@dataclass
class Stroke:
    width: float
    points: list[Point]
    clear: bool = False

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "width": self.width,
            "points": [p.as_dict() for p in self.points],
        }
        if self.clear:
            d["clear"] = True
        return d


@dataclass
class RectFlash:
    cx: float
    cy: float
    w: float
    h: float
    clear: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = {"cx": self.cx, "cy": self.cy, "w": self.w, "h": self.h}
        if self.clear:
            d["clear"] = True
        return d


@dataclass
class CircleFlash:
    cx: float
    cy: float
    r: float
    clear: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = {"cx": self.cx, "cy": self.cy, "r": self.r}
        if self.clear:
            d["clear"] = True
        return d


@dataclass
class Fill:
    rings: list[list[Point]]
    clear: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = {"rings": [[p.as_dict() for p in ring] for ring in self.rings]}
        if self.clear:
            d["clear"] = True
        return d


@dataclass
class LayerPreview:
    units: str = "MM"
    bounds: Bounds | None = None
    strokes: list[Stroke] = field(default_factory=list)
    circles: list[CircleFlash] = field(default_factory=list)
    rects: list[RectFlash] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        b = self.bounds
        if b is None:
            b = Bounds(0, 0, 0, 0)
        out: dict[str, Any] = {
            "units": self.units,
            "bounds": b.as_dict(),
            "strokes": [s.as_dict() for s in self.strokes],
            "circles": [c.as_dict() for c in self.circles],
            "rects": [r.as_dict() for r in self.rects],
            "fills": [f.as_dict() for f in self.fills],
        }
        if self.warnings:
            out["warnings"] = list(self.warnings)
        return out


@dataclass
class NCCParams:
    """
    Parameters aligned with FlatCAM ``defaults.py`` / ToolNCC (where applicable).

    - ``overlap`` is always stored as **fraction** in [0, 1) (FlatCAM UI percent / 100).
    - ``check_validity``: same role as ``tools_ncc_check_valid`` (safe tool vs feature gap).
    - ``check_inset``: optional extra check (not in FlatCAM UI); default ``False``.
    """

    tool_diameter: float = 0.136
    tool_shape: str = "V"
    overlap: float = 0.4
    margin: float = 1.0
    method: str = "seed"
    connect: bool = True
    contour: bool = True
    selection: str = "itself"
    check_validity: bool = True
    check_inset: bool = False
    steps_per_circle: int = 64
    decimals: int = 4

    @staticmethod
    def from_json(d: dict[str, Any]) -> NCCParams:
        # FlatCAM-style keys (see defaults.py / ToolNCC storage)
        td = _parse_float(
            d.get("toolDiameter", d.get("toolsNccNewdia", d.get("tools_ncc_newdia"))),
            0.136,
        )
        overlap_raw = _parse_float(
            d.get("overlap", d.get("toolsNccOverlap", d.get("tools_ncc_overlap"))),
            40.0,
        )
        overlap = _normalize_ncc_overlap(overlap_raw)
        margin = _parse_float(
            d.get("margin", d.get("toolsNccMargin", d.get("tools_ncc_margin"))),
            1.0,
        )
        raw_shape = str(
            d.get("toolShape", d.get("toolsNccToolType", d.get("tools_ncc_tool_type", "V")))
        ).strip().upper()
        shape = raw_shape[0] if raw_shape else "V"

        method = _parse_method(d.get("method", d.get("toolsNccMethod", d.get("tools_ncc_method"))))
        selection = _parse_selection(
            d.get("selection", d.get("toolsNccRef", d.get("tools_ncc_ref")))
        )
        connect = _parse_bool(
            d.get("connect", d.get("toolsNccConnect", d.get("tools_ncc_connect"))),
            True,
        )
        contour = _parse_bool(
            d.get("contour", d.get("toolsNccContour", d.get("tools_ncc_contour"))),
            True,
        )
        check_validity = _parse_bool(
            d.get("checkValidity", d.get("toolsNccCheckValid", d.get("tools_ncc_check_valid"))),
            True,
        )
        check_inset = _parse_bool(
            d.get("checkInset", d.get("check_inset")),
            False,
        )
        steps = d.get("stepsPerCircle", d.get("gerberCircleSteps", d.get("gerber_circle_steps")))
        if steps is None:
            steps = d.get("geometryCircleSteps", d.get("geometry_circle_steps"))
        steps_per_circle = int(steps) if steps is not None else 64
        dec = d.get("decimals", d.get("geometryDecimals"))
        decimals = int(dec) if dec is not None else 4

        return NCCParams(
            tool_diameter=td,
            tool_shape=shape,
            overlap=overlap,
            margin=margin,
            method=method,
            connect=connect,
            contour=contour,
            selection=selection,
            check_validity=check_validity,
            check_inset=check_inset,
            steps_per_circle=steps_per_circle,
            decimals=decimals,
        )


@dataclass
class NCCToolpathPreview:
    tool_diameter: float
    overlap: float
    margin: float
    bounds: Bounds
    lines: list[Stroke]
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "toolDiameter": self.tool_diameter,
            "overlap": self.overlap,
            "margin": self.margin,
            "bounds": self.bounds.as_dict(),
            "lines": [ln.as_dict() for ln in self.lines],
        }
        if self.warnings:
            d["warnings"] = list(self.warnings)
        return d


@dataclass
class MillingParams:
    """
    Simplified Milling/CNCJob params (FlatCAM Milling-like).
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

    @staticmethod
    def from_json(d: dict[str, Any]) -> "MillingParams":
        return MillingParams(
            tool_diameter=_parse_float(d.get("toolDiameter"), 0.5),
            cut_z=_parse_float(d.get("cutZ"), -0.05),
            travel_z=_parse_float(d.get("travelZ"), 2.0),
            feedrate_xy=_parse_float(d.get("feedrateXY"), 120.0),
            feedrate_z=_parse_float(d.get("feedrateZ"), 60.0),
            spindle_speed=_parse_float(d.get("spindleSpeed"), 0.0),
            dwell=_parse_bool(d.get("dwell"), False),
            dwell_time=_parse_float(d.get("dwellTime"), 1.0),
            toolchange_z=_parse_float(d.get("toolchangeZ"), 15.0),
            end_move_z=_parse_float(d.get("endMoveZ"), 15.0),
            preprocessor=str(d.get("preprocessor") or "default"),
        )


@dataclass
class CNCJobPreview:
    tool_diameter: float
    bounds: Bounds
    lines: list[Stroke]
    gcode: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "toolDiameter": self.tool_diameter,
            "bounds": self.bounds.as_dict(),
            "lines": [ln.as_dict() for ln in self.lines],
            "gcode": self.gcode,
        }
        if self.warnings:
            d["warnings"] = list(self.warnings)
        return d

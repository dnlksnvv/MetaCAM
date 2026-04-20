"""
Gerber → LayerPreview (port of metacam Go core/gerber/parser.go).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from metacam.core.domain.models import (
    Bounds,
    CircleFlash,
    Fill,
    LayerPreview,
    Point,
    RectFlash,
    Stroke,
)
from metacam.core.gerber.aperture import Aperture, parse_aperture_def
from metacam.core.gerber.arc_def import arc_points
from metacam.core.gerber.number import parse_gerber_number
from metacam.core.gerber.tokenize import statements_from_bytes

_DEFAULT_STEPS = 64

_re_comment = re.compile(r"^G0?4")
# FS: format specification (X and Y integer+decimal digits).
# Example: %FSLAX36Y36*%
_re_fs = re.compile(r"^%?FS([LTD])?([AI])X(\d)(\d)Y(\d)(\d)\*%?$")
_re_fs_alt = re.compile(r"^%FS([LTD])?([AI])X(\d)(\d)Y(\d)(\d)\*MO(IN|MM)\*%$")
_re_mo = re.compile(r"^%?MO(IN|MM)\*%?$")
_re_add = re.compile(r"^%ADD(\d+)([A-Za-z_$\.][A-Za-z0-9_$\.\-]*)(?:,(.*))?\*%$")
_re_tool = re.compile(r"^(?:G54)?D(\d+)\*$")
_re_op_alone = re.compile(r"^D0?([123])\*$")
_re_g36 = re.compile(r"^G36\*$")
_re_g37 = re.compile(r"^G37\*$")
_re_interp = re.compile(r"^G0?([123])\*$")
_re_quad = re.compile(r"^G7([45])")
_re_lp = re.compile(r"^%LP([DC])\*%$")
_re_eof = re.compile(r"^M02\*")
_re_x = re.compile(r"X([+-]?\d+)")
_re_y = re.compile(r"Y([+-]?\d+)")
_re_i = re.compile(r"I([+-]?\d+)")
_re_j = re.compile(r"J([+-]?\d+)")
_re_d_op = re.compile(r"D0?([123])")
_re_g_interp = re.compile(r"G0([123])")


def norm_ap_id(s: str) -> str:
    s = s.lstrip("0")
    return s if s else "0"


def first_match(rx: re.Pattern[str], gline: str) -> tuple[str, bool]:
    m = rx.search(gline)
    if not m:
        return "", False
    return m.group(1), True


@dataclass
class _Parser:
    int_digits: int = 4
    frac_digits: int = 4
    zeros: str = "L"
    units: str = ""
    apertures: dict[str, Aperture] = field(default_factory=dict)
    cx: float = 0.0
    cy: float = 0.0
    prev_x: float = 0.0
    prev_y: float = 0.0
    current_ap: str = ""
    last_path_ap: str = ""
    interp_mode: int = 1
    op_code: int = 1
    quad_mode: str = ""
    path: list[tuple[float, float]] = field(default_factory=list)
    making_region: bool = False
    lpc: bool = False
    steps_per_circle: int = _DEFAULT_STEPS
    out: LayerPreview = field(default_factory=LayerPreview)

    def __post_init__(self) -> None:
        self.out.bounds = Bounds(
            float("inf"), float("inf"), float("-inf"), float("-inf")
        )

    def parse_coord_num(self, s: str) -> float:
        z = self.zeros[0] if self.zeros else "L"
        return parse_gerber_number(s, self.int_digits, self.frac_digits, z)

    def expand_bounds(self, x: float, y: float) -> None:
        b = self.out.bounds
        assert b is not None
        b.min_x = min(b.min_x, x)
        b.min_y = min(b.min_y, y)
        b.max_x = max(b.max_x, x)
        b.max_y = max(b.max_y, y)

    def expand_bounds_width(self, x: float, y: float, w: float) -> None:
        h = w / 2
        self.expand_bounds(x - h, y - h)
        self.expand_bounds(x + h, y + h)

    def flash_at(self, x: float, y: float) -> None:
        ap = self.apertures.get(self.current_ap)
        if ap is None:
            return
        if ap.type == "C":
            r = ap.size / 2
            self.out.circles.append(CircleFlash(x, y, r, self.lpc))
            self.expand_bounds_width(x, y, ap.size)
        elif ap.type == "R":
            self.out.rects.append(RectFlash(x, y, ap.w, ap.h, self.lpc))
            self.expand_bounds(x - ap.w / 2, y - ap.h / 2)
            self.expand_bounds(x + ap.w / 2, y + ap.h / 2)
        elif ap.type == "O":
            self.out.rects.append(RectFlash(x, y, ap.w, ap.h, self.lpc))
            self.expand_bounds(x - ap.w / 2, y - ap.h / 2)
            self.expand_bounds(x + ap.w / 2, y + ap.h / 2)
        elif ap.type == "P":
            n = ap.n if ap.n >= 3 else 6
            r = ap.size / 2
            ring: list[Point] = []
            for i in range(n):
                th = 2 * math.pi * i / n
                px = x + r * math.cos(th)
                py = y + r * math.sin(th)
                ring.append(Point(px, py))
                self.expand_bounds(px, py)
            self.out.fills.append(Fill([ring], self.lpc))

    def add_fill_ring(self, pts: list[tuple[float, float]]) -> None:
        ring = [Point(x, y) for x, y in pts]
        for p in ring:
            self.expand_bounds(p.x, p.y)
        self.out.fills.append(Fill([ring], self.lpc))

    def flush_stroke_path(self) -> None:
        if self.making_region or len(self.path) < 2:
            return
        lap = self.last_path_ap or self.current_ap
        ap = self.apertures.get(lap)
        if ap is None:
            self.out.warnings.append(f"no aperture for path (D{lap})")
            self.path = []
            return
        if ap.type == "C":
            pts = [Point(x, y) for x, y in self.path]
            for q in pts:
                self.expand_bounds_width(q.x, q.y, ap.size)
            self.out.strokes.append(Stroke(ap.size, pts, self.lpc))
        elif ap.type == "R":
            if len(self.path) == 2:
                x0, y0 = self.path[0]
                x1, y1 = self.path[1]
                minx = min(x0, x1) - ap.w / 2
                maxx = max(x0, x1) + ap.w / 2
                miny = min(y0, y1) - ap.h / 2
                maxy = max(y0, y1) + ap.h / 2
                ring = [
                    Point(minx, miny),
                    Point(maxx, miny),
                    Point(maxx, maxy),
                    Point(minx, maxy),
                ]
                for q in ring:
                    self.expand_bounds(q.x, q.y)
                self.out.fills.append(Fill([[p for p in ring]], self.lpc))
            else:
                pts = [Point(x, y) for x, y in self.path]
                w = max(ap.w, ap.h)
                for q in pts:
                    self.expand_bounds_width(q.x, q.y, w)
                self.out.strokes.append(Stroke(w, pts, self.lpc))
        else:
            w = ap.size if ap.size > 0 else 0.01
            pts = [Point(x, y) for x, y in self.path]
            for q in pts:
                self.expand_bounds_width(q.x, q.y, w)
            self.out.strokes.append(Stroke(w, pts, self.lpc))
        self.path = []

    def linear_pen_down(self, lx: float, ly: float) -> None:
        if self.making_region:
            if not self.path:
                self.path.append((lx, ly))
            else:
                last = self.path[-1]
                if last[0] != lx or last[1] != ly:
                    self.path.append((lx, ly))
            self.last_path_ap = self.current_ap
            return
        if not self.path:
            self.path = [(lx, ly)]
            self.last_path_ap = self.current_ap
            return
        last = self.path[-1]
        if last[0] == lx and last[1] == ly:
            if len(self.path) == 1:
                self.flash_at(lx, ly)
            return
        self.path.append((lx, ly))
        self.last_path_ap = self.current_ap

    def linear_pen_up(self, lx: float, ly: float) -> None:
        if self.making_region:
            if len(self.path) >= 3:
                self.add_fill_ring(self.path)
            self.path = [(lx, ly)]
            self.cx, self.cy = lx, ly
            return
        self.flush_stroke_path()
        self.path = [(lx, ly)]
        self.cx, self.cy = lx, ly

    def handle_linear_line(self, gline: str) -> None:
        xs, has_x = first_match(_re_x, gline)
        ys, has_y = first_match(_re_y, gline)
        lx, ly = self.cx, self.cy
        if has_x:
            lx = self.parse_coord_num(xs)
            self.cx = lx
        if has_y:
            ly = self.parse_coord_num(ys)
            self.cy = ly
        m = _re_d_op.search(gline)
        if m:
            self.op_code = int(m.group(1))
        m2 = _re_g_interp.search(gline)
        if m2:
            self.interp_mode = int(m2.group(1))
        if self.op_code == 1:
            self.linear_pen_down(lx, ly)
        elif self.op_code == 2:
            self.linear_pen_up(lx, ly)
        elif self.op_code == 3:
            self.flash_at(lx, ly)
            self.cx, self.cy = lx, ly

    def is_arc_line(self, gline: str) -> bool:
        if _re_i.search(gline) or _re_j.search(gline):
            return True
        if "G02" in gline or "G2" in gline or "G03" in gline or "G3" in gline:
            return True
        return self.interp_mode in (2, 3)

    def handle_arc_line(self, gline: str) -> None:
        if not self.quad_mode:
            self.out.warnings.append(f"arc without G74/G75 (ignored): {gline}")
            return
        xs, has_x = first_match(_re_x, gline)
        ys, has_y = first_match(_re_y, gline)
        is_, has_i = first_match(_re_i, gline)
        js, has_j = first_match(_re_j, gline)
        circular_x, circular_y = self.cx, self.cy
        if has_x:
            circular_x = self.parse_coord_num(xs)
        if has_y:
            circular_y = self.parse_coord_num(ys)
        i_val = j_val = 0.0
        if has_i:
            i_val = self.parse_coord_num(is_)
        if has_j:
            j_val = self.parse_coord_num(js)
        m = re.search(r"G0?([23])", gline)
        if m:
            self.interp_mode = int(m.group(1))
        m = _re_d_op.search(gline)
        if m:
            self.op_code = int(m.group(1))
        if self.op_code != 1:
            if self.op_code == 2:
                self.flush_stroke_path()
                self.cx, self.cy = circular_x, circular_y
                self.path = [(self.cx, self.cy)]
            return
        if self.quad_mode == "MULTI":
            center = (self.cx + i_val, self.cy + j_val)
            radius = math.hypot(i_val, j_val)
            start = math.atan2(-j_val, -i_val)
            stop = math.atan2(circular_y - center[1], circular_x - center[0])
            cw = self.interp_mode == 2
            pts = arc_points(center, radius, start, stop, cw, self.steps_per_circle)
            if pts:
                pts[-1] = (circular_x, circular_y)
            if not self.path:
                self.path.extend(pts)
            else:
                self.path.extend(pts[1:])
            self.cx, self.cy = circular_x, circular_y
            self.last_path_ap = self.current_ap
            return
        self.out.warnings.append(
            "G74 single-quadrant arc not implemented; segment skipped"
        )
        self.cx, self.cy = circular_x, circular_y

    def close_region_polygon(self) -> None:
        if len(self.path) >= 3:
            self.add_fill_ring(self.path)

    def handle_line(self, gline: str) -> None:
        if _re_comment.match(gline):
            return
        m = _re_lp.match(gline)
        if m:
            self.lpc = m.group(1) == "C"
            return
        m = _re_fs.match(gline)
        if m:
            if m.group(1):
                self.zeros = m.group(1)
            ix, fx = int(m.group(3)), int(m.group(4))
            iy, fy = int(m.group(5)), int(m.group(6))
            # Most gerbers use same format for X/Y; keep one set for simplicity.
            # If they differ, prefer X but emit a warning.
            if (ix, fx) != (iy, fy):
                self.out.warnings.append(f"FS X{ix}{fx} != Y{iy}{fy}; using X format")
            self.int_digits = ix
            self.frac_digits = fx
            return
        m = _re_fs_alt.match(gline)
        if m:
            if m.group(1):
                self.zeros = m.group(1)
            ix, fx = int(m.group(3)), int(m.group(4))
            iy, fy = int(m.group(5)), int(m.group(6))
            if (ix, fx) != (iy, fy):
                self.out.warnings.append(f"FS X{ix}{fx} != Y{iy}{fy}; using X format")
            self.int_digits = ix
            self.frac_digits = fx
            self.units = m.group(7)
            self.out.units = self.units
            return
        m = _re_mo.match(gline)
        if m:
            self.units = m.group(1)
            self.out.units = self.units
            return
        m = _re_add.match(gline)
        if m:
            aid = norm_ap_id(m.group(1))
            ap = parse_aperture_def(m.group(2), m.group(3) or "")
            if ap.type == "C" and ap.size == 0:
                ap.size = 1e-12
            self.apertures[aid] = ap
            return
        m = _re_tool.match(gline)
        if m:
            self.flush_stroke_path()
            self.current_ap = norm_ap_id(m.group(1))
            return
        m = _re_op_alone.match(gline)
        if m:
            self.op_code = int(m.group(1))
            if self.op_code == 3:
                self.flash_at(self.cx, self.cy)
            return
        if _re_g36.match(gline):
            self.flush_stroke_path()
            self.making_region = True
            self.path = []
            return
        if _re_g37.match(gline):
            self.close_region_polygon()
            self.making_region = False
            self.path = []
            return
        m = _re_interp.match(gline)
        if m:
            self.interp_mode = int(m.group(1))
            return
        m = _re_quad.match(gline)
        if m:
            self.quad_mode = "SINGLE" if m.group(1) == "4" else "MULTI"
            return
        if _re_eof.match(gline):
            return
        if any(c in gline for c in "XYIJ") or gline.startswith("G0"):
            if self.is_arc_line(gline):
                self.handle_arc_line(gline)
            else:
                self.handle_linear_line(gline)
            return
        self.out.warnings.append(f"ignored: {gline}")

    def finish(self) -> LayerPreview:
        self.flush_stroke_path()
        b = self.out.bounds
        assert b is not None
        if math.isinf(b.min_x):
            self.out.bounds = Bounds(0, 0, 0, 0)
        if not self.out.units:
            self.out.units = "MM"
        return self.out


def parse_gerber_preview(data: bytes) -> LayerPreview:
    p = _Parser()
    for gline in statements_from_bytes(data):
        gline = gline.strip()
        if not gline:
            continue
        try:
            p.handle_line(gline)
        except Exception as e:  # noqa: BLE001
            p.out.warnings.append(str(e))
    pv = p.finish()
    # Normalize everything to millimeters for downstream NCC/milling code.
    if (pv.units or "").upper() == "IN":
        s = 25.4
        if pv.bounds is not None:
            pv.bounds.min_x *= s
            pv.bounds.min_y *= s
            pv.bounds.max_x *= s
            pv.bounds.max_y *= s
        for st in pv.strokes:
            st.width *= s
            for pt in st.points:
                pt.x *= s
                pt.y *= s
        for c in pv.circles:
            c.cx *= s
            c.cy *= s
            c.r *= s
        for r in pv.rects:
            r.cx *= s
            r.cy *= s
            r.w *= s
            r.h *= s
        for f in pv.fills:
            for ring in f.rings:
                for pt in ring:
                    pt.x *= s
                    pt.y *= s
        pv.units = "MM"
    return pv

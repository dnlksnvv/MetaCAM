"""
NCC pipeline: copper union → hull+margin − copper → FlatCAM clear_polygon2 per island.
"""
from __future__ import annotations

import math
from typing import Any

from shapely.geometry import (
    LineString,
    MultiPolygon,
    Point as ShpPoint,
    Polygon,
    box,
)
from shapely.geometry.base import BaseGeometry, JOIN_STYLE
from shapely.ops import unary_union

from metacam.core.domain.models import (
    Bounds,
    LayerPreview,
    NCCParams,
    NCCToolpathPreview,
    Point,
    Stroke,
)
from metacam.core.gerber.parser import parse_gerber_preview
from metacam.core.ncc.flatcam_seed import clear_polygon2
from metacam.core.ncc.flatcam_validity import (
    find_optim_min_distance,
    flatcam_validity_warnings,
)


def _as_polygons(g: BaseGeometry) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return []


def layer_preview_to_copper_solids(pv: LayerPreview) -> list[Polygon]:
    """
    Separate copper polygons (per stroke / flash / fill ring), analogous to
    FlatCAM aperture ``geometry`` solids used in ``find_optim_mp``.
    """
    out: list[Polygon] = []
    for s in pv.strokes:
        if len(s.points) < 2 or s.width <= 0:
            continue
        ls = LineString([(p.x, p.y) for p in s.points])
        g = ls.buffer(s.width / 2.0, quad_segs=16)
        for p in _as_polygons(g):
            if p.is_valid and not p.is_empty:
                out.append(p)
    for c in pv.circles:
        if c.r <= 0:
            continue
        g = ShpPoint(c.cx, c.cy).buffer(c.r, quad_segs=32)
        for p in _as_polygons(g):
            if p.is_valid and not p.is_empty:
                out.append(p)
    for r in pv.rects:
        if r.w <= 0 or r.h <= 0:
            continue
        poly = box(r.cx - r.w / 2, r.cy - r.h / 2, r.cx + r.w / 2, r.cy + r.h / 2)
        if poly.is_valid and not poly.is_empty:
            out.append(poly)
    for f in pv.fills:
        for ring in f.rings:
            if len(ring) < 3:
                continue
            poly = Polygon([(p.x, p.y) for p in ring])
            if poly.is_valid and not poly.is_empty:
                out.append(poly)
    return out


def layer_preview_to_copper_union(pv: LayerPreview) -> BaseGeometry:
    parts: list[BaseGeometry] = []
    for s in pv.strokes:
        if len(s.points) < 2 or s.width <= 0:
            continue
        ls = LineString([(p.x, p.y) for p in s.points])
        parts.append(ls.buffer(s.width / 2.0, quad_segs=16))
    for c in pv.circles:
        if c.r <= 0:
            continue
        parts.append(ShpPoint(c.cx, c.cy).buffer(c.r, quad_segs=32))
    for r in pv.rects:
        if r.w <= 0 or r.h <= 0:
            continue
        parts.append(box(r.cx - r.w / 2, r.cy - r.h / 2, r.cx + r.w / 2, r.cy + r.h / 2))
    for f in pv.fills:
        for ring in f.rings:
            if len(ring) < 3:
                continue
            poly = Polygon([(p.x, p.y) for p in ring])
            if poly.is_valid and not poly.is_empty:
                parts.append(poly)
    if not parts:
        return Polygon()
    u = unary_union(parts)
    if not u.is_valid:
        u = u.buffer(0)
    return u


def _calculate_bounding_box_itself(geo_n: BaseGeometry) -> BaseGeometry:
    """
    ToolNCC.calculate_bounding_box() for ncc_select == 0 ('Itself').
    """
    if geo_n.is_empty:
        raise ValueError("no copper geometry")
    if isinstance(geo_n, MultiPolygon):
        return geo_n.convex_hull
    return unary_union(geo_n).convex_hull


def _apply_margin_to_bounding_box_itself(bbox: BaseGeometry, ncc_margin: float) -> BaseGeometry:
    """ToolNCC.apply_margin_to_bounding_box() for ncc_select == 0."""
    return bbox.buffer(distance=ncc_margin, join_style=JOIN_STYLE.mitre)


def _get_ncc_empty_area(target: BaseGeometry, boundary: BaseGeometry) -> BaseGeometry:
    """ToolNCC.get_ncc_empty_area(target, boundary) — boundary minus copper."""
    if isinstance(target, list):
        target = MultiPolygon(target)
    try:
        return boundary.difference(target)
    except Exception:
        parts: list[BaseGeometry]
        if isinstance(target, Polygon):
            parts = [target]
        elif isinstance(target, MultiPolygon):
            parts = list(target.geoms)
        else:
            parts = [target]
        b = boundary
        for el in parts:
            b = b.difference(el)
        return b


def empty_area_itself(cu: BaseGeometry, margin_mm: float) -> BaseGeometry:
    """Non-copper region for 'Itself': convex hull / margin / subtract — as FlatCAM ToolNCC."""
    bbox = _calculate_bounding_box_itself(cu)
    boundary = _apply_margin_to_bounding_box_itself(bbox, margin_mm)
    empty = _get_ncc_empty_area(cu, boundary)
    if empty.is_empty:
        raise ValueError("empty clearing region")
    return empty


def _check_inset_nonempty(polys: list[Polygon], tool_dia: float) -> None:
    q = 32
    for p in polys:
        if p.area <= 0:
            continue
        inset = p.buffer(-tool_dia / 2.0, quad_segs=q)
        if inset.is_empty:
            raise ValueError(
                "ncc: inset region empty for this tool diameter (smaller tool or larger margin)"
            )


def _bounds_from_lines(lines: list[Stroke], pad: float) -> Bounds:
    inf = float("inf")
    b = Bounds(inf, inf, -inf, -inf)
    for ln in lines:
        for p in ln.points:
            b.min_x = min(b.min_x, p.x)
            b.min_y = min(b.min_y, p.y)
            b.max_x = max(b.max_x, p.x)
            b.max_y = max(b.max_y, p.y)
    if math.isinf(b.min_x):
        return Bounds(0, 0, 0, 0)
    h = pad / 2
    return Bounds(b.min_x - h, b.min_y - h, b.max_x + h, b.max_y + h)


def generate_ncc_from_gerber_bytes(
    data: bytes, params: NCCParams
) -> tuple[NCCToolpathPreview, LayerPreview]:
    if params.selection != "itself":
        raise ValueError("unsupported selection (only 'itself')")
    if params.method != "seed":
        raise ValueError("unsupported method (only 'seed' / tools_ncc_method 1)")
    if params.tool_shape not in ("", "V", "C"):
        raise ValueError("unsupported toolShape")
    if params.tool_diameter <= 0:
        raise ValueError("bad tool diameter")
    if not (0 <= params.overlap < 1):
        raise ValueError("overlap must be in [0,1) after normalization (FlatCAM percent / 100)")

    pv = parse_gerber_preview(data)
    cu = layer_preview_to_copper_union(pv)
    if cu.is_empty:
        raise ValueError("no copper geometry")

    warnings = list(pv.warnings)
    if params.check_validity:
        solids = layer_preview_to_copper_solids(pv)
        msg, min_d = find_optim_min_distance(solids, params.decimals)
        if msg != "ok":
            warnings.append(msg.strip())
        elif min_d is not None:
            warnings.extend(
                flatcam_validity_warnings(
                    params.tool_diameter, min_d, params.decimals
                )
            )

    empty = empty_area_itself(cu, params.margin)
    islands = _as_polygons(empty)
    if params.check_inset:
        _check_inset_nonempty(islands, params.tool_diameter)

    out_lines: list[Stroke] = []
    steps = params.steps_per_circle if params.steps_per_circle > 0 else 64
    disp_w = params.tool_diameter * 0.15

    for poly in islands:
        if poly.area <= 0:
            continue
        segs = clear_polygon2(
            poly,
            params.tool_diameter,
            steps,
            seedpoint=None,
            overlap=params.overlap,
            connect=params.connect,
            contour=params.contour,
        )
        for ls in segs:
            coords = list(ls.coords)
            if len(coords) < 2:
                continue
            out_lines.append(
                Stroke(disp_w, [Point(x, y) for x, y in coords], clear=False)
            )

    tp = NCCToolpathPreview(
        tool_diameter=params.tool_diameter,
        overlap=params.overlap,
        margin=params.margin,
        bounds=_bounds_from_lines(out_lines, params.tool_diameter),
        lines=out_lines,
        warnings=warnings,
    )
    return tp, pv


def ncc_response_dict(tp: NCCToolpathPreview, copper: LayerPreview) -> dict[str, Any]:
    return {"copper": copper.as_dict(), "toolpath": tp.as_dict()}

"""
FlatCAM camlib.Geometry.clear_polygon2 (seed) + paint_connect — same control flow
as FlatCAM_beta_8.994_sources/camlib.py (Shapely + rtree).

Contour buffering expands MultiPolygon parts explicitly (Shapely 2: MultiPolygon
is not iterable; FlatCAM relied on older iterable behaviour for autolist loops).
"""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from metacam.core.ncc.flatcam_rtree import FlatCAMRTreeStorage, autolist


def _insert_path_segments(geoms: FlatCAMRTreeStorage, path: BaseGeometry) -> None:
    """
    Insert intersection segments into rtree storage.
    FlatCAM used ``for p in path: insert(p)`` except TypeError; Shapely 2
    yields MultiLineString / collections that need explicit expansion.
    """
    if path.is_empty:
        return
    gt = path.geom_type
    if gt == "LineString":
        geoms.insert(path)
        return
    if gt == "LinearRing":
        geoms.insert(LineString(path.coords))
        return
    if gt == "MultiLineString":
        for ls in path.geoms:
            geoms.insert(ls)
        return
    if gt == "GeometryCollection":
        for sub in path.geoms:
            _insert_path_segments(geoms, sub)
        return
    try:
        for p in path:
            _insert_path_segments(geoms, p)
    except TypeError:
        geoms.insert(path)


def _polygon_parts_from_buffer_result(buf: BaseGeometry) -> list[Polygon]:
    """Polygons produced by buffer(-tooldia/2), matching FlatCAM autolist + for-loop intent."""
    if buf is None or buf.is_empty:
        return []
    gt = buf.geom_type
    if gt == "Polygon":
        return [buf]  # type: ignore[list-item]
    if gt == "MultiPolygon":
        return list(buf.geoms)  # type: ignore[union-attr]
    raw = autolist(buf)
    out: list[Polygon] = []
    for x in raw:
        if x is None or x.is_empty:
            continue
        if x.geom_type == "Polygon":
            out.append(x)  # type: ignore[arg-type]
        elif x.geom_type == "MultiPolygon":
            out.extend(x.geoms)  # type: ignore[union-attr]
    return out


def paint_connect(
    storage: FlatCAMRTreeStorage,
    boundary: Polygon,
    tooldia: float,
    steps_per_circle: int,
    max_walk: float | None = None,
) -> FlatCAMRTreeStorage | None:
    """
    camlib.Geometry.paint_connect — same algorithm as FlatCAM 8.994.
    """
    max_walk = max_walk or 10 * tooldia
    steps_int = int(steps_per_circle)

    def get_pts(o):
        return [o.coords[0], o.coords[-1]]

    optimized_paths = FlatCAMRTreeStorage()
    optimized_paths.get_points = get_pts
    current_pt = (0, 0)
    try:
        pt, geo = storage.nearest(current_pt)
    except StopIteration:
        return None

    storage.remove(geo)

    geo = LineString(geo)
    current_pt = geo.coords[-1]
    try:
        while True:
            pt, candidate = storage.nearest(current_pt)
            storage.remove(candidate)

            candidate = LineString(candidate)

            if pt != candidate.coords[0] and pt == candidate.coords[-1]:
                candidate = LineString(list(candidate.coords)[::-1])

            walk_path = LineString([current_pt, pt])
            walk_cut = walk_path.buffer(tooldia / 2, steps_int)

            if walk_cut.within(boundary) and walk_path.length < max_walk:
                geo = LineString(list(geo.coords) + list(candidate.coords))
            else:
                optimized_paths.insert(geo)
                geo = candidate

            current_pt = geo.coords[-1]

    except StopIteration:
        optimized_paths.insert(geo)

    return optimized_paths


def rtree_storage_to_linestrings(storage: FlatCAMRTreeStorage | None) -> list[LineString]:
    if storage is None:
        return []
    out: list[LineString] = []
    for g in storage.get_objects():
        if g is None or g.is_empty:
            continue
        ls = LineString(g.coords)
        if len(ls.coords) >= 2:
            out.append(ls)
    return out


def clear_polygon2(
    polygon_to_clear: Polygon,
    tooldia: float,
    steps_per_circle: int,
    seedpoint=None,
    overlap: float = 0.15,
    connect: bool = True,
    contour: bool = True,
) -> list[LineString]:
    """
    Same algorithm as camlib.Geometry.clear_polygon2 (FlatCAM 8.994), without Qt/processEvents/abort.
    Returns list[LineString] for JSON/API (FlatCAM returns FlatCAMRTreeStorage).
    """
    steps_int = int(steps_per_circle)
    radius = tooldia / 2 * (1 - overlap)

    def get_pts(o):
        return [o.coords[0], o.coords[-1]]

    geoms = FlatCAMRTreeStorage()
    geoms.get_points = get_pts

    path_margin = polygon_to_clear.buffer(-tooldia / 2, steps_int)
    if path_margin.is_empty or path_margin is None:
        return []

    if seedpoint is None:
        seedpoint = path_margin.representative_point()

    while True:
        path = Point(seedpoint).buffer(radius, steps_int).exterior
        path = path.intersection(path_margin)

        if path.is_empty:
            break
        _insert_path_segments(geoms, path)

        radius += tooldia * (1 - overlap)

    if contour:
        buffered_poly = _polygon_parts_from_buffer_result(
            polygon_to_clear.buffer(-tooldia / 2, steps_int)
        )
        outer_edges = [x.exterior for x in buffered_poly]
        inner_edges = []
        for x in buffered_poly:
            for y in x.interiors:
                inner_edges.append(y)
        for g in outer_edges + inner_edges:
            if g and not g.is_empty:
                geoms.insert(g)

    if connect:
        geoms_conn = paint_connect(geoms, polygon_to_clear, tooldia, steps_int, None)
        if geoms_conn:
            return rtree_storage_to_linestrings(geoms_conn)

    return rtree_storage_to_linestrings(geoms)

from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry


def shapely_to_paths(g: BaseGeometry) -> list[list[list[float]]]:
    """
    Convert Shapely Polygon/MultiPolygon into gerber-wizard compatible paths:
    - returns list of rings, each ring is [[x,y], ...]
    - includes exterior and interior rings; consumer can fill with even-odd rule.
    """
    if g is None or g.is_empty:
        return []
    polys: list[Polygon] = []
    if isinstance(g, Polygon):
        polys = [g]
    elif isinstance(g, MultiPolygon):
        polys = list(g.geoms)
    else:
        try:
            gg = g.buffer(0)
        except Exception:
            return []
        if isinstance(gg, Polygon):
            polys = [gg]
        elif isinstance(gg, MultiPolygon):
            polys = list(gg.geoms)
        else:
            return []

    out: list[list[list[float]]] = []
    for p in polys:
        if p.is_empty:
            continue
        out.append([[float(x), float(y)] for x, y in list(p.exterior.coords)])
        for hole in p.interiors:
            out.append([[float(x), float(y)] for x, y in list(hole.coords)])
    return out


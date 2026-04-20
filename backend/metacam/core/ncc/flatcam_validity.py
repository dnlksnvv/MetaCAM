"""
FlatCAM ToolNCC.find_optim_mp — minimum distance between copper solids (aperture geometry).

Uses the same loop as appTools/ToolNCC.py (pairwise distance, rounded to ``decimals``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

if TYPE_CHECKING:
    pass


def find_optim_min_distance(
    solids: list[Polygon],
    decimals: int,
) -> tuple[str, float | None]:
    """
    Mirror ``ToolNCC.find_optim_mp(aperture_storage, decimals)`` outcome:

    Returns ``('ok', min_dist)`` or ``(error_message, None)``.
    """
    total_geo = [g for g in solids if g is not None and not g.is_empty and g.is_valid]
    if len(total_geo) < 2:
        return (
            "[ERROR_NOTCL] The Gerber object has one Polygon as geometry.\n"
            "There are no distances between geometry elements to be found.",
            None,
        )

    try:
        mp = MultiPolygon(total_geo)
    except Exception:
        u = unary_union(total_geo)
        if u.geom_type == "Polygon":
            return (
                "[ERROR_NOTCL] The Gerber object has one Polygon as geometry.\n"
                "There are no distances between geometry elements to be found.",
                None,
            )
        if u.geom_type != "MultiPolygon":
            u = u.buffer(0)
            if u.geom_type != "MultiPolygon":
                return (
                    "[ERROR_NOTCL] The Gerber object has one Polygon as geometry.\n"
                    "There are no distances between geometry elements to be found.",
                    None,
                )
        mp = u

    try:
        mp = mp.buffer(0)
    except Exception:
        pass

    geoms = list(mp.geoms) if mp.geom_type == "MultiPolygon" else [mp]
    if len(geoms) < 2:
        return (
            "[ERROR_NOTCL] The Gerber object has one Polygon as geometry.\n"
            "There are no distances between geometry elements to be found.",
            None,
        )

    min_dict: dict[float, list] = {}
    idx = 1
    for geo in geoms:
        for s_geo in geoms[idx:]:
            dist = geo.distance(s_geo)
            dist = float("%.*f" % (decimals, dist))
            if dist in min_dict:
                min_dict[dist].append(None)
            else:
                min_dict[dist] = [None]
        idx += 1

    min_list = list(min_dict.keys())
    min_dist = min(min_list)
    return "ok", min_dist


def flatcam_validity_warnings(
    tool_diameter: float,
    min_dist: float | None,
    decimals: int,
) -> list[str]:
    """Messages aligned with ToolNCC.find_safe_tooldia_worker (suitable vs none)."""
    if min_dist is None:
        return []
    td = float("%.*f" % (decimals, tool_diameter))
    md = float("%.*f" % (decimals, min_dist))
    if td <= md:
        return [
            "At least one of the selected tools can do a complete isolation. "
            f"(toolDia={td} <= minFeatureGap={md})"
        ]
    return [
        "Incomplete isolation. None of the selected tools could do a complete isolation. "
        f"(toolDia={td} > minFeatureGap={md})"
    ]

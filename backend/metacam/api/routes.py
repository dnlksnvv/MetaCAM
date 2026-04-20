from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from metacam.core.domain.models import CNCJobPreview, MillingParams, NCCParams, Stroke, Point
from metacam.core.domain.export_preview import shapely_to_paths
from metacam.core.gerber.parser import parse_gerber_preview
from metacam.core.ncc.pipeline import generate_ncc_from_gerber_bytes, ncc_response_dict
from metacam.core.milling.gcode import generate_cncjob_gcode
from metacam.core.store import FsStore
from metacam.core.ncc.pipeline import layer_preview_to_copper_union

log = logging.getLogger("metacam.api")
router = APIRouter()

from pathlib import Path

_STORE = FsStore(root=(Path(__file__).resolve().parent.parent.parent / "data").resolve())


@router.post("/gerber/preview")
async def gerber_preview(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        pv = parse_gerber_preview(data)
        return pv.as_dict()
    except Exception as e:  # noqa: BLE001
        log.exception("gerber preview")
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/ncc/generate")
async def ncc_generate(
    file: UploadFile = File(...),
    params: str = Form(""),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        raw: Any = json.loads(params) if (params or "").strip() else {}
        p = NCCParams.from_json(raw if isinstance(raw, dict) else {})
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"params JSON: {e}") from e
    log.info("ncc/generate start: file=%s bytes=%d", file.filename, len(data))
    try:
        tp, copper = generate_ncc_from_gerber_bytes(data, p)
    except ValueError as e:
        log.warning("ncc/generate error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("ncc/generate")
        raise HTTPException(status_code=422, detail=str(e)) from e
    log.info("ncc/generate done: polylines=%d", len(tp.lines))
    return ncc_response_dict(tp, copper)


@router.post("/milling/generate")
async def milling_generate(
    toolpath: str = Form(""),
    params: str = Form(""),
) -> dict[str, Any]:
    """
    Generate a simplified CNCJob (G-code) from an existing toolpath (NCC lines).
    """
    try:
        raw_tp: Any = json.loads(toolpath) if (toolpath or "").strip() else {}
        raw_p: Any = json.loads(params) if (params or "").strip() else {}
        if not isinstance(raw_tp, dict):
            raise ValueError("toolpath JSON must be an object")
        if not isinstance(raw_p, dict):
            raise ValueError("params JSON must be an object")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Parse toolpath lines (same shape as NCCToolpathPreview.as_dict())
    try:
        lines_raw = raw_tp.get("lines") or []
        if not isinstance(lines_raw, list):
            raise ValueError("toolpath.lines must be an array")
        lines: list[Stroke] = []
        for ln in lines_raw:
            pts = ln.get("points") if isinstance(ln, dict) else None
            w = ln.get("width") if isinstance(ln, dict) else None
            if not isinstance(pts, list) or len(pts) < 2:
                continue
            ppts: list[Point] = []
            for p in pts:
                if not isinstance(p, dict):
                    continue
                x = float(p.get("x"))
                y = float(p.get("y"))
                ppts.append(Point(x, y))
            if len(ppts) >= 2:
                lines.append(Stroke(float(w or 0.02), ppts, False))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"toolpath parse: {e}") from e

    mp = MillingParams.from_json(raw_p)
    log.info("milling/generate start: polylines=%d", len(lines))
    try:
        gcode, bounds, preview_lines = generate_cncjob_gcode(lines, mp)
        cnc = CNCJobPreview(
            tool_diameter=mp.tool_diameter,
            bounds=bounds,
            lines=preview_lines,
            gcode=gcode,
            warnings=[],
        )
    except ValueError as e:
        log.warning("milling/generate error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("milling/generate")
        raise HTTPException(status_code=422, detail=str(e)) from e
    log.info("milling/generate done: gcode_bytes=%d", len(gcode.encode("utf-8")))
    return {"cncjob": cnc.as_dict()}


@router.post("/milling/generate_from_gerber")
async def milling_generate_from_gerber(
    file: UploadFile = File(...),
    ncc_params: str = Form(""),
    milling_params: str = Form(""),
) -> dict[str, Any]:
    """
    Generate CNCJob directly from Gerber file:
    Gerber -> NCC -> G-code.

    This avoids sending megabytes of toolpath JSON back to server.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        raw_n: Any = json.loads(ncc_params) if (ncc_params or "").strip() else {}
        raw_m: Any = json.loads(milling_params) if (milling_params or "").strip() else {}
        n = NCCParams.from_json(raw_n if isinstance(raw_n, dict) else {})
        m = MillingParams.from_json(raw_m if isinstance(raw_m, dict) else {})
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"params JSON: {e}") from e

    log.info("milling/generate_from_gerber start: file=%s bytes=%d", file.filename, len(data))
    try:
        tp, _copper = generate_ncc_from_gerber_bytes(data, n)
        gcode, bounds, preview_lines = generate_cncjob_gcode(tp.lines, m)
        cnc = CNCJobPreview(
            tool_diameter=m.tool_diameter,
            bounds=bounds,
            lines=preview_lines,
            gcode=gcode,
            warnings=list(tp.warnings),
        )
    except ValueError as e:
        log.warning("milling/generate_from_gerber error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("milling/generate_from_gerber")
        raise HTTPException(status_code=422, detail=str(e)) from e
    log.info(
        "milling/generate_from_gerber done: polylines=%d gcode_bytes=%d",
        len(tp.lines),
        len(gcode.encode("utf-8")),
    )
    return {"cncjob": cnc.as_dict()}


# -------------------- Project/Config API (for real app) --------------------


@router.get("/configs/recent")
async def configs_recent() -> dict[str, Any]:
    return {"configs": _STORE.get_recent_configs()}


@router.post("/configs")
async def configs_create(config: str = Form("")) -> dict[str, Any]:
    try:
        raw: Any = json.loads(config) if (config or "").strip() else {}
        if not isinstance(raw, dict):
            raise ValueError("config must be a JSON object")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"config JSON: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    stored = _STORE.upsert_recent_config(raw, max_items=4)
    return {"config": stored, "configs": _STORE.get_recent_configs()}


@router.delete("/configs/{config_id}")
async def configs_delete(config_id: str) -> dict[str, Any]:
    configs = _STORE.delete_recent_config(config_id)
    return {"ok": True, "configs": configs}


@router.get("/projects")
async def projects_list() -> dict[str, Any]:
    return {"projects": _STORE.list_projects()}


@router.post("/projects")
async def projects_create(
    file: UploadFile = File(...),
    name: str = Form(""),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    prj = _STORE.create_project_from_bytes(file.filename or "file", data)
    if (name or "").strip():
        prj = _STORE.rename_project(prj["id"], name)
    # compute and store preview now (include gerber-wizard compatible copper.paths)
    try:
        pv_obj = parse_gerber_preview(data)
        pv = pv_obj.as_dict()
        cu = layer_preview_to_copper_union(pv_obj)
        pv["copper"] = {"paths": shapely_to_paths(cu)}
    except Exception as e:  # noqa: BLE001
        pv = {"error": str(e)}
    # store preview in project folder (not a run)
    proj_dir = _STORE.projects_dir / prj["id"]
    (proj_dir / "preview.json").write_text(json.dumps(pv, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project": prj, "preview": pv}


@router.get("/projects/{project_id}")
async def projects_get(project_id: str) -> dict[str, Any]:
    prj = _STORE.get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="project not found")
    # attach preview + latest run artifacts if present
    proj_dir = _STORE.projects_dir / project_id
    preview = None
    try:
        preview = json.loads((proj_dir / "preview.json").read_text(encoding="utf-8"))
    except Exception:
        preview = None
    # Backward compatibility: older preview.json may not have copper.paths.
    needs_paths = (
        isinstance(preview, dict)
        and (
            not isinstance(preview.get("copper"), dict)
            or not isinstance(preview.get("copper", {}).get("paths"), list)
        )
    )
    if preview is None or needs_paths:
        src = _STORE.get_project_source_path(project_id)
        if src:
            try:
                data = src.read_bytes()
                pv_obj = parse_gerber_preview(data)
                pv = pv_obj.as_dict()
                cu = layer_preview_to_copper_union(pv_obj)
                pv["copper"] = {"paths": shapely_to_paths(cu)}
                preview = pv
                (proj_dir / "preview.json").write_text(
                    json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
    latest = prj.get("latest_run") if isinstance(prj.get("latest_run"), dict) else None
    latest_payload: dict[str, Any] | None = None
    if latest and latest.get("id"):
        rid = str(latest.get("id"))
        run_dir = proj_dir / "runs" / rid
        try:
            ncc = json.loads((run_dir / "ncc.json").read_text(encoding="utf-8"))
        except Exception:
            ncc = None
        try:
            cncjob = json.loads((run_dir / "cncjob.json").read_text(encoding="utf-8"))
        except Exception:
            cncjob = None
        # Merge run summary (status/id/...) with artifacts so frontend can use `latest.status`.
        latest_payload = {**latest, "ncc": ncc, "cncjob": cncjob}
    return {"project": prj, "preview": preview, "latest": latest_payload, "config": prj.get("last_config")}


@router.patch("/projects/{project_id}")
async def projects_rename(project_id: str, name: str = Form("")) -> dict[str, Any]:
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="name required")
    try:
        prj = _STORE.rename_project(project_id, name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    return {"project": prj}


@router.delete("/projects/{project_id}")
async def projects_delete(project_id: str) -> dict[str, Any]:
    prj = _STORE.get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="project not found")
    _STORE.delete_project(project_id)
    return {"ok": True}


@router.get("/projects/{project_id}/source")
async def projects_source(project_id: str):
    p = _STORE.get_project_source_path(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="source not found")
    return FileResponse(path=str(p), filename=p.name, media_type="application/octet-stream")


@router.post("/projects/{project_id}/generate")
async def projects_generate(
    project_id: str,
    config: str = Form(""),
    config_id: str = Form(""),
) -> dict[str, Any]:
    """
    Unified action: Project Gerber -> NCC -> CNCJob, with persisted config history.

    - If `config` is provided: upsert into recent configs and use it.
    - Else if `config_id` provided: find it in recent configs and use it.
    """
    prj = _STORE.get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="project not found")
    src_path = _STORE.get_project_source_path(project_id)
    if not src_path:
        raise HTTPException(status_code=404, detail="source not found")
    data = src_path.read_bytes()

    cfg_obj: dict[str, Any] | None = None
    if (config or "").strip():
        try:
            raw: Any = json.loads(config)
            if not isinstance(raw, dict):
                raise ValueError("config must be object")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"config JSON: {e}") from e
        cfg_obj = _STORE.upsert_recent_config(raw, max_items=4)
    elif (config_id or "").strip():
        cid = (config_id or "").strip()
        for c in _STORE.get_recent_configs():
            if isinstance(c, dict) and c.get("id") == cid:
                cfg_obj = c
                break
        if not cfg_obj:
            raise HTTPException(status_code=404, detail="config_id not found in recent")
    else:
        # default config
        cfg_obj = _STORE.upsert_recent_config(
            {
                "method": "ncc",
                "ncc": {
                    "toolDiameter": 0.1,
                    "toolType": "V",
                    "overlapPct": 40,
                    "margin": 1.0,
                    "connect": True,
                    "contour": True,
                    "checkValidity": True,
                    "checkInset": True,
                },
                "milling": {
                    "toolDiameter": 0.5,
                    "cutZ": -0.05,
                    "travelZ": 2.0,
                    "feedrateXY": 120,
                    "feedrateZ": 60,
                    "spindleSpeed": 0,
                    "dwell": False,
                    "dwellTime": 1.0,
                    "endMoveZ": 15.0,
                },
            },
            max_items=4,
        )

    run = _STORE.create_run(project_id, cfg_obj)
    try:
        ncc_cfg = cfg_obj.get("ncc") if isinstance(cfg_obj.get("ncc"), dict) else {}
        mill_cfg = cfg_obj.get("milling") if isinstance(cfg_obj.get("milling"), dict) else {}

        # Map unified config to our existing params
        ncc_params = {
            "toolDiameter": ncc_cfg.get("toolDiameter", 0.1),
            "toolShape": ncc_cfg.get("toolType", "V"),
            "overlap": ncc_cfg.get("overlapPct", 40),
            "margin": ncc_cfg.get("margin", 1.0),
            "method": 1,
            "connect": ncc_cfg.get("connect", True),
            "contour": ncc_cfg.get("contour", True),
            "toolsNccRef": 0,
            "checkValidity": ncc_cfg.get("checkValidity", True),
            "checkInset": ncc_cfg.get("checkInset", True),
            "stepsPerCircle": 64,
        }
        milling_params = {
            "toolDiameter": mill_cfg.get("toolDiameter", 0.5),
            "cutZ": mill_cfg.get("cutZ", -0.05),
            "travelZ": mill_cfg.get("travelZ", 2.0),
            "feedrateXY": mill_cfg.get("feedrateXY", 120),
            "feedrateZ": mill_cfg.get("feedrateZ", 60),
            "spindleSpeed": mill_cfg.get("spindleSpeed", 0),
            "dwell": mill_cfg.get("dwell", False),
            "dwellTime": mill_cfg.get("dwellTime", 1.0),
            "endMoveZ": mill_cfg.get("endMoveZ", 15.0),
            "preprocessor": mill_cfg.get("preprocessor", "default"),
        }

        n = NCCParams.from_json(ncc_params)
        m = MillingParams.from_json(milling_params)

        tp, copper = generate_ncc_from_gerber_bytes(data, n)
        gcode, bounds, preview_lines = generate_cncjob_gcode(tp.lines, m)
        gcode_rel = _STORE.store_run_gcode(project_id, run["id"], "job.nc", gcode.encode("utf-8"))
        ncc_obj = tp.as_dict()
        cncjob_obj = CNCJobPreview(
            tool_diameter=m.tool_diameter,
            bounds=bounds,
            lines=preview_lines,
            gcode=gcode,
            warnings=list(tp.warnings),
        ).as_dict()

        # store artifacts (without embedding huge data in project.json)
        proj_dir = _STORE.projects_dir / project_id
        run_dir = proj_dir / "runs" / run["id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "ncc.json").write_text(json.dumps(ncc_obj, ensure_ascii=False), encoding="utf-8")
        # store cncjob without gcode text (download via file)
        cncjob_small = dict(cncjob_obj)
        cncjob_small.pop("gcode", None)
        (run_dir / "cncjob.json").write_text(json.dumps(cncjob_small, ensure_ascii=False), encoding="utf-8")

        result = {
            "gcode_path": gcode_rel,
            "ncc_summary": {"lines": len(ncc_obj.get("lines") or []), "bounds": ncc_obj.get("bounds")},
            "cncjob_summary": {"lines": len(cncjob_small.get("lines") or []), "bounds": cncjob_small.get("bounds")},
        }
        run = _STORE.finish_run_ok(project_id, run["id"], result)
        # set last_config_id on project
        proj_meta = _STORE.get_project(project_id) or {}
        proj_meta["last_config_id"] = cfg_obj.get("id")
        proj_meta["last_config"] = cfg_obj
        # atomic update
        (proj_dir / "project.json").write_text(
            json.dumps(proj_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        download_url = f"/api/v1/projects/{project_id}/runs/{run['id']}/download"
        return {
            "project": _STORE.get_project(project_id),
            "config": cfg_obj,
            "configs": _STORE.get_recent_configs(),
            "run": run,
            # Keep legacy copper preview for our own UI...
            "copper": {"paths": shapely_to_paths(layer_preview_to_copper_union(copper))},
            # ...and also return raw preview if needed by other clients
            "preview": copper.as_dict(),
            "ncc": {"paths": [[ [p["x"], p["y"]] for p in ln["points"]] for ln in (ncc_obj.get("lines") or [])]},
            "cncjob": {"paths": [[ [p["x"], p["y"]] for p in ln["points"]] for ln in (cncjob_obj.get("lines") or [])]},
            "downloadUrl": download_url,
        }
    except Exception as e:  # noqa: BLE001
        _STORE.finish_run_error(project_id, run["id"], str(e))
        raise


@router.get("/projects/{project_id}/runs/{run_id}")
async def projects_run_get(project_id: str, run_id: str) -> dict[str, Any]:
    run = _STORE.get_run(project_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": run}


@router.get("/projects/{project_id}/runs/{run_id}/download")
async def projects_run_download(project_id: str, run_id: str):
    run = _STORE.get_run(project_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    res = run.get("result") if isinstance(run.get("result"), dict) else None
    rel = res.get("gcode_path") if res else None
    if not isinstance(rel, str):
        raise HTTPException(status_code=404, detail="gcode not found")
    p = _STORE.get_run_file_path(project_id, run_id, rel)
    if not p:
        raise HTTPException(status_code=404, detail="gcode file missing")
    return FileResponse(path=str(p), filename=p.name, media_type="text/plain")

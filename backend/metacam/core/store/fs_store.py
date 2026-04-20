from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _safe_filename(name: str) -> str:
    name = (name or "file").strip()
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", ".", " "):
            keep.append(ch)
        else:
            keep.append("_")
    out = "".join(keep).strip().replace(" ", "_")
    return out[:120] or "file"


def _stable_hash_config(obj: dict[str, Any]) -> str:
    # Stable JSON hash (normalized ordering).
    import hashlib

    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class FsStore:
    root: Path

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def configs_path(self) -> Path:
        return self.root / "configs" / "configs.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default
        except Exception:
            return default

    # -------------------- Configs --------------------
    def get_recent_configs(self) -> list[dict[str, Any]]:
        data = self._read_json(self.configs_path, {"recent": []})
        recent = data.get("recent") if isinstance(data, dict) else []
        return recent if isinstance(recent, list) else []

    def upsert_recent_config(self, config: dict[str, Any], max_items: int = 4) -> dict[str, Any]:
        """
        Insert config into recent list (dedupe by content hash), keep max_items, newest first.
        Returns stored config with id/hash/timestamps.
        """
        cfg = dict(config or {})
        cfg.pop("id", None)
        cfg.pop("hash", None)
        cfg_hash = _stable_hash_config(cfg)
        now = _now_iso()

        recent = self.get_recent_configs()
        # Remove existing with same hash
        recent = [c for c in recent if not (isinstance(c, dict) and c.get("hash") == cfg_hash)]

        stored = {
            "id": f"cfg_{uuid.uuid4().hex[:12]}",
            "hash": cfg_hash,
            "created_at": now,
            "updated_at": now,
            **cfg,
        }
        recent.insert(0, stored)
        recent = recent[:max_items]
        _atomic_write_json(self.configs_path, {"recent": recent})
        return stored

    def delete_recent_config(self, config_id_or_hash: str) -> list[dict[str, Any]]:
        """
        Delete a config from recent list by id or hash. Returns updated recent list.
        """
        key = (config_id_or_hash or "").strip()
        if not key:
            return self.get_recent_configs()
        recent = self.get_recent_configs()
        recent2 = [
            c
            for c in recent
            if not (isinstance(c, dict) and (c.get("id") == key or c.get("hash") == key))
        ]
        _atomic_write_json(self.configs_path, {"recent": recent2})
        return recent2

    # -------------------- Projects --------------------
    def list_projects(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.projects_dir.exists():
            return []
        for p in sorted(self.projects_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_dir():
                continue
            meta = self._read_json(p / "project.json", None)
            if isinstance(meta, dict):
                meta2 = self.compact_project_meta(meta)
                # persist compaction if needed
                if meta2 is not meta:
                    _atomic_write_json(p / "project.json", meta2)
                out.append(meta2)
        return out

    def create_project_from_bytes(self, filename: str, data: bytes) -> dict[str, Any]:
        pid = f"prj_{uuid.uuid4().hex[:12]}"
        proj_dir = self.projects_dir / pid
        proj_dir.mkdir(parents=True, exist_ok=True)

        safe = _safe_filename(filename)
        src_path = proj_dir / safe
        src_path.write_bytes(data)

        now = _now_iso()
        meta = {
            "id": pid,
            "name": safe,
            "created_at": now,
            "updated_at": now,
            "source": {
                "filename": safe,
                "path": str(src_path.relative_to(self.root)),
                "size_bytes": len(data),
            },
            "last_config_id": None,
            "latest_run": None,
        }
        _atomic_write_json(proj_dir / "project.json", meta)
        self.prune_projects(max_items=4)
        return meta

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        proj_dir = self.projects_dir / project_id
        meta = self._read_json(proj_dir / "project.json", None)
        if not isinstance(meta, dict):
            return None
        meta2 = self.compact_project_meta(meta)
        if meta2 is not meta:
            _atomic_write_json(proj_dir / "project.json", meta2)
        return meta2

    def compact_project_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure `project.json` stays small.
        Old versions may have embedded huge NCC/CNCJob + G-code strings in latest_run.result.
        We keep only summary + file references.
        """
        changed = False
        m = dict(meta)
        lr = m.get("latest_run")
        if isinstance(lr, dict):
            lr2 = dict(lr)
            res = lr2.get("result")
            if isinstance(res, dict):
                # New format already stores summaries
                if "ncc_summary" in res or "cncjob_summary" in res or "gcode_path" in res:
                    # drop any legacy heavy keys
                    for k in ("ncc", "cncjob", "copper", "toolpath", "gcode"):
                        if k in res:
                            res.pop(k, None)
                            changed = True
                    lr2["result"] = res
                else:
                    # Legacy: extract lightweight summaries if possible, then drop heavy content
                    ncc = res.get("ncc") if isinstance(res.get("ncc"), dict) else None
                    cnc = res.get("cncjob") if isinstance(res.get("cncjob"), dict) else None
                    gpath = res.get("gcode_path") if isinstance(res.get("gcode_path"), str) else None
                    ncc_summary = None
                    if ncc:
                        lines = ncc.get("lines")
                        ncc_summary = {
                            "lines": len(lines) if isinstance(lines, list) else None,
                            "bounds": ncc.get("bounds"),
                        }
                    cnc_summary = None
                    if cnc:
                        lines = cnc.get("lines")
                        cnc_summary = {
                            "lines": len(lines) if isinstance(lines, list) else None,
                            "bounds": cnc.get("bounds"),
                        }
                    lr2["result"] = {
                        "gcode_path": gpath,
                        "ncc_summary": ncc_summary,
                        "cncjob_summary": cnc_summary,
                    }
                    changed = True
            # Ensure we never embed huge keys in latest_run
            lr2.pop("ncc", None)
            lr2.pop("cncjob", None)
            if lr2 != lr:
                m["latest_run"] = lr2
                changed = True
        # default key
        if "last_config_id" not in m:
            m["last_config_id"] = None
            changed = True
        # last_config should be small; if missing keep None
        if "last_config" not in m:
            m["last_config"] = None
            changed = True
        return m if changed else meta

    def get_project_source_path(self, project_id: str) -> Path | None:
        meta = self.get_project(project_id)
        if not meta:
            return None
        src = meta.get("source") if isinstance(meta.get("source"), dict) else None
        rel = src.get("path") if src else None
        if not isinstance(rel, str):
            return None
        p = self.root / rel
        return p if p.exists() else None

    def rename_project(self, project_id: str, new_name: str) -> dict[str, Any]:
        proj_dir = self.projects_dir / project_id
        meta = self._read_json(proj_dir / "project.json", None)
        if not isinstance(meta, dict):
            raise FileNotFoundError("project not found")
        meta["name"] = _safe_filename(new_name) or meta.get("name") or project_id
        meta["updated_at"] = _now_iso()
        _atomic_write_json(proj_dir / "project.json", meta)
        return meta

    def delete_project(self, project_id: str) -> None:
        proj_dir = self.projects_dir / project_id
        if proj_dir.exists() and proj_dir.is_dir():
            shutil.rmtree(proj_dir)

    def prune_projects(self, max_items: int = 4) -> None:
        """
        Keep only the newest `max_items` projects; delete the oldest by mtime.
        """
        if not self.projects_dir.exists():
            return
        dirs = [p for p in self.projects_dir.iterdir() if p.is_dir()]
        if len(dirs) <= max_items:
            return
        dirs_sorted = sorted(dirs, key=lambda x: x.stat().st_mtime, reverse=True)
        for p in dirs_sorted[max_items:]:
            try:
                shutil.rmtree(p)
            except Exception:
                pass

    # -------------------- Runs --------------------
    def create_run(self, project_id: str, config: dict[str, Any]) -> dict[str, Any]:
        rid = f"run_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        run = {
            "id": rid,
            "project_id": project_id,
            "config": config,
            "status": "running",
            "started_at": now,
            "finished_at": None,
            "error": None,
            "result": None,
        }
        run_dir = self.projects_dir / project_id / "runs" / rid
        _atomic_write_json(run_dir / "run.json", run)
        # update project latest_run pointer
        self._update_project_latest_run(project_id, run)
        return run

    def finish_run_ok(
        self,
        project_id: str,
        run_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        run_dir = self.projects_dir / project_id / "runs" / run_id
        run = self._read_json(run_dir / "run.json", None)
        if not isinstance(run, dict):
            raise FileNotFoundError("run not found")
        run["status"] = "done"
        run["finished_at"] = _now_iso()
        run["result"] = result
        _atomic_write_json(run_dir / "run.json", run)
        self._update_project_latest_run(project_id, run)
        return run

    def finish_run_error(self, project_id: str, run_id: str, error: str) -> dict[str, Any]:
        run_dir = self.projects_dir / project_id / "runs" / run_id
        run = self._read_json(run_dir / "run.json", None)
        if not isinstance(run, dict):
            raise FileNotFoundError("run not found")
        run["status"] = "error"
        run["finished_at"] = _now_iso()
        run["error"] = error
        _atomic_write_json(run_dir / "run.json", run)
        self._update_project_latest_run(project_id, run)
        return run

    def get_run(self, project_id: str, run_id: str) -> dict[str, Any] | None:
        run_dir = self.projects_dir / project_id / "runs" / run_id
        run = self._read_json(run_dir / "run.json", None)
        return run if isinstance(run, dict) else None

    def store_run_gcode(self, project_id: str, run_id: str, filename: str, data: bytes) -> str:
        run_dir = self.projects_dir / project_id / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(filename)
        p = run_dir / safe
        p.write_bytes(data)
        return str(p.relative_to(self.root))

    def store_run_artifact_json(self, project_id: str, run_id: str, name: str, obj: Any) -> str:
        run_dir = self.projects_dir / project_id / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        safe = _safe_filename(name)
        if not safe.endswith(".json"):
            safe += ".json"
        p = run_dir / safe
        _atomic_write_json(p, obj)
        return str(p.relative_to(self.root))

    def read_artifact_json(self, rel_path: str) -> Any | None:
        p = (self.root / rel_path).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def get_run_file_path(self, project_id: str, run_id: str, rel_path: str) -> Path | None:
        p = (self.root / rel_path).resolve()
        # Ensure it stays within root
        if not str(p).startswith(str(self.root.resolve())):
            return None
        if not p.exists():
            return None
        return p

    def _update_project_latest_run(self, project_id: str, run: dict[str, Any]) -> None:
        proj_dir = self.projects_dir / project_id
        meta = self._read_json(proj_dir / "project.json", None)
        if not isinstance(meta, dict):
            return
        meta["updated_at"] = _now_iso()
        meta["latest_run"] = {
            "id": run.get("id"),
            "status": run.get("status"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "error": run.get("error"),
            # keep only small summary here; full artifacts live in run folder
            "result": (
                {
                    "gcode_path": run.get("result", {}).get("gcode_path")
                    if isinstance(run.get("result"), dict)
                    else None,
                    "ncc_summary": run.get("result", {}).get("ncc_summary")
                    if isinstance(run.get("result"), dict)
                    else None,
                    "cncjob_summary": run.get("result", {}).get("cncjob_summary")
                    if isinstance(run.get("result"), dict)
                    else None,
                }
                if isinstance(run.get("result"), dict)
                else None
            ),
        }
        _atomic_write_json(proj_dir / "project.json", meta)


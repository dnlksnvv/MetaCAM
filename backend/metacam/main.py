"""
FastAPI entry: same routes as Go metacam-server + static UI.
Run from repo: cd metacam_py && PYTHONPATH=. uvicorn metacam.main:app --reload --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from metacam.api.routes import router as api_v1_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Metacam", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Needed for browser preflight (DELETE/PATCH), and for future UI.
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

_STATIC = Path(__file__).resolve().parent.parent / "web" / "static"
if _STATIC.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")

# ensure data directory exists
_DATA = Path(__file__).resolve().parent.parent / "data"
_DATA.mkdir(parents=True, exist_ok=True)

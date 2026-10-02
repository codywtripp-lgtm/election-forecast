"""Immutable dated raw snapshots: data/raw/<source>/<name>/<YYYY-MM-DD>.<ext>.gz"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
from pathlib import Path

import requests

from pipeline.config import RAW, USER_AGENT

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


def snapshot_path(source: str, name: str, ext: str, day: dt.date | None = None) -> Path:
    day = day or dt.date.today()
    return RAW / source / name / f"{day.isoformat()}.{ext}.gz"


def write_snapshot(path: Path, content: bytes) -> str:
    """Write gzip (deterministic: mtime=0) and return sha256 of the raw content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(content)
    return hashlib.sha256(content).hexdigest()


def latest_snapshot(source: str, name: str) -> Path:
    files = sorted((RAW / source / name).glob("*.gz"))
    if not files:
        raise FileNotFoundError(f"no snapshot for {source}/{name}")
    return files[-1]


def read_snapshot(path: Path) -> bytes:
    with gzip.open(path, "rb") as gz:
        return gz.read()


def fetch(url: str, **kw) -> bytes:
    r = SESSION.get(url, timeout=60, **kw)
    r.raise_for_status()
    return r.content

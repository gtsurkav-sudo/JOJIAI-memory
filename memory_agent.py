"""Utilities for reading and updating memory JSON files with file locking.

This module provides a small helper class :class:`MemoryAgent` that reads and
writes the memory JSON files stored in the repository.  Each write operation is
protected by an exclusive file lock so parallel processes do not clobber each
other's changes.

The files track four segments of memory:
    - decisions
    - logs
    - profile
    - projects

Every segment keeps a ``last_updated`` timestamp in ISO 8601 format.  When a
segment is written through :meth:`MemoryAgent.update_memory`, the timestamp is
refreshed automatically.  For list‑based segments (``decisions``, ``logs`` and
``projects``) the new entry also receives its own ``last_updated`` field.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict

import fcntl


@contextmanager
def _locked_file(path: str, mode: str):
    """Open *path* and lock it for the duration of the context."""
    with open(path, mode) as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield fh
        finally:
            fh.flush()
            os.fsync(fh.fileno())
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _iso_now() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryAgent:
    """Helper for reading and updating memory JSON files."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = base_dir or os.path.dirname(__file__)
        self.files = {
            "decisions": os.path.join(self.base_dir, "memory_decisions_v2.json"),
            "logs": os.path.join(self.base_dir, "memory_logs_v2.json"),
            "profile": os.path.join(self.base_dir, "memory_profile_v2.json"),
            "projects": os.path.join(self.base_dir, "memory_projects_v2.json"),
        }

    def _read_json(self, segment: str) -> Dict[str, Any]:
        with _locked_file(self.files[segment], "r") as fh:
            return json.load(fh)

    def _write_json(self, segment: str, data: Dict[str, Any]) -> None:
        with _locked_file(self.files[segment], "w") as fh:
            json.dump(data, fh, ensure_ascii=False)

    def update_memory(self, segment: str, entry: Dict[str, Any]) -> None:
        """Update *segment* with *entry* and refresh timestamps.

        Parameters
        ----------
        segment:
            One of ``decisions``, ``logs``, ``profile`` or ``projects``.
        entry:
            Data to merge into the segment.  For list‑based segments the entry
            is appended (or merged for projects with the same ``project_id``).
        """
        data = self._read_json(segment)
        now = _iso_now()
        data["last_updated"] = now

        if segment == "profile":
            data.setdefault("data", {}).update(entry)
            data["data"]["last_updated"] = now
        elif segment in {"decisions", "logs"}:
            entry = dict(entry)
            entry["last_updated"] = now
            data[segment].append(entry)
        elif segment == "projects":
            entry = dict(entry)
            entry["last_updated"] = now
            pid = entry.get("project_id")
            projects = data.setdefault("projects", [])
            for idx, proj in enumerate(projects):
                if proj.get("project_id") == pid:
                    projects[idx].update(entry)
                    break
            else:
                projects.append(entry)
        else:
            raise ValueError(f"Unknown segment: {segment}")

        self._write_json(segment, data)

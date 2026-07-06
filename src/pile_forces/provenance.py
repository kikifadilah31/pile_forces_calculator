"""
Run provenance (template Core 5): write run_manifest.json for reproducibility.

Captures tool version, timestamp, environment, hashed inputs, all parameters,
and the engineering standards/method used, so a result can be reproduced and
audited later.
"""

import datetime
import hashlib
import json
import os
import platform
import sys

from . import config


def sha256(path: str) -> str:
    """Return the SHA-256 hex digest of a file (streamed, 8 KiB chunks)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _dependency_versions() -> dict:
    versions = {}
    for mod in ("numpy", "pandas", "matplotlib", "typst"):
        try:
            versions[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001 — optional / best-effort provenance
            versions[mod] = "not installed"
    return versions


def write_manifest(
    out_dir: str,
    tool_version: str,
    input_files: list[str],
    params: dict,
    cli_args: dict | None = None,
) -> str:
    """Write run_manifest.json into out_dir. Returns the manifest path."""
    manifest = {
        "tool": "pile-forces",
        "tool_version": tool_version,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dependencies": _dependency_versions(),
        "inputs": {p: sha256(p) for p in input_files if os.path.isfile(p)},
        "parameters": params,
        "cli_args": cli_args or {},
        "standards": config.STANDARDS,
    }
    path = os.path.join(out_dir, "run_manifest.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return path

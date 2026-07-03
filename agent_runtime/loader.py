"""Load project data files: policies, agents, adapters, tasks, events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# Files the CLI is allowed to read.  Secrets / credential files are intentionally absent.
ALLOWED_EXTENSIONS = {".json", "", ".md", ".txt", ".jsonl", ".sample"}
DENIED_NAMES = {".env", ".env.local", ".envrc", ".secret", ".key", ".pem", ".p12", ".pfx"}


def normalize_path(path: str | os.PathLike[str]) -> str:
    """Return a forward-slash-normalized path for cross-platform comparisons."""
    return str(path).replace(os.sep, "/")


def is_safe_to_read(path: Path) -> bool:
    """Return False for obvious credential / env files."""
    name = path.name.lower()
    stem = path.stem.lower()
    if name in DENIED_NAMES:
        return False
    if stem in DENIED_NAMES:
        return False
    if name.startswith(".") and "env" in name:
        return False
    if path.suffix.lower() in {".key", ".pem", ".p12", ".pfx", ".crt", ".der"}:
        return False
    return True


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_jsonl(path: Path) -> list[Any]:
    records: list[Any] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def discover_policies(root: Path, explicit: Path | None = None) -> list[Path]:
    """Return policy file paths to load."""
    if explicit is not None:
        return [explicit]
    policies_dir = root / "policies"
    if not policies_dir.is_dir():
        return []
    return sorted(policies_dir.glob("*.sample.policy.json"))


def load_policies(root: Path, explicit: Path | None = None) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for path in discover_policies(root, explicit=explicit):
        policies.append(load_json(path))
    return policies


def load_agents(root: Path) -> dict[str, Any]:
    return load_json(root / "agents" / "agents.sample.json")


def load_adapters(root: Path) -> dict[str, Any]:
    return load_json(root / "adapters" / "adapters.sample.json")


def load_schema(root: Path, name: str) -> dict[str, Any]:
    return load_json(root / name)


def load_jsonl_files(root: Path, subdir: str, pattern: str) -> list[tuple[Path, list[Any]]]:
    results: list[tuple[Path, list[Any]]] = []
    directory = root / subdir
    if not directory.is_dir():
        return results
    for path in sorted(directory.glob(pattern)):
        if not is_safe_to_read(path):
            continue
        results.append((path, load_jsonl(path)))
    return results


def iter_text_files(root: Path) -> list[Path]:
    """Yield non-secret text files under root for public-scan style checks."""
    files: list[Path] = []
    skipped_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    for path in root.rglob("*"):
        if any(part in skipped_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if not is_safe_to_read(path):
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt", ".py", ".sample", "", ".yml", ".yaml"}:
            continue
        files.append(path)
    return files

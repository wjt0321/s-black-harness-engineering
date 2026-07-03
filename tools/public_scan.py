#!/usr/bin/env python3
"""Public repository scan for release-risk patterns.

This script is read-only and self-contained: it scans text files under the
repository root, reports potential public-release risks, and exits with a
non-zero status if anything is found. It does not access the network, execute
external commands, write files, or read credential files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from agent_runtime.loader import is_safe_to_read, normalize_path


# Detection rules use only safe string/regex literals.  No real keys are embedded.
# Regex strings are split in source so the scanner does not flag itself.
SCAN_RULES: list[dict[str, str]] = [
    {
        "id": "github-token",
        "title": "GitHub token pattern",
        "regex": "ghp_" + r"[A-Za-z0-9]{30,}|github_pat_" + r"[A-Za-z0-9_]{50,}",
    },
    {
        "id": "openai-style-key",
        "title": "OpenAI-style API key pattern",
        "regex": "sk-" + r"[A-Za-z0-9]{20,}",
    },
    {
        "id": "tavily-key",
        "title": "Tavily key pattern",
        "regex": "tvly-(dev-)?" + r"[A-Za-z0-9_-]{20,}",
    },
    {
        "id": "minimax-key",
        "title": "MiniMax key pattern",
        "regex": "mkt_" + r"[A-Za-z0-9]{20,}",
    },
    {
        "id": "generic-bearer-token",
        "title": "Bearer token pattern",
        "regex": "Bearer" + r"\s+[A-Za-z0-9._~+/-]{30,}",
    },
    {
        "id": "windows-absolute-path",
        "title": "Windows absolute path trace",
        "regex": r"(?<![A-Za-z])[A-Za-z]:[\\/][A-Za-z0-9_.\\/-]+",
    },
    {
        "id": "unix-home-path",
        "title": "Unix home directory path trace",
        "regex": "/(?:home|Users)/" + r"[A-Za-z0-9_.-]+/",
    },
]

SKIPPED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    ".tox",
    "build",
    "dist",
}

SCAN_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".jsonl",
    ".yml",
    ".yaml",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
}


def iter_text_files(root: Path) -> list[Path]:
    """Return safe, non-secret text files under root."""
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIPPED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if not is_safe_to_read(path):
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        files.append(path)
    return files


def _line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_file(path: Path, root: Path) -> list[tuple[str, int, str, str]]:
    """Scan a single file and return (relative_path, line, rule_id, title)."""
    findings: list[tuple[str, int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    rel = normalize_path(path.relative_to(root))
    for rule in SCAN_RULES:
        compiled = re.compile(rule["regex"])
        for match in compiled.finditer(text):
            line_no = _line_number(text, match.start())
            findings.append((rel, line_no, rule["id"], rule["title"]))
    return findings


def scan(root: Path | None = None) -> tuple[list[tuple[str, int, str, str]], list[str]]:
    """Scan the repository and return (findings, summary_lines)."""
    if root is None:
        root = Path.cwd()
    findings: list[tuple[str, int, str, str]] = []
    for path in iter_text_files(root):
        findings.extend(scan_file(path, root))

    lines: list[str] = []
    for rel, line_no, rule_id, title in findings:
        lines.append(f"{rel}:{line_no} {rule_id}: {title}")
    return findings, lines


def main(argv: list[str] | None = None) -> int:
    root = Path.cwd()
    findings, lines = scan(root)
    for line in lines:
        print(line)

    if findings:
        return 1
    print("OK public scan")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

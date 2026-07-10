"""Read-only project documentation context recovery helper.

Provides a compact, deterministic summary to help new sessions quickly
re-establish project state without reading all docs or using an LLM.

The command does not access the network, read credential files, or execute
external programs. It only reads safe markdown files from the project root.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import is_safe_to_read


@dataclass
class DocsContextResult:
    """Result of a docs context recovery query."""

    status: str
    milestone: dict[str, Any] = field(default_factory=dict)
    current_stage: dict[str, Any] = field(default_factory=dict)
    recommended: list[dict[str, Any]] = field(default_factory=list)
    next_design_entry: dict[str, Any] = field(default_factory=dict)
    docs_summary: dict[str, Any] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "milestone": self.milestone,
            "current_stage": self.current_stage,
            "recommended": self.recommended,
            "next_design_entry": self.next_design_entry,
            "docs_summary": self.docs_summary,
        }
        if self.findings:
            d["findings"] = self.findings
        if self.next_action:
            d["next_action"] = self.next_action
        return d


def _read_text(root: Path, rel_path: str) -> str | None:
    """Return the text of a safe project file, or None if unavailable."""
    path = root / rel_path
    if not path.is_file() or not is_safe_to_read(path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def _extract_milestone(text: str | None) -> dict[str, Any]:
    """Extract milestone tag and commit hash from README-style text."""
    milestone: dict[str, Any] = {}
    if not text:
        return milestone
    tag_match = re.search(r"(v\d+\.\d+\.\d+-[a-zA-Z0-9._-]+)", text)
    if tag_match:
        milestone["tag"] = tag_match.group(1)
    commit_match = re.search(r"commit `([0-9a-f]{7,40})`", text)
    if commit_match:
        milestone["commit"] = commit_match.group(1)
    return milestone


def _extract_current_stage(text: str | None) -> dict[str, Any]:
    """Extract the latest in-progress or completed stage from README text.

    README uses emoji markers: ✅ completed, 🟡 in progress, ⚪ future.
    """
    if not text:
        return {}
    stages: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"[-*]\s*([🟡✅⚪])\s*(Stage\s+[\d.]+)\s*[—-]\s*(.+)", line)
        if match:
            emoji, stage, description = match.groups()
            status = {"🟡": "in_progress", "✅": "completed", "⚪": "future"}.get(emoji, "unknown")
            stages.append(
                {
                    "stage": stage,
                    "status": status,
                    "description": description.strip(),
                }
            )
    if not stages:
        return {}
    # Prefer the last in-progress stage, otherwise the last completed one.
    for entry in reversed(stages):
        if entry["status"] == "in_progress":
            return entry
    return stages[-1]


def _extract_index_top_docs(text: str | None) -> list[dict[str, Any]]:
    """Extract the 'current most important docs' list from docs/00-index.md."""
    docs: list[dict[str, Any]] = []
    if not text:
        return docs
    in_section = False
    for line in text.splitlines():
        if "当前最重要的几份文档" in line:
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("#"):
                break
            match = re.match(r"\d+\.\s+`([^`]+)`(?::\s*(.+))?", line.strip())
            if match:
                path = match.group(1)
                # Normalize bare doc filenames to root-relative docs/ paths.
                if not path.startswith(("docs/", "tasks/", "README")):
                    path = f"docs/{path}"
                note = (match.group(2) or "").strip()
                docs.append(
                    {
                        "path": path,
                        "reason": note or "index-top-doc",
                    }
                )
            if len(docs) >= 5:
                break
    return docs


def _latest_handoff(root: Path) -> str | None:
    """Return the relative path of the newest tasks/handoff-*.md file."""
    handoffs = sorted((root / "tasks").glob("handoff-*.md"))
    for path in reversed(handoffs):
        if is_safe_to_read(path):
            return str(path.relative_to(root)).replace("\\", "/")
    return None


def _docs_summary(root: Path) -> dict[str, Any]:
    """Return a safe summary of the docs directory."""
    docs_dir = root / "docs"
    files = [p for p in docs_dir.glob("*.md") if is_safe_to_read(p)]
    numbers = []
    for p in files:
        m = re.match(r"(\d+)-", p.name)
        if m:
            numbers.append(int(m.group(1)))
    numbered_names = sorted([p.name for p in files if re.match(r"\d+-", p.name)])
    return {
        "total_docs": len(files),
        "numbered_range": f"{min(numbers)}-{max(numbers)}" if numbers else "none",
        "latest_docs": numbered_names[-3:] if len(numbered_names) >= 3 else numbered_names,
    }


def _extract_next_design_entry(roadmap_text: str | None) -> dict[str, Any]:
    """Return the next high-priority design entry from the roadmap.

    The roadmap marks Stage 10+ as the orchestration hub backend work.
    We pick the first Stage >= 10 that has a clear deliverable doc reference.
    """
    if not roadmap_text:
        return {}
    # Find all Stage headings and the following deliverable bullet.
    for match in re.finditer(r"##\s*Stage\s+(\d+)\s*[—-]\s*(.+?)\n", roadmap_text):
        stage_num = int(match.group(1))
        if stage_num < 10:
            continue
        title = match.group(2).strip()
        section_start = match.end()
        section_end = roadmap_text.find("\n## ", section_start)
        if section_end == -1:
            section_end = len(roadmap_text)
        section = roadmap_text[section_start:section_end]
        # Look for a docs/NN-... deliverable reference.
        doc_match = re.search(r"`((?:docs|decisions)/[^`]+)`", section)
        entry_doc = doc_match.group(1) if doc_match else None
        # Also collect concise todo bullets for context.
        todos = [m.group(1).strip("- ") for m in re.finditer(r"[-*]\s*(.+)", section) if m.group(1).strip().startswith(("补", "定义", "设计", "明确", "调整"))]
        return {
            "stage": f"Stage {stage_num}",
            "title": title,
            "path": entry_doc,
            "focus": todos[:3] if todos else [],
        }
    return {}


def get_docs_context(root: Path) -> DocsContextResult:
    """Build a compact project context recovery summary.

    Reads only safe markdown files from the project root. No network access,
    no credential files, no LLM generation.
    """
    root = root.resolve()
    findings: list[str] = []

    readme = _read_text(root, "README.md")
    index = _read_text(root, "docs/00-index.md")
    roadmap = _read_text(root, "docs/02-roadmap.md")
    progress = _read_text(root, "tasks/progress.md")

    if readme is None:
        findings.append("README.md not available; milestone and stage info may be incomplete.")
    if index is None:
        findings.append("docs/00-index.md not available; recommended doc list may be incomplete.")

    milestone = _extract_milestone(readme)
    current_stage = _extract_current_stage(readme)
    next_design_entry = _extract_next_design_entry(roadmap)

    # Build recommended reading list.
    recommended: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(path: str, reason: str) -> None:
        if path not in seen:
            recommended.append({"path": path, "reason": reason})
            seen.add(path)

    # 1. Always-start-here docs.
    add("docs/00-index.md", "context-root")
    add("docs/02-roadmap.md", "roadmap")
    add("README.md", "project-overview")
    add("docs/10-cli-poc-usage.md", "cli-usage")

    # 2. Session continuity: latest handoff and progress ledger.
    handoff = _latest_handoff(root)
    if handoff:
        add(handoff, "latest-handoff")
    if progress is not None:
        add("tasks/progress.md", "progress-ledger")

    # 3. Latest release notes for continuity.
    release_note_docs = []
    for name in (root / "docs").glob("*.md"):
        if not is_safe_to_read(name):
            continue
        if re.search(r"release-notes", name.name):
            num_match = re.match(r"(\d+)-", name.name)
            if num_match:
                release_note_docs.append((int(num_match.group(1)), name.name))
    if release_note_docs:
        release_note_docs.sort(key=lambda x: x[0])
        add(f"docs/{release_note_docs[-1][1]}", "latest-release-notes")

    # 4. Index top docs.
    for doc in _extract_index_top_docs(index):
        add(doc["path"], doc["reason"])

    # Cap to a recoverable size.
    recommended = recommended[:10]

    docs_summary = _docs_summary(root)
    if handoff:
        docs_summary["latest_handoff"] = handoff

    status = "pass" if not findings else "warn"
    next_action = (
        "Read the recommended docs in order to recover project context."
        if status == "pass"
        else "Some context sources are missing; review findings before proceeding."
    )

    return DocsContextResult(
        status=status,
        milestone=milestone,
        current_stage=current_stage,
        recommended=recommended,
        next_design_entry=next_design_entry,
        docs_summary=docs_summary,
        findings=findings,
        next_action=next_action,
    )

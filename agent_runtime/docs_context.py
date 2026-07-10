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


def _parse_stage_digest(text: str | None) -> dict[str, Any] | None:
    """Parse the compact stage digest file if present.

    Returns a dict with milestone, current_stage, recent_completed,
    recovery_order, next_design_entry. Returns None if the file does not look
    like a valid stage digest.

    Parsing is line-based and tolerant to markdown variations; it only relies
    on section headings and list markers defined by the digest template.
    """
    if not text:
        return None
    if "当前稳定基线" not in text or "当前阶段" not in text:
        return None

    # Split into sections by '## ' headings.
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current_heading = line[3:].strip()
            sections[current_heading] = []
        elif current_heading is not None:
            sections[current_heading].append(line)

    def section_lines(prefix: str) -> list[str]:
        for heading, lines in sections.items():
            if heading.startswith(prefix):
                return lines
        return []

    digest: dict[str, Any] = {}

    baseline_lines = section_lines("当前稳定基线")
    milestone: dict[str, Any] = {}
    for line in baseline_lines:
        tag_match = re.search(r"[里里]程碑[：:]\s*`?([^`\n]+)`?", line)
        if tag_match:
            milestone["tag"] = tag_match.group(1).strip()
        commit_match = re.search(r"commit[：:]\s*`?([0-9a-f]{7,40})`?", line)
        if commit_match:
            milestone["commit"] = commit_match.group(1)
    digest["milestone"] = milestone

    stage_lines = section_lines("当前阶段")
    for line in stage_lines:
        stage_match = re.search(r"\*\*([^*]*Stage\s+[\d.]+[^*]*)\*\*", line)
        if stage_match:
            stage_text = stage_match.group(1).strip()
            m = re.match(r"(Stage\s+[\d.]+)\s*[—-]\s*(.+)", stage_text)
            if m:
                digest["current_stage"] = {
                    "stage": m.group(1).strip(),
                    "status": "in_progress",
                    "description": m.group(2).strip(),
                }
            else:
                digest["current_stage"] = {
                    "stage": stage_text,
                    "status": "in_progress",
                    "description": "",
                }
            break

    recent: list[dict[str, Any]] = []
    for line in section_lines("最近完成的"):
        match = re.search(r"\*\*(Stage\s+[\d.]+)\*\*\s*[—-]\s*(.+)", line)
        if match:
            recent.append(
                {
                    "stage": match.group(1).strip(),
                    "description": match.group(2).strip(),
                }
            )
    digest["recent_completed"] = recent

    recovery_order: list[dict[str, Any]] = []
    for line in section_lines("推荐恢复顺序"):
        stripped = line.strip()
        if not stripped:
            continue
        # Extract backtick-wrapped path if present; otherwise take the first token.
        entry_match = re.search(r"`([^`]+)`", stripped)
        if entry_match:
            entry = entry_match.group(1).strip()
            purpose = stripped.split("`", 2)[-1].strip()
            # Drop leading dash/em-dash and spaces.
            purpose = re.sub(r"^[\s—-]+", "", purpose)
        else:
            match = re.match(r"\d+\.\s+(\S+)\s*[—-]\s*(.+)", stripped)
            if not match:
                continue
            entry = match.group(1).strip()
            purpose = match.group(2).strip()
        recovery_order.append({"entry": entry, "purpose": purpose})
    digest["recovery_order"] = recovery_order

    next_lines = section_lines("下一步推荐入口")
    next_entry: dict[str, Any] = {}
    for line in next_lines:
        stage_match = re.search(r"\*\*([^*]*Stage\s+\d+[^*]*)\*\*", line)
        if stage_match:
            stage_text = stage_match.group(1).strip()
            m = re.match(r"(Stage\s+\d+)\s*[—-]\s*(.+)", stage_text)
            if m:
                next_entry["stage"] = m.group(1).strip()
                next_entry["title"] = m.group(2).strip()
            else:
                next_entry["stage"] = stage_text
        doc_match = re.search(r"入口文档[：:]\s*`([^`]+)`", line)
        if doc_match:
            next_entry["path"] = doc_match.group(1)
        focus_match = re.search(r"重点[：:]\s*(.+)", line)
        if focus_match:
            next_entry["focus"] = [focus_match.group(1).strip()]
    digest["next_design_entry"] = next_entry

    return digest


def get_docs_context(root: Path) -> DocsContextResult:
    """Build a compact project context recovery summary.

    Reads only safe markdown files from the project root. No network access,
    no credential files, no LLM generation.

    If ``docs/000-stage-digest.md`` exists, its compact fields take priority for
    milestone, current stage, next design entry and recovery order. Missing or
    partial digest values fall back to parsing README / index / roadmap.
    """
    root = root.resolve()
    findings: list[str] = []

    digest_text = _read_text(root, "docs/000-stage-digest.md")
    digest = _parse_stage_digest(digest_text)
    digest_available = digest is not None

    readme = _read_text(root, "README.md")
    index = _read_text(root, "docs/00-index.md")
    roadmap = _read_text(root, "docs/02-roadmap.md")
    progress = _read_text(root, "tasks/progress.md")

    if digest_available:
        milestone = digest.get("milestone", {})
        current_stage = digest.get("current_stage", {})
        next_design_entry = digest.get("next_design_entry", {})
        recovery_order = digest.get("recovery_order", [])
    else:
        milestone = _extract_milestone(readme)
        current_stage = _extract_current_stage(readme)
        next_design_entry = _extract_next_design_entry(roadmap)
        recovery_order = []

    if not milestone:
        findings.append("Milestone info not available; check README.md or docs/000-stage-digest.md.")
    if not current_stage:
        findings.append("Current stage info not available; check README.md or docs/000-stage-digest.md.")

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

    # 2. Digest-driven recovery order (if present).
    if digest_available:
        add("docs/000-stage-digest.md", "stage-digest")
        for entry in recovery_order:
            entry_path = entry.get("entry", "")
            # Skip non-concrete entries (commands, wildcards, explanations).
            if not entry_path:
                continue
            if " " in entry_path or "*" in entry_path or entry_path.endswith(".py"):
                continue
            if entry_path == "docs context":
                continue
            # Normalize bare filenames to docs/ paths.
            if not entry_path.startswith(("docs/", "tasks/", "README")):
                entry_path = f"docs/{entry_path}"
            # Skip placeholder digest entries that do not exist as files
            # (e.g. "tasks/handoff-latest.md" standing for the latest handoff).
            if not (root / entry_path).is_file():
                continue
            add(entry_path, entry.get("purpose") or "digest-recovery-order")

    # 3. Session continuity: latest handoff and progress ledger.
    handoff = _latest_handoff(root)
    if handoff:
        add(handoff, "latest-handoff")
    if progress is not None:
        add("tasks/progress.md", "progress-ledger")

    # 4. Latest release notes for continuity.
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

    # 5. Index top docs (fallback enrichment).
    for doc in _extract_index_top_docs(index):
        add(doc["path"], doc["reason"])

    # Cap to a recoverable size.
    recommended = recommended[:10]

    docs_summary = _docs_summary(root)
    docs_summary["digest_available"] = digest_available
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

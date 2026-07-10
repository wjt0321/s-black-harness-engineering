"""Tests for docs context recovery read model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main
from agent_runtime.docs_context import get_docs_context


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a minimal fake project root with context sources."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    (fake_root / "docs").mkdir()
    (fake_root / "tasks").mkdir()
    return fake_root


def _write_readme(fake_root: Path) -> None:
    readme = fake_root / "README.md"
    readme.write_text(
        "# Test Project\n\n"
        "Current milestone is `v0.99.0-test` (commit `deadbeef`).\n\n"
        "## Current progress\n\n"
        "- ✅ Stage 0 — Project skeleton\n"
        "- 🟡 Stage 5 — Runtime CLI\n"
        "- ⚪ Stage 10 — Future work\n",
        encoding="utf-8",
    )


def _write_index(fake_root: Path) -> None:
    index = fake_root / "docs" / "00-index.md"
    index.write_text(
        "# Index\n\n"
        "## 当前最重要的几份文档\n\n"
        "1. `01-vision.md`: project vision\n"
        "2. `10-usage.md`: cli usage\n"
        "3. `21-boundaries.md`: write boundaries\n",
        encoding="utf-8",
    )


def _write_roadmap(fake_root: Path) -> None:
    roadmap = fake_root / "docs" / "02-roadmap.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "## Stage 0 — Done\n\n"
        "Done.\n\n"
        "## Stage 10 — Adapter Interface（下一步高优先级）\n\n"
        "要做的事：\n\n"
        "- 定义 adapter 分类\n"
        "- 定义统一 metadata\n\n"
        "主要交付物：\n\n"
        "- `docs/48-adapter-interface.md`\n",
        encoding="utf-8",
    )


def _write_progress(fake_root: Path) -> None:
    progress = fake_root / "tasks" / "progress.md"
    progress.write_text("# Progress\n\n- Done something.\n", encoding="utf-8")


def _write_handoff(fake_root: Path) -> None:
    handoff = fake_root / "tasks" / "handoff-2026-07-10.md"
    handoff.write_text("# Handoff\n\nContext.\n", encoding="utf-8")


def _write_extra_docs(fake_root: Path) -> None:
    for name in ["01-vision.md", "10-usage.md", "21-boundaries.md", "48-adapter-interface.md"]:
        (fake_root / "docs" / name).write_text(f"# {name}\n", encoding="utf-8")
    # Older and newer release notes to test latest selection.
    (fake_root / "docs" / "11-release-notes-v0.1.md").write_text("# v0.1\n", encoding="utf-8")
    (fake_root / "docs" / "55-release-notes.md").write_text("# later\n", encoding="utf-8")


def test_docs_context_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)

    code = main(["--root", str(fake_root), "docs", "context", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["milestone"]["tag"] == "v0.99.0-test"
    assert result["milestone"]["commit"] == "deadbeef"
    assert result["current_stage"]["stage"] == "Stage 5"
    assert result["current_stage"]["status"] == "in_progress"
    assert result["next_design_entry"]["stage"] == "Stage 10"
    assert result["next_design_entry"]["path"] == "docs/48-adapter-interface.md"

    paths = [d["path"] for d in result["recommended"]]
    assert "docs/00-index.md" in paths
    assert "docs/02-roadmap.md" in paths
    assert "README.md" in paths
    assert "docs/10-usage.md" in paths
    assert "docs/55-release-notes.md" in paths
    assert "tasks/progress.md" in paths
    assert "tasks/handoff-2026-07-10.md" in paths

    summary = result["docs_summary"]
    assert summary["total_docs"] == 8
    assert summary["latest_docs"][-1] == "55-release-notes.md"
    assert summary["latest_handoff"] == "tasks/handoff-2026-07-10.md"


def test_docs_context_human_output_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)

    code = main(["--root", str(fake_root), "docs", "context"])
    captured = capsys.readouterr()
    assert code == 0
    assert "DOCS CONTEXT" in captured.out
    assert "v0.99.0-test" in captured.out
    assert "Stage 5" in captured.out
    assert "docs/48-adapter-interface.md" in captured.out
    # Ensure no full roadmap text is dumped.
    assert "Done." not in captured.out


def test_docs_context_missing_sources_warns(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    # Only create empty README without useful markers.
    (fake_root / "README.md").write_text("# Empty\n", encoding="utf-8")

    code = main(["--root", str(fake_root), "docs", "context", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "warn"
    assert result["findings"]


def test_docs_context_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)

    before = {p: p.read_bytes() for p in fake_root.rglob("*") if p.is_file()}
    code = main(["--root", str(fake_root), "docs", "context"])
    assert code == 0
    for p, content in before.items():
        assert p.read_bytes() == content


def test_get_docs_context_module_api(tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)

    result = get_docs_context(fake_root)
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["milestone"]["tag"] == "v0.99.0-test"
    assert d["current_stage"]["stage"] == "Stage 5"


def _write_stage_digest(fake_root: Path) -> None:
    digest = fake_root / "docs" / "72-stage-digest.md"
    digest.write_text(
        "# Stage Digest\n\n"
        "## 当前稳定基线\n\n"
        "- 里程碑：`v0.99.0-test-digest`\n"
        "- 冻结 commit：`c0ffee0`\n\n"
        "## 当前阶段\n\n"
        "- **Stage 9.9 — Digest Recovery Model**\n\n"
        "## 最近完成的 3 个阶段/里程碑\n\n"
        "1. **Stage 9.8** — Previous step\n"
        "2. **Stage 9.7** — Earlier step\n\n"
        "## 推荐恢复顺序\n\n"
        "1. `docs/72-stage-digest.md` — digest summary\n"
        "2. `docs/02-roadmap.md` — roadmap view\n"
        "3. `docs/00-index.md` — index\n\n"
        "## 下一步推荐入口\n\n"
        "- **Stage 20 — Future Design**（下一步）\n"
        "- 入口文档：`docs/99-future.md`\n"
        "- 重点：future work\n",
        encoding="utf-8",
    )


def test_docs_context_uses_stage_digest_when_present(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)
    _write_stage_digest(fake_root)
    (fake_root / "docs" / "99-future.md").write_text("# future\n", encoding="utf-8")

    code = main(["--root", str(fake_root), "docs", "context", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)

    # Digest values override README/roadmap values.
    assert result["milestone"]["tag"] == "v0.99.0-test-digest"
    assert result["milestone"]["commit"] == "c0ffee0"
    assert result["current_stage"]["stage"] == "Stage 9.9"
    assert result["current_stage"]["description"] == "Digest Recovery Model"
    assert result["next_design_entry"]["stage"] == "Stage 20"
    assert result["next_design_entry"]["path"] == "docs/99-future.md"

    # Digest is in recommended list.
    paths = [d["path"] for d in result["recommended"]]
    assert "docs/72-stage-digest.md" in paths
    assert result["docs_summary"]["digest_available"] is True


def test_docs_context_falls_back_when_digest_missing(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)

    code = main(["--root", str(fake_root), "docs", "context", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)

    # Fallback to README/roadmap parsing.
    assert result["milestone"]["tag"] == "v0.99.0-test"
    assert result["current_stage"]["stage"] == "Stage 5"
    assert result["next_design_entry"]["stage"] == "Stage 10"
    assert result["docs_summary"]["digest_available"] is False

    # No digest in recommended list.
    paths = [d["path"] for d in result["recommended"]]
    assert "docs/72-stage-digest.md" not in paths


def test_docs_context_digest_skips_nonexistent_entries(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_readme(fake_root)
    _write_index(fake_root)
    _write_roadmap(fake_root)
    _write_progress(fake_root)
    _write_handoff(fake_root)
    _write_extra_docs(fake_root)
    digest = fake_root / "docs" / "72-stage-digest.md"
    digest.write_text(
        "# Stage Digest\n\n"
        "## 当前稳定基线\n\n"
        "- 里程碑：`v0.99.0-test`\n"
        "- 冻结 commit：`c0ffee0`\n\n"
        "## 当前阶段\n\n"
        "- **Stage 9.9 — Test**\n\n"
        "## 推荐恢复顺序\n\n"
        "1. `docs/72-stage-digest.md` — digest\n"
        "2. `docs/99-missing.md` — missing placeholder\n"
        "3. `python -m agent_runtime.cli docs context` — command\n"
        "4. `docs/02-roadmap.md` — roadmap\n\n"
        "## 下一步推荐入口\n\n"
        "- **Stage 10 — Future**\n"
        "- 入口文档：`docs/48-adapter-interface.md`\n",
        encoding="utf-8",
    )

    code = main(["--root", str(fake_root), "docs", "context", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    paths = [d["path"] for d in result["recommended"]]
    assert "docs/72-stage-digest.md" in paths
    assert "docs/02-roadmap.md" in paths
    assert "docs/99-missing.md" not in paths
    assert "python -m agent_runtime.cli docs context" not in paths

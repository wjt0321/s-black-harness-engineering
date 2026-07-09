"""Tests for orchestration route preview read-only command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with adapter registry and schema."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    schema_src = ROOT / "adapters" / "execution-envelope.schema.json"
    schema_dst = fake_root / "adapters" / "execution-envelope.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
    return fake_root


def _write_adapters(fake_root: Path) -> None:
    """Write a minimal adapter registry with multiple capabilities."""
    adapters_file = fake_root / "adapters" / "adapters.sample.json"
    adapters_file.parent.mkdir(parents=True, exist_ok=True)
    registry = {
        "version": 1,
        "description": "Test adapter registry",
        "adapters": [
            {
                "id": "local-shell",
                "name": "Local Shell",
                "kind": "shell",
                "description": "Local shell commands.",
                "enabled": True,
                "capabilities": ["local_command", "test", "git_status"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {
                    "type": "object",
                    "required": ["command"],
                    "properties": {"command": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check"],
            },
            {
                "id": "github-cli",
                "name": "GitHub CLI",
                "kind": "github",
                "description": "GitHub operations.",
                "enabled": True,
                "capabilities": ["repo_create", "issue_ops", "git_push", "remote_status"],
                "risk_level": "external",
                "requires_approval": True,
                "input_schema": {
                    "type": "object",
                    "required": ["operation"],
                    "properties": {"operation": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check", "secret_scan", "user_approval"],
            },
            {
                "id": "disabled-adapter",
                "name": "Disabled Adapter",
                "kind": "test",
                "description": "Should be ignored.",
                "enabled": False,
                "capabilities": ["local_command"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
        ],
    }
    adapters_file.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


def _write_task(fake_root: Path, status: str = "running") -> None:
    """Write a single task to the ledger."""
    tasks_file = fake_root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260709-001",
        "title": "Route preview test task",
        "status": status,
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "git_push",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def test_route_preview_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["requested_capability"] == "git_push"
    assert result["selected_adapter_id"] == "github-cli"
    assert result["capability"] == "git_push"
    assert result["operation"] == "git_push"
    assert result["requested_mode"] == "dry-run"
    assert result["selected_mode"] == "dry-run"
    assert result["risk_level"] == "external"
    assert result["requires_approval"] is True
    assert result["requires_dry_run"] is True
    assert result["routing_reason"]
    assert "preflight_checks" in result["constraints"]


def test_route_preview_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ROUTE PREVIEW" in captured.out
    assert "github-cli" in captured.out
    assert "git_push" in captured.out
    assert "external" in captured.out


def test_route_preview_with_adapter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_status",
        "--adapter", "local-shell",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "local-shell"
    assert result["risk_level"] == "local"
    assert result["requires_approval"] is False
    assert result["requires_dry_run"] is False


def test_route_preview_adapter_not_supports_capability(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--adapter", "local-shell",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None
    assert any("github-cli" in fc["adapter_id"] for fc in result["fallback_candidates"])


def test_route_preview_no_matching_adapter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "unknown_capability",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "unknown_capability" in result["routing_reason"]


def test_route_preview_task_id_context(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_task(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--task-id", "task-20260709-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["task_id"] == "task-20260709-001"
    assert "task_context" in result["constraints"]


def test_route_preview_commit_mode_forced_to_dry_run(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--mode", "commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["requested_mode"] == "commit"
    assert result["selected_mode"] == "dry-run"
    assert result["requires_dry_run"] is True


def test_route_preview_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    adapters_before = (fake_root / "adapters" / "adapters.sample.json").read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--json",
    ])
    assert code == 0
    assert (fake_root / "adapters" / "adapters.sample.json").read_bytes() == adapters_before

"""Tests for orchestration preflight read-only handoff command."""

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
    """Write a minimal adapter registry for routing/preflight tests."""
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
                "capabilities": ["local_command", "git_status", "read_file"],
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
                "capabilities": ["git_push", "issue_ops"],
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
                "id": "file-reader",
                "name": "File Reader",
                "kind": "shell",
                "description": "File reader requiring target.",
                "enabled": True,
                "capabilities": ["file_read"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {
                    "type": "object",
                    "required": ["operation", "target"],
                    "properties": {
                        "operation": {"type": "string"},
                        "target": {"type": "string"},
                    },
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check"],
            },
        ],
    }
    adapters_file.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


def _write_policy(fake_root: Path) -> None:
    """Write a minimal policy with one blocking command rule."""
    policies_dir = fake_root / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    policy = {
        "version": 1,
        "name": "test-policy",
        "command_rules": [
            {
                "id": "block-rm",
                "title": "Block recursive delete",
                "severity": "block",
                "action": "deny",
                "regex": r"\brm\s+-rf\b",
                "enabled": True,
                "message": "Recursive delete is blocked by test policy.",
            }
        ],
    }
    (policies_dir / "test.sample.policy.json").write_text(
        json.dumps(policy, ensure_ascii=False), encoding="utf-8"
    )


def _write_task(fake_root: Path) -> None:
    """Write a single task to the ledger."""
    tasks_file = fake_root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260709-001",
        "title": "Preflight test task",
        "status": "running",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "read_file",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def test_preflight_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["requested_capability"] == "read_file"
    assert result["requested_mode"] == "dry-run"
    assert result["effective_mode"] == "dry-run"
    assert result["route"]["selected_adapter_id"] == "local-shell"
    assert result["route"]["operation"] == "read_file"
    assert result["route"]["risk_level"] == "local"
    assert result["guardrail"]["status"] == "pass"
    assert result["requires_approval"] is False
    assert result["requires_dry_run"] is False


def test_preflight_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PREFLIGHT" in captured.out
    assert "read_file" in captured.out
    assert "local-shell" in captured.out
    assert "effective_mode=dry-run" in captured.out


def test_preflight_route_blocked_skips_guardrail(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "git_push",
        "--adapter", "local-shell",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["route"]["selected_adapter_id"] is None
    assert result["guardrail"]["status"] is None
    assert result["effective_mode"] == "dry-run"


def test_preflight_missing_operation(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "local_command",
        "--adapter", "local-shell",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "operation" in result["next_action"].lower()


def test_preflight_missing_target(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "file_read",
        "--adapter", "file-reader",
        "--operation", "file_read",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "target" in result["next_action"].lower()


def test_preflight_local_commit_allowed(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--mode", "commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["requested_mode"] == "commit"
    assert result["selected_mode"] == "commit"
    assert result["effective_mode"] == "commit"
    assert result["requires_approval"] is False


def test_preflight_external_commit_downgrade(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "git_push",
        "--operation", "git_push",
        "--target", "origin/main",
        "--mode", "commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    assert result["requested_mode"] == "commit"
    assert result["selected_mode"] == "dry-run"
    assert result["effective_mode"] == "dry-run"
    assert result["requires_approval"] is True
    assert result["requires_dry_run"] is True
    assert result["guardrail"]["status"] == "needs_approval"
    assert result["guardrail"]["finding_count"] >= 1


def test_preflight_guardrail_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_policy(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "local_command",
        "--adapter", "local-shell",
        "--operation", "rm -rf /tmp/x",
        "--target", "/tmp/x",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["guardrail"]["status"] == "blocked"
    assert any(f["rule_id"] == "block-rm" for f in result["guardrail"]["blocking_findings"])
    assert result["effective_mode"] == "dry-run"


def test_preflight_task_id_context(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_task(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--task-id", "task-20260709-001",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["task_id"] == "task-20260709-001"
    assert "task_context" in result["constraints"]


def test_preflight_readonly(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_task(fake_root)
    ledger_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--task-id", "task-20260709-001",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == ledger_before

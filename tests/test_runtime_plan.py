"""Tests for runtime plan command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from jsonschema import validate

from agent_runtime.cli import main
from agent_runtime.loader import load_schema


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the sample files needed for planning."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "adapters/adapters.sample.json",
        "adapters/execution-envelope.schema.json",
        "agents/agents.sample.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _write_tasks(
    root: Path,
    status: str,
    task_id: str = "task-20260703-001",
) -> Path:
    """Write a tasks.jsonl with a single task in the given status."""
    tasks_file = root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": task_id,
        "title": "Runtime plan test task",
        "status": status,
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")
    return tasks_file


def _write_events(root: Path, task_id: str = "task-20260703-001") -> Path:
    """Write a minimal events.jsonl for the test task."""
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "evt-20260703-001",
        "task_id": task_id,
        "timestamp": "2026-07-03T10:00:00+08:00",
        "actor": "test",
        "event_type": "created",
        "message": "Test task created.",
    }
    events_file.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return events_file


def test_runtime_plan_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["task_status"] == "running"

    request = result["request_draft"]
    assert request["adapter_id"] == "shell-local"
    assert request["operation"] == "read_file"
    assert request["target"] == "docs/06-adapter-layer.md"
    assert request["risk_level"] == "local"
    assert request["requires_approval"] is False
    assert request["preflight_status"] == "pass"

    assert result["approval_draft"] is None
    assert result["event_draft"] is None


def test_runtime_plan_needs_approval(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    assert result["task_status"] == "running"

    request = result["request_draft"]
    assert request["adapter_id"] == "github-cli"
    assert request["operation"] == "git_push"
    assert request["requires_approval"] is True
    assert request["preflight_status"] == "needs_approval"

    approval = result["approval_draft"]
    assert approval is not None
    assert approval["status"] == "pending"
    assert approval["request_id"] == request["request_id"]

    event = result["event_draft"]
    assert event is not None
    assert event["event_type"] == "approval_requested"
    assert event["approval_id"] == approval["approval_id"]
    assert event["adapter_id"] == "github-cli"
    assert event["operation"] == "git_push"


def test_runtime_plan_terminal_task_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["task_status"] == "finished"
    assert result["request_draft"] is None
    assert result["approval_draft"] is None
    assert result["event_draft"] is None
    assert any(f["rule_id"] == "task-terminal" for f in result["findings"])
    assert "terminal" in result["next_action"].lower()


def test_runtime_plan_missing_task(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-999",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "task-not-found" for f in result["findings"])


def test_runtime_plan_unknown_adapter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "nonexistent-adapter",
        "--operation", "foo",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "adapter-not-found" for f in result["findings"])


def test_runtime_plan_json_sanitizes_payload(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    text = captured.out.lower()
    assert "\"input\"" not in text
    assert "decision_ref" not in text
    assert "raw_ref" not in text


def test_runtime_plan_human_output(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "request_draft:" in captured.out
    assert "task_id=" in captured.out
    assert "preflight=pass" in captured.out


def test_runtime_plan_does_not_write_ledger(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(fake_root, "running")
    events_file = _write_events(fake_root)

    tasks_before = tasks_file.read_bytes()
    events_before = events_file.read_bytes()

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
    ])
    assert code == 0
    assert tasks_file.read_bytes() == tasks_before
    assert events_file.read_bytes() == events_before


def test_runtime_plan_uses_agent_profile(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "--agent", "orchestrator",
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["request_draft"]["policy_profile"] == "s-black"
    rule_ids = {f["rule_id"] for f in result["findings"]}
    assert "github-publish-preflight" in rule_ids
    assert "lark-send-target-confirmed" not in rule_ids


def test_runtime_plan_explicit_tasks_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    custom_tasks = fake_root / "custom" / "tasks.jsonl"
    custom_tasks.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260703-001",
        "title": "Custom ledger task",
        "status": "running",
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    custom_tasks.write_text(json.dumps(task) + "\n", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--tasks-file", str(custom_tasks),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["task_status"] == "running"


def _envelope_schema(root: Path) -> dict:
    return load_schema(root, "adapters/execution-envelope.schema.json")


def test_runtime_plan_draft_json_pass_validates_schema(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--draft-json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["task_status"] == "running"

    envelope = result["envelope_draft"]
    assert envelope is not None
    assert envelope["version"] == 1
    schema = _envelope_schema(fake_root)
    validate(instance=envelope, schema=schema)

    artifacts = envelope["artifacts"]
    request = next(a for a in artifacts if a["artifact_type"] == "adapter_request")
    assert request["adapter_id"] == "shell-local"
    assert request["operation"] == "read_file"
    assert request["context"]["dry_run"] is True
    assert not any(a["artifact_type"] == "approval_record" for a in artifacts)


def test_runtime_plan_draft_json_needs_approval_includes_artifacts(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--draft-json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"

    envelope = result["envelope_draft"]
    assert envelope is not None
    artifacts = envelope["artifacts"]
    assert any(a["artifact_type"] == "adapter_request" for a in artifacts)
    assert any(a["artifact_type"] == "approval_record" for a in artifacts)
    assert any(
        a["artifact_type"] == "execution_event" and a["event_type"] == "approval_requested"
        for a in artifacts
    )

    approval = next(a for a in artifacts if a["artifact_type"] == "approval_record")
    assert approval["status"] == "pending"
    assert "decision_ref" not in approval

    event = next(a for a in artifacts if a["artifact_type"] == "execution_event")
    assert event["metadata"]["approval_id"] == approval["approval_id"]


def test_runtime_plan_draft_json_terminal_task_no_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--draft-json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["envelope_draft"] is None


def test_runtime_plan_draft_json_sanitizes_refs(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--draft-json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    text = captured.out
    assert "raw_ref" not in text
    assert "decision_ref" not in text


def test_runtime_plan_regular_json_compatible(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert "request_draft" in result
    assert "approval_draft" in result
    assert "event_draft" in result
    # Regular --json remains a compact summary; envelope_draft is not included.
    assert "envelope_draft" not in result


def test_runtime_plan_draft_json_does_not_write_ledger(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(fake_root, "running")
    events_file = _write_events(fake_root)

    tasks_before = tasks_file.read_bytes()
    events_before = events_file.read_bytes()

    code = main([
        "--root", str(fake_root),
        "runtime", "plan",
        "--task-id", "task-20260703-001",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--draft-json",
    ])
    assert code == 3
    assert tasks_file.read_bytes() == tasks_before
    assert events_file.read_bytes() == events_before

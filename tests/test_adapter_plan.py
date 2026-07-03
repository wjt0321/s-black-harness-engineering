"""Tests for adapter plan envelope generation."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from agent_runtime.cli import main
from agent_runtime.loader import load_schema


ROOT = Path(__file__).resolve().parents[1]


def _envelope_schema(root: Path) -> dict:
    return load_schema(root, "adapters/execution-envelope.schema.json")


def test_adapter_plan_github_git_push_needs_approval(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
    ])
    captured = capsys.readouterr()
    assert code == 3
    assert "NEEDS_APPROVAL" in captured.out
    assert "adapter_request" in captured.out
    assert "approval_record" in captured.out
    assert "approval_requested" in captured.out


def test_adapter_plan_shell_read_file_pass(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "README.md",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "adapter_request" in captured.out
    assert "approval_record" not in captured.out


def test_adapter_plan_json_validates_against_schema(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    envelope = json.loads(captured.out)
    schema = _envelope_schema(ROOT)
    validate(instance=envelope, schema=schema)

    assert envelope["version"] == 1
    artifacts = envelope["artifacts"]
    assert any(a["artifact_type"] == "adapter_request" for a in artifacts)
    assert any(a["artifact_type"] == "approval_record" for a in artifacts)
    assert any(
        a["artifact_type"] == "execution_event" and a["event_type"] == "approval_requested"
        for a in artifacts
    )


def test_adapter_plan_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
    ])
    assert code == 3
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()


def test_adapter_plan_unknown_adapter(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "nonexistent-adapter",
        "--operation", "foo",
    ])
    captured = capsys.readouterr()
    assert code == 1
    assert "ERROR" in captured.out
    assert "adapter-not-found" in captured.out


def test_adapter_plan_with_agent_uses_profile(capsys):
    code = main([
        "--root", str(ROOT),
        "--agent", "orchestrator",
        "adapter", "plan",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    envelope = json.loads(captured.out)
    request = next(a for a in envelope["artifacts"] if a["artifact_type"] == "adapter_request")
    assert request["context"]["policy_profile"] == "s-black"

    findings = request["preflight"]["findings"]
    rule_ids = {f["rule_id"] for f in findings}
    assert "github-publish-preflight" in rule_ids
    assert "memory-publish-preflight" not in rule_ids


def test_adapter_plan_custom_actor_and_task_id(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "plan",
        "--adapter", "shell-local",
        "--operation", "read_file",
        "--target", "README.md",
        "--actor", "test-runner",
        "--task-id", "task-20260703-999999",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    envelope = json.loads(captured.out)
    request = next(a for a in envelope["artifacts"] if a["artifact_type"] == "adapter_request")
    assert request["actor"] == "test-runner"
    assert request["task_id"] == "task-20260703-999999"

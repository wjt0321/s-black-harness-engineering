"""Tests for orchestration run --commit controlled write."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.orchestration_run_commit import RunCommitResult, commit_run
from agent_runtime.orchestration_run_dry_run import dry_run_run


ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "task-20260709-001"
REQUEST_ID = "req-20260709-001"


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with required schemas and registries."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    for src in [
        ROOT / "adapters" / "execution-envelope.schema.json",
        ROOT / "tasks" / "event.schema.json",
        ROOT / "tasks" / "task.schema.json",
    ]:
        dst = fake_root / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    adapters_dir = fake_root / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    adapters_data = json.loads((ROOT / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    adapters_data["adapters"].append(
        {
            "id": "dummy-local",
            "name": "Dummy Local Reader",
            "kind": "dummy",
            "description": "Low-risk test adapter for run commit tests.",
            "enabled": True,
            "capabilities": ["read_file"],
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
            "postflight_checks": [],
        }
    )
    (adapters_dir / "adapters.sample.json").write_text(
        json.dumps(adapters_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    policies_dir = fake_root / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    for policy_path in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copy(policy_path, policies_dir / policy_path.name)

    tasks_dir = fake_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": TASK_ID,
        "title": "Run commit test task",
        "status": "running",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "read_file",
    }
    (tasks_dir / "tasks.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return fake_root


def _base_args(fake_root: Path, **extra: str) -> list[str]:
    args = [
        "--root", str(fake_root),
        "orchestration", "run",
        "--task-id", TASK_ID,
        "--request-id", REQUEST_ID,
        "--capability", "read_file",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
    ]
    for key, value in extra.items():
        flag = f"--{key.replace('_', '-')}"
        if value == "":
            args.append(flag)
        else:
            args.append(flag)
            args.append(value)
    return args


def test_commit_missing_args_returns_needs_input(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        output=None,
        expected_plan_hash=None,
    )
    assert isinstance(result, RunCommitResult)
    assert result.status == "needs_input"
    assert "--output" in result.findings[0].message
    assert "--expected-plan-hash" in result.findings[0].message


def test_commit_hash_mismatch_blocked_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    output = "drafts/runtime/task-001/req-001.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash="deadbeef",
    )
    assert result.status == "blocked"
    assert result.freeze_check == "failed"
    assert result.plan_hash is not None
    assert result.expected_plan_hash == "deadbeef"
    assert not (fake_root / output).exists()


def test_commit_matching_hash_writes_envelope_draft(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    assert dry_run.status == "pass"
    assert dry_run.plan_hash is not None

    output = "drafts/runtime/task-001/req-001.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "pass"
    assert result.freeze_check == "pass"
    assert result.write_summary.get("committed") is True
    assert result.write_summary.get("rolled_back") is False
    assert result.write_summary.get("post_validate") == "pass"
    assert result.write_summary.get("post_inspect") == "pass"
    assert result.artifact_ref.get("path") == output

    written_path = fake_root / output
    assert written_path.is_file()
    envelope = json.loads(written_path.read_text(encoding="utf-8"))
    assert envelope.get("version") == 1
    assert any(a.get("artifact_type") == "adapter_request" for a in envelope.get("artifacts", []))


def test_commit_output_exists_blocked_no_overwrite(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    output = "drafts/runtime/task-001/req-001.envelope.json"
    existing = fake_root / output
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text('{"version": 1}\n', encoding="utf-8")

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "blocked"
    assert "already exists" in result.findings[0].message.lower()
    # Ensure original content not overwritten.
    assert existing.read_text(encoding="utf-8") == '{"version": 1}\n'


def test_commit_preflight_needs_approval_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    assert dry_run.status == "needs_approval"
    assert dry_run.plan_hash is not None

    output = "drafts/runtime/task-001/req-001.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "blocked"
    assert not (fake_root / output).exists()


def test_commit_terminal_task_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    task_path = fake_root / "tasks" / "tasks.jsonl"
    task = json.loads(task_path.read_text(encoding="utf-8").strip())
    task["status"] = "finished"
    task_path.write_text(json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8")

    output = "drafts/runtime/task-001/req-001.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash="any-hash",
    )
    assert result.status in {"blocked", "error"}
    assert not (fake_root / output).exists()


def test_commit_write_failure_no_partial_file(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    # Make the parent path a file so mkdir fails.
    parent = fake_root / "drafts" / "runtime" / "task-001"
    parent.parent.mkdir(parents=True, exist_ok=True)
    parent.write_text('"not a directory"', encoding="utf-8")
    output = "drafts/runtime/task-001/req-001.envelope.json"

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "error"
    assert not (fake_root / output).exists()


def test_commit_output_does_not_expose_sensitive_refs(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    output = "drafts/runtime/task-001/req-001.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    d = result.to_dict()
    dumped = json.dumps(d, ensure_ascii=False)
    assert "decision_ref" not in dumped
    assert "payload_refs" not in dumped
    assert "raw_ref" not in dumped


def test_cli_commit_json_output(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    output = "drafts/runtime/task-001/req-001.envelope.json"
    code = main(
        _base_args(
            fake_root,
            output=output,
            expected_plan_hash=dry_run.plan_hash,
            commit="",
        )
        + ["--json"]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["freeze_check"] == "pass"
    assert result["write_summary"]["committed"] is True
    assert (fake_root / output).is_file()


def test_cli_commit_human_readable_smoke(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    output = "drafts/runtime/task-001/req-001.envelope.json"
    code = main(
        _base_args(
            fake_root,
            output=output,
            expected_plan_hash=dry_run.plan_hash,
            commit="",
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "RUN COMMIT" in captured.out
    assert TASK_ID in captured.out
    assert REQUEST_ID in captured.out
    assert "freeze_check=pass" in captured.out
    assert (fake_root / output).is_file()


def test_commit_is_only_a_strategy_no_events_appended(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    output = "drafts/runtime/task-001/req-001.envelope.json"
    events_file = fake_root / "tasks" / "events.jsonl"
    events_file.write_text("", encoding="utf-8")
    before = events_file.read_bytes()

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "pass"
    assert events_file.read_bytes() == before

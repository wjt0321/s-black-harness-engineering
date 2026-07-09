"""Tests for orchestration run --commit controlled write."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.cli import main
from agent_runtime.orchestration_run_commit import RunCommitResult, commit_run
from agent_runtime.orchestration_run_dry_run import dry_run_run


ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "task-20260709-001"
REQUEST_ID = "req-20260709-001"
EVENTS_FILE = "tasks/events.jsonl"


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
    adapters_data["adapters"].append(
        {
            "id": "dummy-fallback",
            "name": "Dummy Fallback Reader",
            "kind": "dummy",
            "description": "Fallback test adapter for run commit tests.",
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
    (tasks_dir / "events.jsonl").write_text("", encoding="utf-8")

    return fake_root


def _read_events(fake_root: Path, events_file: str = EVENTS_FILE) -> list[dict[str, Any]]:
    path = fake_root / events_file
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


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
    assert "--events-file" in result.findings[0].message


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
        events_file=EVENTS_FILE,
    )
    assert result.status == "blocked"
    assert result.freeze_check == "failed"
    assert result.plan_hash is not None
    assert result.expected_plan_hash == "deadbeef"
    assert not (fake_root / output).exists()
    assert _read_events(fake_root) == []


def test_commit_matching_hash_writes_envelope_draft_and_events(tmp_path: Path) -> None:
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
        events_file=EVENTS_FILE,
    )
    assert result.status == "pass"
    assert result.freeze_check == "pass"
    assert result.write_summary.get("committed") is True
    assert result.write_summary.get("rolled_back") is False
    assert result.write_summary.get("post_validate") == "pass"
    assert result.write_summary.get("post_inspect") == "pass"
    assert result.write_summary.get("event_post_validate") == "pass"
    assert result.write_summary.get("appended_event_count") == 2
    assert result.artifact_ref.get("path") == output
    assert len(result.event_refs) == 2

    written_path = fake_root / output
    assert written_path.is_file()
    envelope = json.loads(written_path.read_text(encoding="utf-8"))
    assert envelope.get("version") == 1
    assert any(a.get("artifact_type") == "adapter_request" for a in envelope.get("artifacts", []))

    events = _read_events(fake_root)
    assert [e["event_type"] for e in events] == ["run_planned", "run_draft_exported"]
    for event in events:
        assert event["task_id"] == TASK_ID
        assert event["actor"] == "cli"
        metadata = event.get("metadata", {})
        assert metadata.get("request_id") == REQUEST_ID
        assert metadata.get("capability") == "read_file"
        assert metadata.get("mode") == "dry-run"
        assert "plan_hash" in metadata


def test_commit_post_check_uses_committed_events_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    observed: list[str] = []

    import agent_runtime.orchestration_run_commit as run_commit_module

    original_check = run_commit_module.check_ledger_consistency

    def spy_check_ledger_consistency(root: Path, tasks_file: str, events_file: str):
        observed.append(events_file)
        return original_check(root, tasks_file, events_file)

    monkeypatch.setattr(
        run_commit_module,
        "check_ledger_consistency",
        spy_check_ledger_consistency,
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
        events_file=EVENTS_FILE,
    )

    assert result.status == "pass"
    assert EVENTS_FILE in observed
    assert not any(path.startswith("tmp") or path.endswith(".tmp") for path in observed)


def test_commit_event_order_and_metadata_safety(tmp_path: Path) -> None:
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
    commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
    )

    events = _read_events(fake_root)
    assert len(events) == 2
    planned, exported = events
    assert planned["event_type"] == "run_planned"
    assert exported["event_type"] == "run_draft_exported"
    assert planned["timestamp"] <= exported["timestamp"]

    dumped = json.dumps(events, ensure_ascii=False)
    assert "decision_ref" not in dumped
    assert "payload_refs" not in dumped
    assert "raw_ref" not in dumped
    assert "evidence description" not in dumped.lower()


def test_commit_event_append_failure_rolls_back_draft_and_events(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    # Pre-seed the events ledger with a malformed line so post-check fails.
    events_path = fake_root / EVENTS_FILE
    events_path.write_text("this is not json\n", encoding="utf-8")
    original_bytes = events_path.read_bytes()

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
        events_file=EVENTS_FILE,
    )
    assert result.status == "blocked"
    assert result.write_summary.get("rolled_back") is True
    assert not (fake_root / output).exists()
    assert events_path.read_bytes() == original_bytes


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
        events_file=EVENTS_FILE,
    )
    assert result.status == "blocked"
    assert "already exists" in result.findings[0].message.lower()
    # Ensure original content not overwritten.
    assert existing.read_text(encoding="utf-8") == '{"version": 1}\n'
    assert _read_events(fake_root) == []


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
        events_file=EVENTS_FILE,
    )
    assert result.status == "blocked"
    assert not (fake_root / output).exists()
    assert _read_events(fake_root) == []


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
        events_file=EVENTS_FILE,
    )
    assert result.status in {"blocked", "error"}
    assert not (fake_root / output).exists()
    assert _read_events(fake_root) == []


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
        events_file=EVENTS_FILE,
    )
    assert result.status == "error"
    assert not (fake_root / output).exists()
    assert _read_events(fake_root) == []


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
        events_file=EVENTS_FILE,
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
            events_file=EVENTS_FILE,
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
    assert result["write_summary"]["appended_event_count"] == 2
    assert (fake_root / output).is_file()
    assert len(_read_events(fake_root)) == 2


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
            events_file=EVENTS_FILE,
            commit="",
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "RUN COMMIT" in captured.out
    assert TASK_ID in captured.out
    assert REQUEST_ID in captured.out
    assert "freeze_check=pass" in captured.out
    assert "events_file=" in captured.out
    assert (fake_root / output).is_file()
    assert len(_read_events(fake_root)) == 2


def test_cli_commit_missing_events_file_returns_needs_input(capsys, tmp_path: Path) -> None:
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
    assert code != 0
    assert "--events-file" in captured.out
    assert not (fake_root / output).exists()


def test_commit_does_not_modify_existing_valid_events(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    pre_existing = {
        "event_id": "evt-20260701-001",
        "task_id": TASK_ID,
        "timestamp": "2026-07-01T00:00:00+08:00",
        "actor": "user",
        "event_type": "created",
        "from_status": None,
        "to_status": "running",
        "message": "Task created",
    }
    events_path = fake_root / EVENTS_FILE
    events_path.write_text(json.dumps(pre_existing, ensure_ascii=False) + "\n", encoding="utf-8")

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
        events_file=EVENTS_FILE,
    )
    assert result.status == "pass"

    events = _read_events(fake_root)
    assert events[0]["event_type"] == "created"
    assert [e["event_type"] for e in events[1:]] == ["run_planned", "run_draft_exported"]


def _commit_source_run(
    fake_root: Path,
    task_id: str = TASK_ID,
    request_id: str = REQUEST_ID,
    capability: str = "read_file",
    operation: str = "read_file",
    target: str = "docs/06-adapter-layer.md",
    output: str = "drafts/runtime/task-001/req-001.envelope.json",
    events_file: str = EVENTS_FILE,
) -> str:
    """Commit a normal run and return its plan_hash."""
    dry_run = dry_run_run(
        fake_root,
        task_id=task_id,
        request_id=request_id,
        capability=capability,
        operation=operation,
        target=target,
    )
    assert dry_run.status == "pass"
    assert dry_run.plan_hash is not None
    result = commit_run(
        fake_root,
        task_id=task_id,
        request_id=request_id,
        capability=capability,
        operation=operation,
        target=target,
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=events_file,
    )
    assert result.status == "pass"
    return dry_run.plan_hash


def test_retry_commit_success_writes_lineage_metadata(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    source_hash = _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    assert dry_run.status == "pass"
    assert dry_run.plan_hash != source_hash

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    assert result.status == "pass"
    assert result.lineage_type == "retry"
    assert result.retry_of == REQUEST_ID

    written_path = fake_root / output
    assert written_path.is_file()
    envelope = json.loads(written_path.read_text(encoding="utf-8"))
    request = next(
        a for a in envelope.get("artifacts", []) if a.get("artifact_type") == "adapter_request"
    )
    assert request.get("context", {}).get("lineage_type") == "retry"
    assert request.get("context", {}).get("retry_of") == REQUEST_ID

    events = _read_events(fake_root)
    retry_events = [e for e in events if e.get("metadata", {}).get("request_id") == new_request_id]
    assert [e["event_type"] for e in retry_events] == ["run_planned", "run_draft_exported"]
    for event in retry_events:
        metadata = event.get("metadata", {})
        assert metadata.get("lineage_type") == "retry"
        assert metadata.get("retry_of") == REQUEST_ID
        assert metadata.get("mode") == "dry-run"
        assert metadata.get("envelope_path") == output


def test_fallback_commit_success_writes_lineage_metadata(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    _commit_source_run(fake_root)

    new_request_id = "req-20260709-003"
    output = "drafts/runtime/task-001/req-003.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_from=REQUEST_ID,
        fallback_to="dummy-fallback",
    )
    assert dry_run.status == "pass"
    assert dry_run.lineage_type == "fallback"
    assert dry_run.fallback_from == REQUEST_ID
    assert dry_run.fallback_to == "dummy-fallback"

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        fallback_from=REQUEST_ID,
        fallback_to="dummy-fallback",
    )
    assert result.status == "pass"
    assert result.lineage_type == "fallback"
    assert result.fallback_from == REQUEST_ID
    assert result.fallback_to == "dummy-fallback"

    written_path = fake_root / output
    assert written_path.is_file()
    envelope = json.loads(written_path.read_text(encoding="utf-8"))
    request = next(
        a for a in envelope.get("artifacts", []) if a.get("artifact_type") == "adapter_request"
    )
    assert request.get("context", {}).get("lineage_type") == "fallback"
    assert request.get("context", {}).get("fallback_from") == REQUEST_ID
    assert request.get("context", {}).get("fallback_to") == "dummy-fallback"
    assert request.get("adapter_id") == "dummy-fallback"

    events = _read_events(fake_root)
    fallback_events = [e for e in events if e.get("metadata", {}).get("request_id") == new_request_id]
    assert [e["event_type"] for e in fallback_events] == ["run_planned", "run_draft_exported"]
    for event in fallback_events:
        metadata = event.get("metadata", {})
        assert metadata.get("lineage_type") == "fallback"
        assert metadata.get("fallback_from") == REQUEST_ID
        assert metadata.get("fallback_to") == "dummy-fallback"
        assert metadata.get("adapter_id") == "dummy-fallback"


def test_retry_commit_missing_expected_hash_blocked_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=None,
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    assert result.status == "needs_input"
    assert "--expected-plan-hash" in result.findings[0].message
    assert not (fake_root / output).exists()
    # Only source run events exist.
    assert len(_read_events(fake_root)) == 2


def test_retry_commit_source_request_not_found_blocked_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    # No source run committed.
    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    assert result.status == "validation_failed"
    assert REQUEST_ID in result.findings[0].message
    assert not (fake_root / output).exists()
    assert _read_events(fake_root) == []


def test_retry_commit_source_request_belongs_to_other_task_blocked_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    other_task_id = "task-20260709-999"
    other_request_id = "req-20260709-999"
    other_task = {
        "id": other_task_id,
        "title": "Other task",
        "status": "running",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "read_file",
    }
    tasks_path = fake_root / "tasks" / "tasks.jsonl"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8") + json.dumps(other_task, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _commit_source_run(
        fake_root,
        task_id=other_task_id,
        request_id=other_request_id,
        output="drafts/runtime/task-20260709-999/req-20260709-999.envelope.json",
    )

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=other_request_id,
    )
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        retry_of=other_request_id,
    )
    assert result.status == "validation_failed"
    assert other_request_id in result.findings[0].message
    assert not (fake_root / output).exists()
    # Only other task events exist.
    events = _read_events(fake_root)
    assert all(e.get("task_id") != TASK_ID for e in events)


def test_retry_commit_hash_mismatch_blocked_no_write(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash="deadbeef",
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    assert result.status == "blocked"
    assert result.freeze_check == "failed"
    assert not (fake_root / output).exists()
    assert len(_read_events(fake_root)) == 2


def test_retry_commit_a_success_b_failure_rolls_back_cleanly(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    # Pre-seed the events ledger with a malformed line so B post-check fails.
    events_path = fake_root / EVENTS_FILE
    original_bytes = events_path.read_bytes()
    events_path.write_text(original_bytes.decode("utf-8") + "this is not json\n", encoding="utf-8")
    original_bytes = events_path.read_bytes()

    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    assert result.status == "blocked"
    assert result.write_summary.get("rolled_back") is True
    assert not (fake_root / output).exists()
    assert events_path.read_bytes() == original_bytes


def test_retry_commit_does_not_expose_sensitive_refs(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    result = commit_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        output=output,
        expected_plan_hash=dry_run.plan_hash,
        events_file=EVENTS_FILE,
        retry_of=REQUEST_ID,
    )
    d = result.to_dict()
    dumped = json.dumps(d, ensure_ascii=False)
    assert "decision_ref" not in dumped
    assert "payload_refs" not in dumped
    assert "raw_ref" not in dumped
    assert "docs/06-adapter-layer.md" not in dumped

    events = _read_events(fake_root)
    events_dumped = json.dumps(events, ensure_ascii=False)
    assert "decision_ref" not in events_dumped
    assert "payload_refs" not in events_dumped
    assert "raw_ref" not in events_dumped


def test_cli_retry_commit_success(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    source_hash = _commit_source_run(fake_root)

    new_request_id = "req-20260709-002"
    output = "drafts/runtime/task-001/req-002.envelope.json"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=new_request_id,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    code = main(
        [
            "--root", str(fake_root),
            "orchestration", "run",
            "--task-id", TASK_ID,
            "--request-id", new_request_id,
            "--capability", "read_file",
            "--operation", "read_file",
            "--target", "docs/06-adapter-layer.md",
            "--retry-of", REQUEST_ID,
            "--output", output,
            "--events-file", EVENTS_FILE,
            "--expected-plan-hash", dry_run.plan_hash,
            "--commit",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "lineage_type=retry" in captured.out
    assert f"retry_of={REQUEST_ID}" in captured.out
    assert (fake_root / output).is_file()
    events = _read_events(fake_root)
    retry_events = [e for e in events if e.get("metadata", {}).get("request_id") == new_request_id]
    assert len(retry_events) == 2

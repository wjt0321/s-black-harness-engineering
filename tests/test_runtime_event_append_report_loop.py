"""Smoke/report loop for runtime event append.

This test builds a minimal temporary project root and exercises the full
read-only -> commit -> report loop:

    dry-run -> commit -> task validate/check-ledger -> runtime report

It asserts that:
- dry-run does not modify the events ledger.
- commit appends exactly one line.
- runtime report reflects the appended event in its summary.
- no sensitive values leak into CLI outputs.
- no real repository ledger files are modified.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agent_runtime.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _last_json_object(text: str) -> dict[str, Any]:
    """Extract the last JSON object from multi-command stdout."""
    decoder = json.JSONDecoder()
    result: dict[str, Any] | None = None
    idx = 0
    while idx < len(text):
        # Skip whitespace and non-JSON prefix.
        while idx < len(text) and text[idx] not in "{[":
            idx += 1
        if idx >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                result = obj
            idx += end
        except json.JSONDecodeError:
            idx += 1
    if result is None:
        raise ValueError("No JSON object found in output")
    return result


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a temporary project root with schemas and policies."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/event.schema.json",
        "tasks/task.schema.json",
        "adapters/execution-envelope.schema.json",
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


def _write_task(root: Path) -> None:
    task = {
        "id": "task-20260706-001",
        "title": "smoke task",
        "status": "running",
        "created_at": "2026-07-06T10:00:00+08:00",
        "updated_at": "2026-07-06T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
        "assignee": "cli",
    }
    (root / "tasks.jsonl").write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(root: Path) -> None:
    events: list[dict[str, Any]] = [
        {
            "event_id": "evt-20260706-001",
            "task_id": "task-20260706-001",
            "timestamp": "2026-07-06T10:00:00+08:00",
            "actor": "cli",
            "event_type": "created",
            "from_status": None,
            "to_status": "planned",
            "message": "created",
            "artifacts": [],
            "metadata": {},
        },
        {
            "event_id": "evt-20260706-002",
            "task_id": "task-20260706-001",
            "timestamp": "2026-07-06T10:01:00+08:00",
            "actor": "cli",
            "event_type": "status_changed",
            "from_status": "planned",
            "to_status": "running",
            "message": "started",
            "artifacts": [],
            "metadata": {"request_id": "req-20260706-001"},
        },
    ]
    (root / "events.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
        encoding="utf-8",
    )


def _write_envelope(root: Path) -> None:
    envelope: dict[str, Any] = {
        "version": 1,
        "description": "smoke envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260706-001",
                "task_id": "task-20260706-001",
                "adapter_id": "github-cli",
                "operation": "git_status",
                "actor": "cli",
                "target": "origin/main",
                "input": {},
                "context": {
                    "source": "cli",
                    "policy_profile": "all",
                    "risk_level": "local",
                    "dry_run": True,
                    "requires_approval": False,
                },
                "preflight": {"status": "pass", "findings": []},
                "created_at": "2026-07-06T10:00:00+08:00",
            },
            {
                "artifact_type": "adapter_response",
                "response_id": "resp-20260706-001",
                "request_id": "req-20260706-001",
                "status": "succeeded",
                "message": "Test response.",
                "artifacts": [],
                "evidence": [
                    {
                        "type": "test",
                        "description": "Detailed evidence description",
                        "ref": "ref-1",
                    }
                ],
                "raw_ref": None,
                "error": None,
                "finished_at": "2026-07-06T10:00:01+08:00",
            },
            {
                "artifact_type": "execution_event",
                "event_id": "exe-20260706-001",
                "task_id": "task-20260706-001",
                "request_id": "req-20260706-001",
                "timestamp": "2026-07-06T10:01:00+08:00",
                "actor": "cli",
                "event_type": "evidence_added",
                "message": "evidence attached",
                "metadata": {"response_id": "resp-20260706-001", "evidence_count": 1},
            },
        ],
    }
    (root / "envelope.json").write_text(json.dumps(envelope), encoding="utf-8")


def _write_candidate(root: Path) -> None:
    candidate: dict[str, Any] = {
        "event_id": "evt-20260706-003",
        "task_id": "task-20260706-001",
        "timestamp": "2026-07-06T10:02:00+08:00",
        "actor": "cli",
        "event_type": "progress",
        "from_status": "running",
        "to_status": "running",
        "message": "Detailed progress message should not leak",
        "artifacts": [],
        "metadata": {"request_id": "req-20260706-001"},
    }
    (root / "candidate.json").write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")


def test_runtime_event_append_smoke_report_loop(capsys, tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root)
    _write_events(root)
    _write_envelope(root)
    _write_candidate(root)

    events_before = (root / "events.jsonl").read_bytes()

    # 1. Dry-run must not modify the ledger.
    dry_code = main([
        "--root", str(root),
        "runtime", "event", "append",
        "--file", "candidate.json",
        "--dry-run",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
        "--envelope", "envelope.json",
    ])
    dry_captured = capsys.readouterr()
    assert dry_code == 0
    assert "would_append=False" in dry_captured.out
    assert "committed=False" in dry_captured.out
    assert (root / "events.jsonl").read_bytes() == events_before

    # 2. Commit appends exactly one line.
    commit_code = main([
        "--root", str(root),
        "runtime", "event", "append",
        "--file", "candidate.json",
        "--commit",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
        "--envelope", "envelope.json",
    ])
    commit_captured = capsys.readouterr()
    assert commit_code == 0
    assert "committed=True" in commit_captured.out
    assert "post_validate=pass" in commit_captured.out
    assert "post_ledger_check=pass" in commit_captured.out

    events_after = (root / "events.jsonl").read_text(encoding="utf-8")
    assert events_after.count("\n") == 3
    assert '"event_id": "evt-20260706-003"' in events_after

    # 3. Post-commit read-only checks pass.
    validate_code = main([
        "--root", str(root),
        "task", "validate",
        "--record-file", "events.jsonl",
        "--schema", "event",
    ])
    assert validate_code == 0

    ledger_code = main([
        "--root", str(root),
        "task", "check-ledger",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
    ])
    assert ledger_code == 0

    # 4. Runtime report reflects the appended event.
    report_code = main([
        "--root", str(root),
        "runtime", "report",
        "--task-id", "task-20260706-001",
        "--request-id", "req-20260706-001",
        "--envelope", "envelope.json",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
        "--json",
    ])
    report_captured = capsys.readouterr()
    assert report_code == 0, report_captured.out
    report = _last_json_object(report_captured.out)
    assert report["event_summary"]["total"] == 3
    assert report["event_summary"]["latest"]["event_type"] == "progress"

    # 5. Sensitive values do not leak into any CLI output.
    combined_output = dry_captured.out + commit_captured.out + report_captured.out
    assert "Detailed progress message should not leak" not in combined_output
    assert "origin/main" not in combined_output
    assert "Detailed evidence description" not in combined_output


def test_smoke_loop_does_not_modify_real_repo_ledgers(tmp_path):
    """Ensure the test never touches the repository sample ledgers."""
    root = _setup_fake_root(tmp_path)
    _write_task(root)
    _write_events(root)
    _write_envelope(root)
    _write_candidate(root)

    real_tasks = (ROOT / "tasks" / "tasks.jsonl").read_bytes()
    real_events = (ROOT / "tasks" / "events.jsonl").read_bytes()
    real_envelope = (ROOT / "adapters" / "execution-envelope.examples.json").read_bytes()

    main([
        "--root", str(root),
        "runtime", "event", "append",
        "--file", "candidate.json",
        "--commit",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
        "--envelope", "envelope.json",
    ])

    main([
        "--root", str(root),
        "runtime", "report",
        "--task-id", "task-20260706-001",
        "--request-id", "req-20260706-001",
        "--envelope", "envelope.json",
        "--tasks-file", "tasks.jsonl",
        "--events-file", "events.jsonl",
    ])

    assert (ROOT / "tasks" / "tasks.jsonl").read_bytes() == real_tasks
    assert (ROOT / "tasks" / "events.jsonl").read_bytes() == real_events
    assert (ROOT / "adapters" / "execution-envelope.examples.json").read_bytes() == real_envelope

"""Smoke loop for runtime task create + event append + report.

This test exercises the full controlled-write chain in a temporary project
root without touching the repository's real task/event ledgers:

1) runtime task create --dry-run
2) runtime task create --commit
3) runtime event append --dry-run
4) runtime event append --commit
5) task validate + task check-ledger
6) runtime report

All assertions check safe identifiers/counts only; no title, summary, evidence
description, artifact payload, or secret value is leaked.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "adapters/execution-envelope.schema.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _task(task_id: str) -> dict[str, object]:
    return {
        "id": task_id,
        "title": "smoke task title",
        "status": "planned",
        "created_at": "2026-07-07T10:00:00+08:00",
        "updated_at": "2026-07-07T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "cli",
        "tags": ["smoke"],
        "artifacts": [],
        "evidence": [],
    }


def _event(event_id: str, task_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": "2026-07-07T10:00:00+08:00",
        "actor": "cli",
        "event_type": "created",
        "from_status": None,
        "to_status": "planned",
        "message": "task created",
        "artifacts": [],
        "metadata": {},
    }


def _envelope(request_id: str, task_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "description": "smoke envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": request_id,
                "task_id": task_id,
                "adapter_id": "shell-local",
                "operation": "read_file",
                "actor": "cli",
                "target": "README.md",
                "input": {},
                "context": {
                    "source": "cli",
                    "policy_profile": "all",
                    "risk_level": "local",
                    "dry_run": True,
                    "requires_approval": False,
                },
                "preflight": {"status": "pass", "findings": []},
                "created_at": "2026-07-07T10:00:00+08:00",
            }
        ],
    }


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, *records: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def test_smoke_loop_task_create_then_event_append_then_report(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    event_id = "evt-20260707-001"
    request_id = "req-20260707-001"

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    events_file = tasks_dir / "events.jsonl"
    tasks_file.write_text("", encoding="utf-8")
    events_file.write_text("", encoding="utf-8")

    candidate_task = root / "candidate-task.json"
    _write_json(candidate_task, _task(task_id))

    candidate_event = root / "candidate-event.json"
    _write_json(candidate_event, _event(event_id, task_id))

    envelope_file = root / "envelope.json"
    _write_json(envelope_file, _envelope(request_id, task_id))

    # 1) task create dry-run
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "task",
            "create",
            "--file",
            str(candidate_task),
            "--dry-run",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "would_create=False" in captured.out
    assert tasks_file.read_text(encoding="utf-8") == ""

    # 2) task create commit
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "task",
            "create",
            "--file",
            str(candidate_task),
            "--commit",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "committed=True" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1
    assert '"id": "task-20260707-001"' in tasks_file.read_text(encoding="utf-8")

    # 3) event append dry-run
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "append",
            "--file",
            str(candidate_event),
            "--dry-run",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "would_append=False" in captured.out
    assert events_file.read_text(encoding="utf-8") == ""

    # 4) event append commit
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "append",
            "--file",
            str(candidate_event),
            "--commit",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "committed=True" in captured.out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1

    # 5) task validate + task check-ledger
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "task",
            "validate",
            "--record-file",
            "tasks/tasks.jsonl",
            "--schema",
            "task",
        ],
    )
    assert main() == 0

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "task",
            "validate",
            "--record-file",
            "tasks/events.jsonl",
            "--schema",
            "event",
        ],
    )
    assert main() == 0

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "task",
            "check-ledger",
            "--tasks-file",
            "tasks/tasks.jsonl",
            "--events-file",
            "tasks/events.jsonl",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out

    # 6) runtime report
    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "report",
            "--task-id",
            task_id,
            "--request-id",
            request_id,
            "--envelope",
            "envelope.json",
            "--tasks-file",
            "tasks/tasks.jsonl",
            "--events-file",
            "tasks/events.jsonl",
        ],
    )
    assert main() in {0, 3, 4}  # pass or needs_input/needs_approval is acceptable for smoke
    captured = capsys.readouterr()
    assert task_id in captured.out
    # No sensitive free-text payload should leak.
    assert "smoke task title" not in captured.out
    assert "task created" not in captured.out

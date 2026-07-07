"""Controlled-write regression test.

This test runs the full controlled-write chain in a temporary project root and
asserts that:

- task create dry-run -> commit -> event append dry-run -> commit works.
- post-commit read-only checks (task validate / check-ledger) pass.
- runtime report runs and does not leak title / event message.
- the repository's real task/event ledgers are not modified.

No new write permissions are introduced; the test only reuses existing commit
commands and tmp_path isolation.
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


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _task(task_id: str) -> dict[str, object]:
    return {
        "id": task_id,
        "title": "controlled write regression task title",
        "status": "planned",
        "created_at": "2026-07-07T10:00:00+08:00",
        "updated_at": "2026-07-07T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "cli",
        "tags": ["regression"],
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
        "message": "controlled write regression event message",
        "artifacts": [],
        "metadata": {},
    }


def _envelope(request_id: str, task_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "description": "controlled write regression envelope",
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


def test_controlled_write_regression_does_not_touch_real_ledgers(tmp_path, monkeypatch, capsys):
    real_tasks = ROOT / "tasks" / "tasks.jsonl"
    real_events = ROOT / "tasks" / "events.jsonl"
    real_tasks_before = real_tasks.read_bytes() if real_tasks.is_file() else b""
    real_events_before = real_events.read_bytes() if real_events.is_file() else b""

    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-999"
    event_id = "evt-20260707-999"
    request_id = "req-20260707-999"

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    events_file = tasks_dir / "events.jsonl"
    tasks_file.write_text("", encoding="utf-8")
    events_file.write_text("", encoding="utf-8")

    _write_json(root / "candidate-task.json", _task(task_id))
    _write_json(root / "candidate-event.json", _event(event_id, task_id))
    _write_json(root / "envelope.json", _envelope(request_id, task_id))

    def _run(argv: list[str]) -> str:
        monkeypatch.setattr("sys.argv", ["agent-runtime", "--root", str(root), *argv])
        code = main()
        captured = capsys.readouterr()
        return captured.out, code

    # 1) task create dry-run
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--dry-run"])
    assert code == 0
    assert "would_create=False" in out
    assert tasks_file.read_text(encoding="utf-8") == ""

    # 2) task create commit
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--commit"])
    assert code == 0
    assert "committed=True" in out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1

    # 3) event append dry-run
    out, code = _run(["runtime", "event", "append", "--file", "candidate-event.json", "--dry-run"])
    assert code == 0
    assert "would_append=False" in out
    assert events_file.read_text(encoding="utf-8") == ""

    # 4) event append commit
    out, code = _run(["runtime", "event", "append", "--file", "candidate-event.json", "--commit"])
    assert code == 0
    assert "committed=True" in out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1

    # 5) post-commit read-only checks
    out, code = _run(["task", "validate", "--record-file", "tasks/tasks.jsonl", "--schema", "task"])
    assert code == 0
    out, code = _run(["task", "validate", "--record-file", "tasks/events.jsonl", "--schema", "event"])
    assert code == 0
    out, code = _run(["task", "check-ledger", "--tasks-file", "tasks/tasks.jsonl", "--events-file", "tasks/events.jsonl"])
    assert code == 0
    assert "PASS" in out

    # 6) runtime report
    out, code = _run([
        "runtime", "report",
        "--task-id", task_id,
        "--request-id", request_id,
        "--envelope", "envelope.json",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
    ])
    assert code in {0, 3, 4}
    assert task_id in out
    # No sensitive free-text payload should leak.
    assert "controlled write regression task title" not in out
    assert "controlled write regression event message" not in out

    # Repository real ledgers must be unchanged.
    assert real_tasks.read_bytes() == real_tasks_before
    assert real_events.read_bytes() == real_events_before

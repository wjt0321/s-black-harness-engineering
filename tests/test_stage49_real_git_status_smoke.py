from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main

ROOT = Path(__file__).resolve().parents[1]


pytestmark = pytest.mark.skipif(
    os.name != "nt"
    or os.environ.get("AGENT_RUNTIME_RUN_REAL_GIT_STATUS_SMOKE") != "1",
    reason="explicit Windows real-execution smoke authorization required",
)


def _copy(root: Path, relative: str) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, destination)


def _build_smoke_root(tmp_path: Path) -> Path:
    root = tmp_path / "stage49-smoke"
    (root / "agent_runtime").mkdir(parents=True)
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / ".git" / "objects" / "pack").mkdir(parents=True)
    (root / ".git" / "info").mkdir(parents=True)
    (root / "tasks").mkdir(parents=True)
    (root / "adapters").mkdir(parents=True)
    (root / "policies").mkdir(parents=True)
    for relative in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "tasks/execution-audit-event.schema.json",
        "adapters/adapter.schema.json",
        "adapters/adapters.sample.json",
    ):
        _copy(root, relative)
    for source in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copyfile(source, root / "policies" / source.name)
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'stage49-smoke'\nversion = '0.0.0'\n",
        encoding="utf-8",
    )
    (root / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    (root / ".git" / "config").write_text(
        "[core]\n"
        "repositoryformatversion = 0\n"
        "bare = false\n"
        "filemode = false\n",
        encoding="utf-8",
    )
    (root / ".git" / "info" / "exclude").write_text("", encoding="utf-8")
    task_id = "task-20260717-999"
    (root / "tasks" / "tasks.jsonl").write_text(
        json.dumps(
            {
                "id": task_id,
                "title": "Stage 49 real smoke",
                "status": "running",
                "created_at": "2026-07-17T08:00:00+00:00",
                "updated_at": "2026-07-17T08:00:00+00:00",
                "created_by": "local-operator",
                "source": "cli",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "tasks" / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "evt-20260717-999001",
                "task_id": task_id,
                "timestamp": "2026-07-17T08:00:00+00:00",
                "actor": "local-operator",
                "event_type": "created",
                "from_status": None,
                "to_status": "running",
                "message": "Stage 49 smoke task created.",
                "artifacts": [],
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def test_real_fixed_git_status_closes_audit_and_withholds_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _build_smoke_root(tmp_path)

    code = main(
        [
            "--root",
            str(root),
            "orchestration",
            "execution",
            "git-status",
            "--task-id",
            "task-20260717-999",
            "--request-id",
            "req-20260717-999",
            "--commit",
            "--json",
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert code == 0
    assert payload["status"] == "ready"
    assert payload["lifecycle"] == "closed"
    assert payload["audit"]["state"] == "closed_succeeded"
    assert payload["audit"]["audit_incomplete"] is False
    assert payload["summary"]["entry_count"] > 0
    assert payload["no_write_evidence"] == {
        "no_write_contract": True,
        "guard_evidence_passed": True,
        "filesystem_write_proof": False,
    }
    assert len((root / "tasks" / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert str(root) not in output
    assert "pyproject.toml" not in output
    assert "refs/heads/main" not in output
    assert "PATH" not in output

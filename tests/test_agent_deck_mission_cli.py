from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime import cli


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_agent_deck_mission_submit_cli_emits_safe_dry_run_json(capsys, tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    shutil.copy(REPO_ROOT / "tasks" / "task.schema.json", tasks / "task.schema.json")
    shutil.copy(REPO_ROOT / "tasks" / "event.schema.json", tasks / "event.schema.json")

    exit_code = cli.main(
        [
            "agent-deck",
            "mission",
            "submit",
            "--goal",
            "为正式任务建立安全入口",
            "--dry-run",
            "--root",
            str(tmp_path),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["task_id"] == "task-20260729-001"
    assert payload["goal_present"] is True
    assert "为正式任务建立安全入口" not in json.dumps(payload, ensure_ascii=False)

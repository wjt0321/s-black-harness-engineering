"""Tests for CLI command entry points."""

from pathlib import Path

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def test_cli_doctor(capsys):
    code = main(["--root", str(ROOT), "doctor"])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out or '"status": "pass"' in captured.out


def test_cli_check_text_pass(capsys):
    code = main(["--root", str(ROOT), "check", "text", "--text", "hello"])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out


def test_cli_check_text_blocked(capsys):
    token = "ghp_" + "X" * 36
    code = main(["--root", str(ROOT), "check", "text", "--text", token])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED" in captured.out
    assert "X" * 36 not in captured.out


def test_cli_check_text_json(capsys):
    code = main(["--root", str(ROOT), "check", "text", "--text", "hello", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert '"status": "pass"' in captured.out


def test_cli_check_path_blocked(capsys):
    code = main(["--root", str(ROOT), "check", "path", "./received/raw.png", "--write"])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED" in captured.out


def test_cli_check_action_needs_approval(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "action",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
    ])
    captured = capsys.readouterr()
    assert code == 3
    assert "NEEDS_APPROVAL" in captured.out
    assert "github-cli-approval" in captured.out
    assert "github-publish-preflight" in captured.out
    assert "secret_scan" in captured.out


def test_cli_check_action_completion_requires_evidence(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "action",
        "--adapter", "shell-local",
        "--operation", "mark_finished",
        "--target", "task-20260702-001",
    ])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out
    assert "completion-evidence-required" in captured.out
    assert "test_output" in captured.out


def test_cli_check_action_policy_profile_limits_rules(capsys):
    code = main([
        "--root", str(ROOT),
        "--policy-profile", "s-black",
        "check", "action",
        "--adapter", "shell-local",
        "--operation", "mark_finished",
        "--target", "task-20260702-001",
    ])
    captured = capsys.readouterr()
    assert code == 4
    assert "completion-evidence-required" in captured.out
    assert "memory-distillation-evidence-required" not in captured.out
    assert "media-artifact-required" not in captured.out


def test_cli_agents_list(capsys):
    code = main(["--root", str(ROOT), "agents", "--capability", "planning"])
    captured = capsys.readouterr()
    assert code == 0
    assert "orchestrator" in captured.out


def test_cli_adapters_list(capsys):
    code = main(["--root", str(ROOT), "adapters", "--kind", "github"])
    captured = capsys.readouterr()
    assert code == 0
    assert "github-cli" in captured.out


def test_cli_policies_list(capsys):
    code = main(["--root", str(ROOT), "policies"])
    captured = capsys.readouterr()
    assert code == 0
    assert "s-black.sample.policy.json" in captured.out


def test_cli_policies_list_profile(capsys):
    code = main(["--root", str(ROOT), "--policy-profile", "s-black", "policies"])
    captured = capsys.readouterr()
    assert code == 0
    assert "s-black.sample.policy.json" in captured.out
    assert "wangcai.sample.policy.json" not in captured.out
    assert "dabai.sample.policy.json" not in captured.out


def test_cli_task_status(capsys):
    code = main(["--root", str(ROOT), "task", "status", "task-20260702-001"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Task: task-20260702-001" in captured.out
    assert "Status: finished" in captured.out
    assert "docs/03-policy-schema.md" in captured.out


def test_cli_task_status_json(capsys):
    code = main(["--root", str(ROOT), "task", "status", "task-20260702-001", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert '"id": "task-20260702-001"' in captured.out
    assert '"status": "finished"' in captured.out


def test_cli_task_status_missing(capsys):
    code = main(["--root", str(ROOT), "task", "status", "missing-task"])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out
    assert "missing-task" in captured.out


def test_cli_task_events(capsys):
    code = main(["--root", str(ROOT), "task", "events", "task-20260702-001"])
    captured = capsys.readouterr()
    assert code == 0
    assert "created" in captured.out
    assert "finished" in captured.out
    assert "planned -> running" in captured.out


def test_cli_task_events_missing(capsys):
    code = main(["--root", str(ROOT), "task", "events", "missing-task"])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out

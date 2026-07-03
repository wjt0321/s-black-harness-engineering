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

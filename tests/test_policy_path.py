"""Tests for check_path path rule checking."""

from pathlib import Path

from agent_runtime.policy import check_path


ROOT = Path(__file__).resolve().parents[1]


def test_check_path_read_allowed():
    result = check_path(ROOT, "./docs/06-adapter-layer.md", read=True)
    assert result.status == "pass"


def test_check_path_write_allowed():
    result = check_path(ROOT, "./image-output/report.png", write=True)
    assert result.status == "pass"


def test_check_path_readonly_blocked_on_write():
    result = check_path(ROOT, "./received/raw.png", write=True)
    assert result.status == "blocked"
    assert any(f.rule_id == "received-readonly" for f in result.findings)


def test_check_path_readonly_allowed_on_read():
    result = check_path(ROOT, "./received/raw.png", read=True)
    assert result.status == "pass"


def test_check_path_delete_on_readonly_blocked():
    result = check_path(ROOT, "./workspaces/orchestrator/plan.md", delete=True)
    assert result.status == "blocked"


def test_check_path_deny_directory():
    result = check_path(ROOT, "./image-prompts/subdir", write=True)
    assert result.status == "blocked"


def test_check_path_disallowed_extension():
    result = check_path(ROOT, "./image-output/report.md", write=True)
    assert result.status == "blocked"

"""Tests for check_text secret scanning."""

from pathlib import Path

import pytest

from agent_runtime.policy import check_text


ROOT = Path(__file__).resolve().parents[1]


def test_check_text_pass():
    result = check_text(ROOT, "hello world")
    assert result.status == "pass"
    assert not result.findings


def test_check_text_blocked_github_token():
    # Construct token in memory to avoid committing a real-looking token.
    token = "ghp_" + "A" * 36
    result = check_text(ROOT, token)
    assert result.status == "blocked"
    assert any(f.rule_id == "github-token" for f in result.findings)
    # Ensure we never echo the full match in output.
    rendered = result.render_json()
    assert "A" * 36 not in rendered


def test_check_text_blocked_openai_key():
    key = "sk-" + "B" * 24
    result = check_text(ROOT, key)
    assert result.status == "blocked"
    assert any(f.rule_id == "openai-style-key" for f in result.findings)


def test_check_text_line_column_reported():
    key = "sk-" + "C" * 24
    text = f"prefix\n{key}\n"
    result = check_text(ROOT, text)
    finding = next(f for f in result.findings if f.rule_id == "openai-style-key")
    assert finding.line == 2
    assert finding.column == 1


def test_check_text_no_full_match_in_human_output():
    token = "ghp_" + "D" * 36
    result = check_text(ROOT, token)
    human = result.render_human()
    assert "D" * 36 not in human

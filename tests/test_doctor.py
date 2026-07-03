"""Tests for doctor validation."""

from pathlib import Path

from agent_runtime.doctor import run_doctor


ROOT = Path(__file__).resolve().parents[1]


def test_doctor_passes():
    result = run_doctor(ROOT)
    assert result.status == "pass"
    assert not result.findings


def test_doctor_fails_missing_directory(tmp_path):
    result = run_doctor(tmp_path)
    assert result.status == "blocked"
    assert any("missing-directory" == f.rule_id for f in result.findings)

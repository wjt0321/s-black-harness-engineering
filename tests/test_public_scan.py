"""Tests for tools/public_scan.py."""

from pathlib import Path

from tools.public_scan import scan


ROOT = Path(__file__).resolve().parents[1]


def test_scan_clean_text(tmp_path):
    sample = tmp_path / "clean.md"
    sample.write_text("This is a clean public document.\nNo tokens or local paths.\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert not findings


def test_scan_detects_github_token(tmp_path):
    sample = tmp_path / "secret.md"
    token = "ghp_" + "A" * 36
    sample.write_text(f"token = {token}\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert any(f[2] == "github-token" for f in findings)


def test_scan_detects_openai_key(tmp_path):
    sample = tmp_path / "secret.md"
    key = "sk-" + "B" * 24
    sample.write_text(f"key = {key}\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert any(f[2] == "openai-style-key" for f in findings)


def test_scan_detects_windows_absolute_path(tmp_path):
    sample = tmp_path / "paths.md"
    windows_path = "Z:" + "\\example\\path"
    sample.write_text(f"target = {windows_path}\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert any(f[2] == "windows-absolute-path" for f in findings)


def test_scan_detects_unix_home_path(tmp_path):
    sample = tmp_path / "paths.md"
    unix_path = "/home/" + "user/project"
    sample.write_text(f"target = {unix_path}\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert any(f[2] == "unix-home-path" for f in findings)


def test_scan_does_not_echo_full_secret(tmp_path):
    sample = tmp_path / "secret.md"
    token = "ghp_" + "C" * 36
    sample.write_text(f"token = {token}\n", encoding="utf-8")
    _, lines = scan(tmp_path)
    output = "\n".join(lines)
    assert "C" * 36 not in output


def test_scan_skips_credential_files(tmp_path):
    cred = tmp_path / ".env"
    cred.write_text("API_KEY=sk-" + "D" * 24 + "\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert not findings


def test_scan_skips_binary_dirs(tmp_path):
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    sample = pycache / "cache.txt"
    sample.write_text("ghp_" + "E" * 36 + "\n", encoding="utf-8")
    findings, _ = scan(tmp_path)
    assert not findings


def test_scan_reports_line_number(tmp_path):
    sample = tmp_path / "secret.md"
    sample.write_text(
        "line one\n"
        "line two\n"
        f"token = ghp_{ 'F' * 36 }\n",
        encoding="utf-8",
    )
    findings, _ = scan(tmp_path)
    finding = next(f for f in findings if f[2] == "github-token")
    assert finding[1] == 3


def test_scan_on_repository_passes():
    findings, _ = scan(ROOT)
    assert not findings

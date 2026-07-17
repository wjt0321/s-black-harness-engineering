from __future__ import annotations

import hashlib

import pytest

from agent_runtime.git_status_porcelain import parse_git_status_output


@pytest.mark.parametrize(
    ("header", "detached", "ahead", "behind"),
    [
        ("## HEAD (no branch)\n", True, 0, 0),
        ("## No commits yet on main\n", False, 0, 0),
        ("## Initial commit on main\n", False, 0, 0),
        ("## main\n", False, 0, 0),
        ("## main...origin/main\n", False, 0, 0),
        ("## main...origin/main [ahead 2]\n", False, 2, 0),
        ("## main...origin/main [behind 3]\n", False, 0, 3),
        ("## main...origin/main [ahead 2, behind 3]\n", False, 2, 3),
    ],
)
def test_branch_header_grammar(
    header: str, detached: bool, ahead: int, behind: int
) -> None:
    raw = header.encode()
    result = parse_git_status_output(raw, b"", exit_code=0)

    assert result.status == "pass"
    assert result.summary is not None
    assert result.summary.detached is detached
    assert result.summary.ahead == ahead
    assert result.summary.behind == behind
    assert result.summary.stdout_digest == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_status_mapping_is_unique_and_path_is_not_projected() -> None:
    raw = (
        "## main...origin/main [ahead 1, behind 2]\n"
        "?? untracked-secret.txt\n"
        "M  staged.txt\n"
        " M unstaged.txt\n"
        "MM both.txt\n"
        "UU conflict.txt\n"
        "R  old -> new\n"
        "C  copied.txt\n"
    ).encode()

    result = parse_git_status_output(raw, b"", exit_code=0)

    assert result.status == "pass"
    assert result.summary is not None
    assert result.summary.to_dict() == {
        "dirty": True,
        "entry_count": 7,
        "staged": 4,
        "unstaged": 2,
        "untracked": 1,
        "conflicted": 1,
        "detached": False,
        "ahead": 1,
        "behind": 2,
        "stdout_byte_count": len(raw),
        "stderr_byte_count": 0,
        "stdout_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "stdout_truncated": False,
        "stderr_truncated": False,
    }
    assert "secret" not in str(result.to_dict())
    assert "old -> new" not in str(result.to_dict())


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"## main",
        b"## main\r\n",
        b"## main\n\n",
        b"## main\n!! ignored\n",
        b"## main\n  path\n",
        b"## main\nZZ path\n",
        b"## main\n?? \n",
        b"## main\n## second\n",
        b"## main...origin/main [ahead 01]\n",
        b"## main...origin/main [ahead 0]\n",
        b"## main...origin/main [behind 2147483648]\n",
        b"## bad branch\n",
        b"## main\nM  bad\x00path\n",
    ],
)
def test_invalid_protocol_is_rejected(raw: bytes) -> None:
    result = parse_git_status_output(raw, b"", exit_code=0)

    assert result.status == "validation_failed"
    assert result.summary is None
    assert result.findings[0].rule_id == "execution.output_protocol_invalid"


def test_nonzero_and_stderr_mapping_withhold_content() -> None:
    nonzero = parse_git_status_output(b"secret path\n", b"fatal secret", exit_code=128)
    stderr = parse_git_status_output(b"## main\n", b"warning secret", exit_code=0)

    assert nonzero.status == "blocked"
    assert nonzero.findings[0].rule_id == "execution.child_nonzero"
    assert stderr.status == "validation_failed"
    assert stderr.findings[0].rule_id == "execution.output_protocol_invalid"
    assert "secret" not in str(nonzero.to_dict())
    assert "secret" not in str(stderr.to_dict())


def test_line_and_output_bounds_are_enforced() -> None:
    long_line = b"## main\n?? " + b"a" * 4094 + b"\n"
    too_many = b"## main\n" + b"?? a\n" * 2001
    too_large = b"## main\n" + b"?? a\n" * 14000

    for raw in (long_line, too_many, too_large):
        result = parse_git_status_output(raw, b"", exit_code=0)
        assert result.status == "validation_failed"
        assert result.summary is None

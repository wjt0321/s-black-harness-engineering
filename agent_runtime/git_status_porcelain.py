"""Finite parser for the fixed Git porcelain-v1 status operation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .result import CheckResult, Finding

_MAX_STREAM_BYTES = 65_536
_MAX_LINE_BYTES = 4_096
_MAX_STATUS_LINES = 2_000
_MAX_COUNT = 2_147_483_647
_CONFLICT = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
_INDEX = {" ", "M", "T", "A", "D", "R", "C"}
_WORKTREE = {" ", "M", "T", "D"}
_COUNT_RE = r"(?:[1-9][0-9]{0,9})"
_TRACKING_RE = re.compile(
    rf"^(?P<branch>\S+)\.\.\.(?P<upstream>\S+)"
    rf"(?: \[(?:ahead (?P<ahead>{_COUNT_RE})"
    rf"(?:, behind (?P<ahead_behind>{_COUNT_RE}))?"
    rf"|behind (?P<behind>{_COUNT_RE}))\])?$"
)


@dataclass(frozen=True)
class GitStatusSummary:
    dirty: bool
    entry_count: int
    staged: int
    unstaged: int
    untracked: int
    conflicted: int
    detached: bool
    ahead: int
    behind: int
    stdout_byte_count: int
    stderr_byte_count: int
    stdout_digest: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dirty": self.dirty,
            "entry_count": self.entry_count,
            "staged": self.staged,
            "unstaged": self.unstaged,
            "untracked": self.untracked,
            "conflicted": self.conflicted,
            "detached": self.detached,
            "ahead": self.ahead,
            "behind": self.behind,
            "stdout_byte_count": self.stdout_byte_count,
            "stderr_byte_count": self.stderr_byte_count,
            "stdout_digest": self.stdout_digest,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
        }


@dataclass
class GitStatusParseResult(CheckResult):
    summary: GitStatusSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["summary"] = None if self.summary is None else self.summary.to_dict()
        return payload


def _invalid() -> GitStatusParseResult:
    return GitStatusParseResult(
        status="validation_failed",
        findings=[
            Finding(
                "execution.output_protocol_invalid",
                "error",
                "validation_failed",
                "Fixed Git status output failed protocol validation.",
            )
        ],
        summary=None,
        next_action="Inspect the repository and trusted Git installation.",
    )


def _valid_token(value: str) -> bool:
    return bool(value) and all(
        ord(char) >= 0x21 and ord(char) != 0x7F and not char.isspace()
        for char in value
    )


def _parse_header(line: str) -> tuple[bool, int, int] | None:
    if not line.startswith("## "):
        return None
    value = line[3:]
    if value == "HEAD (no branch)":
        return True, 0, 0
    for prefix in ("No commits yet on ", "Initial commit on "):
        if value.startswith(prefix):
            token = value[len(prefix) :]
            return (False, 0, 0) if _valid_token(token) else None
    tracking = _TRACKING_RE.fullmatch(value)
    if tracking:
        branch = tracking.group("branch")
        upstream = tracking.group("upstream")
        if not _valid_token(branch) or not _valid_token(upstream):
            return None
        ahead_text = tracking.group("ahead")
        behind_text = tracking.group("ahead_behind") or tracking.group("behind")
        ahead = int(ahead_text) if ahead_text else 0
        behind = int(behind_text) if behind_text else 0
        if ahead > _MAX_COUNT or behind > _MAX_COUNT:
            return None
        return False, ahead, behind
    return (False, 0, 0) if _valid_token(value) else None


def parse_git_status_output(
    stdout: bytes,
    stderr: bytes,
    *,
    exit_code: int,
) -> GitStatusParseResult:
    """Validate fixed status output and return a path-free safe summary."""
    if exit_code != 0:
        return GitStatusParseResult(
            status="blocked",
            findings=[
                Finding(
                    "execution.child_nonzero",
                    "block",
                    "blocked",
                    "The fixed Git status child returned a nonzero exit code.",
                )
            ],
            summary=None,
            next_action="Inspect the repository before retrying.",
        )
    if (
        stderr
        or not stdout
        or len(stdout) > _MAX_STREAM_BYTES
        or len(stderr) > _MAX_STREAM_BYTES
        or b"\x00" in stdout
        or b"\r" in stdout
        or not stdout.endswith(b"\n")
        or stdout.endswith(b"\n\n")
    ):
        return _invalid()
    try:
        text = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _invalid()
    lines = text[:-1].split("\n")
    if not lines or len(lines) - 1 > _MAX_STATUS_LINES:
        return _invalid()
    if any(len(line.encode("utf-8")) > _MAX_LINE_BYTES for line in lines):
        return _invalid()
    header = _parse_header(lines[0])
    if header is None:
        return _invalid()
    detached, ahead, behind = header
    staged = unstaged = untracked = conflicted = 0
    for line in lines[1:]:
        if len(line) < 4 or line[2] != " " or line[3:] == "":
            return _invalid()
        pair = line[:2]
        opaque_path = line[3:]
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in opaque_path):
            return _invalid()
        if pair == "??":
            untracked += 1
            continue
        if pair in _CONFLICT:
            conflicted += 1
            continue
        x, y = pair
        if x not in _INDEX or y not in _WORKTREE or pair == "  ":
            return _invalid()
        if x != " ":
            staged += 1
        if y != " ":
            unstaged += 1
    entry_count = len(lines) - 1
    return GitStatusParseResult(
        status="pass",
        summary=GitStatusSummary(
            dirty=entry_count > 0,
            entry_count=entry_count,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            conflicted=conflicted,
            detached=detached,
            ahead=ahead,
            behind=behind,
            stdout_byte_count=len(stdout),
            stderr_byte_count=len(stderr),
            stdout_digest="sha256:" + hashlib.sha256(stdout).hexdigest(),
        ),
        next_action="Use the safe status summary; raw paths remain withheld.",
    )

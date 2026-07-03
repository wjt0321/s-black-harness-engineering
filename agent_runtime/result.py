"""Result model and output formatting for the agent-runtime CLI."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, TextIO


# Exit codes documented in docs/08-minimal-cli-design.md
EXIT_PASS = 0
EXIT_ERROR = 1
EXIT_BLOCKED = 2
EXIT_NEEDS_APPROVAL = 3
EXIT_NEEDS_INPUT = 4
EXIT_VALIDATION_FAILED = 5

_STATUS_TO_EXIT = {
    "pass": EXIT_PASS,
    "warn": EXIT_PASS,
    "blocked": EXIT_BLOCKED,
    "needs_approval": EXIT_NEEDS_APPROVAL,
    "needs_input": EXIT_NEEDS_INPUT,
    "error": EXIT_ERROR,
    "validation_failed": EXIT_VALIDATION_FAILED,
}

SEVERITY_ORDER = {"info": 0, "warn": 1, "block": 2}


@dataclass
class Finding:
    rule_id: str
    severity: str
    action: str
    message: str
    # Optional location / context that does NOT include the full secret match.
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "action": self.action,
            "message": self.message,
        }
        if self.line is not None:
            d["line"] = self.line
        if self.column is not None:
            d["column"] = self.column
        return d


@dataclass
class CheckResult:
    status: str
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def exit_code(self) -> int:
        return _STATUS_TO_EXIT.get(self.status, EXIT_ERROR)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d

    def render_human(self, no_color: bool = False) -> str:
        lines: list[str] = [self.status.upper()]
        for finding in self.findings:
            loc = ""
            if finding.line is not None:
                loc = f" at line {finding.line}"
                if finding.column is not None:
                    loc += f", col {finding.column}"
            lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
        if self.next_action:
            lines.append(f"Next: {self.next_action}")
        return "\n".join(lines)

    def render_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def coalesce_status(statuses: list[str]) -> str:
    """Return the most severe status from a list of statuses."""
    if not statuses:
        return "pass"
    order = [("pass", 0), ("warn", 1), ("needs_input", 2), ("needs_approval", 3), ("blocked", 4), ("error", 5)]
    rank = {name: idx for name, idx in order}
    ranked = [(s, rank.get(s, -1)) for s in statuses]
    ranked.sort(key=lambda x: x[1])
    return ranked[-1][0]


def emit(result: CheckResult, json_output: bool = False, no_color: bool = False, out: TextIO | None = None) -> int:
    """Print a result and return the appropriate exit code."""
    stream = out if out is not None else sys.stdout
    if json_output:
        stream.write(result.render_json() + "\n")
    else:
        stream.write(result.render_human(no_color=no_color) + "\n")
    return result.exit_code()

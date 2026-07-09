"""Controlled task submit command for orchestration namespace.

This module provides a control-plane-facing wrapper over
``runtime task create --dry-run / --commit``.

It keeps the same safety boundary:

* dry-run does not write any ledger files;
* commit appends exactly one task JSON object to the task ledger;
* no automatic event append, routing, preflight, or adapter execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .result import CheckResult
from .runtime_task_create import create_task, create_task_dry_run


def submit_task(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
    dry_run: bool = False,
    commit: bool = False,
    tasks_file: str | None = None,
    events_file: str | None = None,
    candidate: dict[str, Any] | None = None,
) -> CheckResult:
    """Submit a task through the orchestration namespace.

    First version is a thin wrapper over ``runtime task create`` so the
    controlled-write primitive, schema validation, rollback, and scan rules all
    remain identical to the runtime layer.
    """
    if dry_run and commit:
        return CheckResult(
            status="error",
            findings=[],
            next_action="Choose exactly one mode: --dry-run or --commit.",
        )

    if dry_run:
        result = create_task_dry_run(
            root,
            file=file,
            stdin=stdin,
            dry_run=True,
            tasks_file=tasks_file,
            events_file=events_file,
            candidate=candidate,
        )
        if hasattr(result, "next_action") and result.status == "pass":
            result.next_action = (
                "Dry-run passed. Re-run with --commit to submit the task, or continue with orchestration route preview once persisted."
            )
        return result

    if commit:
        result = create_task(
            root,
            file=file,
            stdin=stdin,
            commit=True,
            tasks_file=tasks_file,
            events_file=events_file,
            candidate=candidate,
        )
        if hasattr(result, "next_action") and result.status == "pass":
            result.next_action = (
                "Task submitted. Continue with orchestration route preview or orchestration preflight next."
            )
        return result

    return CheckResult(
        status="error",
        findings=[],
        next_action="Provide exactly one mode: --dry-run or --commit.",
    )

"""Controlled task submit command for orchestration namespace.

This module provides a control-plane-facing wrapper over the runtime
controlled-write primitives. A submit is now an A+B transaction:

* A = append exactly one task JSON object to the task ledger;
* B = append exactly one ``created`` event JSON object to the events ledger;
* both writes happen only under ``--commit``;
* any failure after A rolls B (or the attempted B) back, then rolls A back to
  the original byte size.

It keeps the same safety boundary:

* dry-run does not write any ledger files;
* no automatic routing, preflight, or adapter execution;
* no network access, messaging, or credential files.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger_consistency import check_ledger_consistency
from .loader import is_safe_to_read, normalize_path
from .result import CheckResult, Finding
from .runtime_event_append import append_event
from .runtime_task_create import _load_candidate_task, create_task
from .task_validation import validate_records


@dataclass
class TaskSubmitResult(CheckResult):
    """Result of an orchestration task submit dry-run or commit.

    The summary only exposes safe identifiers and status/count fields. It does
    not include the task title, summary, evidence descriptions, event message,
    or any free-text payload.
    """

    source: str | None = None
    task_id: str | None = None
    event_id: str | None = None
    task_status: str | None = None
    title_present: bool = False
    assignee_present: bool = False
    tag_count: int | None = None
    artifact_count: int | None = None
    evidence_count: int | None = None
    would_create: bool = False
    would_append_created_event: bool = False
    ledger_check: str | None = None
    metadata_keys: list[str] = field(default_factory=list)
    committed: bool = False
    created_event_committed: bool = False
    post_validate_tasks: str | None = None
    post_validate_events: str | None = None
    post_ledger_check: str | None = None
    rolled_back: bool = False
    rollback_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.source is not None:
            d["source"] = self.source
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.event_id is not None:
            d["event_id"] = self.event_id
        if self.task_status is not None:
            d["task_status"] = self.task_status
        d["title_present"] = self.title_present
        d["assignee_present"] = self.assignee_present
        if self.tag_count is not None:
            d["tag_count"] = self.tag_count
        if self.artifact_count is not None:
            d["artifact_count"] = self.artifact_count
        if self.evidence_count is not None:
            d["evidence_count"] = self.evidence_count
        d["would_create"] = self.would_create
        d["would_append_created_event"] = self.would_append_created_event
        if self.ledger_check is not None:
            d["ledger_check"] = self.ledger_check
        if self.metadata_keys:
            d["metadata_keys"] = self.metadata_keys
        d["committed"] = self.committed
        d["created_event_committed"] = self.created_event_committed
        if self.post_validate_tasks is not None:
            d["post_validate_tasks"] = self.post_validate_tasks
        if self.post_validate_events is not None:
            d["post_validate_events"] = self.post_validate_events
        if self.post_ledger_check is not None:
            d["post_ledger_check"] = self.post_ledger_check
        d["rolled_back"] = self.rolled_back
        if self.rollback_error is not None:
            d["rollback_error"] = self.rollback_error
        return d


_TASK_ID_RE = re.compile(r"^task-([0-9]{8})-([0-9]{3,})$")
_EVENT_ID_RE = re.compile(r"^evt-[0-9]{8}-[0-9]{3,}$")


def _load_existing_event_ids(root: Path, events_file: str | None) -> set[str]:
    """Collect event_id values already present in the target events ledger."""
    events_path = (root / (events_file or "tasks/events.jsonl")).resolve()
    event_ids: set[str] = set()
    if not events_path.is_file() or not is_safe_to_read(events_path):
        return event_ids
    with open(events_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                event_id = record.get("event_id")
                if event_id and _EVENT_ID_RE.match(str(event_id)):
                    event_ids.add(str(event_id))
    return event_ids


def _generate_event_id(root: Path, task_id: str, events_file: str | None) -> str:
    """Generate a unique created event id derived from the task id.

    ``task-YYYYMMDD-NNN`` becomes ``evt-YYYYMMDD-NNN001``; if that id already
    exists in the events ledger, the trailing digits are incremented.
    """
    match = _TASK_ID_RE.match(task_id)
    if match:
        date_part = match.group(1)
        seq_part = match.group(2)
        base = f"evt-{date_part}-{seq_part}001"
    else:
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        base = f"evt-{date_part}-000001"

    existing = _load_existing_event_ids(root, events_file)
    if base not in existing:
        return base

    # Increment trailing digits while keeping the schema pattern.
    for i in range(2, 10000):
        candidate = f"{base[:-3]}{i:03d}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("Could not generate a unique event id")


def _build_created_event(
    root: Path,
    task_id: str,
    task_status: str,
    candidate: dict[str, Any],
    events_file: str | None,
) -> dict[str, Any]:
    """Build a safe created event for the newly submitted task.

    Metadata only contains safe identifiers and counts; it never includes the
    task title, summary, absolute paths, or free-text payloads.
    """
    actor = candidate.get("created_by") or "cli"
    source = candidate.get("source") or "cli"
    return {
        "event_id": _generate_event_id(root, task_id, events_file),
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "event_type": "created",
        "from_status": None,
        "to_status": task_status,
        "message": "Task submitted.",
        "metadata": {
            "source": source,
            "actor": actor,
            "submit_method": "orchestration_task_submit",
        },
    }


def _rel_to_root(root: Path, path: Path) -> str:
    return normalize_path(path.resolve().relative_to(root.resolve()))


def _simulate_ab_append_and_check(
    root: Path,
    candidate: dict[str, Any],
    created_event: dict[str, Any],
    tasks_path: Path,
    events_path: Path,
) -> CheckResult:
    """Simulate appending both task and created event, then run ledger checks.

    Creates temporary ledger files containing the existing records plus the
    candidate task and created event. The temp files are always cleaned up.
    """
    existing_task_lines: list[str] = []
    if tasks_path.is_file():
        existing_task_lines = tasks_path.read_text(encoding="utf-8").splitlines()

    existing_event_lines: list[str] = []
    if events_path.is_file():
        existing_event_lines = events_path.read_text(encoding="utf-8").splitlines()

    tmp_tasks_name: str | None = None
    tmp_events_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
        ) as tmp_tasks:
            for line in existing_task_lines:
                tmp_tasks.write(line + "\n")
            tmp_tasks.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            tmp_tasks_name = tmp_tasks.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
        ) as tmp_events:
            for line in existing_event_lines:
                tmp_events.write(line + "\n")
            tmp_events.write(json.dumps(created_event, ensure_ascii=False) + "\n")
            tmp_events_name = tmp_events.name

        return check_ledger_consistency(
            root,
            tasks_file=_rel_to_root(root, Path(tmp_tasks_name)),
            events_file=_rel_to_root(root, Path(tmp_events_name)),
        )
    finally:
        if tmp_tasks_name:
            Path(tmp_tasks_name).unlink(missing_ok=True)
        if tmp_events_name:
            Path(tmp_events_name).unlink(missing_ok=True)


def _rollback_file(path: Path, original_size: int, created: bool) -> tuple[bool, str | None]:
    try:
        if created:
            path.unlink(missing_ok=True)
        else:
            with open(path, "r+b") as fh:
                fh.truncate(original_size)
        return True, None
    except OSError as exc:
        return False, str(exc)


def _candidate_summary(
    *,
    status: str,
    source: str,
    candidate: dict[str, Any],
    task_id: str,
    event_id: str | None,
    ledger_check: str | None,
    would_create: bool,
    would_append_created_event: bool,
    committed: bool,
    created_event_committed: bool,
    next_action: str,
    findings: list[Finding] | None = None,
    post_validate_tasks: str | None = None,
    post_validate_events: str | None = None,
    post_ledger_check: str | None = None,
    rolled_back: bool = False,
    rollback_error: str | None = None,
) -> TaskSubmitResult:
    title = candidate.get("title")
    assignee = candidate.get("assignee")
    tags = candidate.get("tags")
    artifacts = candidate.get("artifacts")
    evidence = candidate.get("evidence")
    metadata = candidate.get("metadata")
    return TaskSubmitResult(
        status=status,
        findings=findings or [],
        source=source,
        task_id=task_id,
        event_id=event_id,
        task_status=candidate.get("status"),
        title_present=isinstance(title, str) and len(title) > 0,
        assignee_present=assignee is not None,
        tag_count=len(tags) if isinstance(tags, list) else None,
        artifact_count=len(artifacts) if isinstance(artifacts, list) else None,
        evidence_count=len(evidence) if isinstance(evidence, list) else None,
        would_create=would_create,
        would_append_created_event=would_append_created_event,
        ledger_check=ledger_check,
        metadata_keys=sorted(metadata.keys()) if isinstance(metadata, dict) else [],
        committed=committed,
        created_event_committed=created_event_committed,
        post_validate_tasks=post_validate_tasks,
        post_validate_events=post_validate_events,
        post_ledger_check=post_ledger_check,
        rolled_back=rolled_back,
        rollback_error=rollback_error,
        next_action=next_action,
    )


def _resolve_ledger_path(
    root: Path, file: str | None, default: str, label: str
) -> CheckResult | Path:
    """Validate that a ledger file path is inside root and a safe JSONL file."""
    path = (root / (file or default)).resolve()
    if path != root and root not in path.parents:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id=f"{label}-file-outside-root",
                    severity="error",
                    action="error",
                    message=f"{label} file must be inside the project root.",
                )
            ],
            next_action=f"Choose a project-local JSONL {label} ledger.",
        )
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & {".git", "credential", "credentials", "secret", "secrets"}:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id=f"unsafe-{label}-file",
                    severity="error",
                    action="error",
                    message=f"{label} file must not point to git internals or credential paths.",
                )
            ],
            next_action=f"Choose a safe project-local .jsonl {label} ledger path.",
        )
    if not is_safe_to_read(path) or path.suffix.lower() != ".jsonl":
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id=f"unsafe-{label}-file",
                    severity="error",
                    action="error",
                    message=f"{label} file must be a safe JSONL file.",
                )
            ],
            next_action=f"Choose a safe .jsonl {label} ledger path.",
        )
    return path


def _is_blocked_for_commit(path: Path, label: str) -> CheckResult | None:
    """Early safety checks before any ledger write."""
    if not _has_trailing_newline(path):
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id=f"{label}-file-missing-trailing-newline",
                    severity="block",
                    action="deny",
                    message=f"{label} file must end with a newline before append.",
                )
            ],
            next_action=f"Fix the {label} ledger newline explicitly, then retry the submit.",
        )
    if not path.parent.is_dir():
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id=f"{label}-parent-missing",
                    severity="block",
                    action="deny",
                    message=f"{label} file parent directory must already exist.",
                )
            ],
            next_action=f"Create the {label} ledger directory explicitly before committing a submit.",
        )
    return None


def _has_trailing_newline(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return True
    with open(path, "rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) == b"\n"


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

    ``--dry-run`` previews the A+B append without writing. ``--commit`` appends
    exactly one task snapshot to the task ledger and exactly one ``created``
    event to the events ledger; if any post-write check fails, both ledgers are
    rolled back to their original byte sizes.
    """
    if dry_run and commit:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="dry-run-commit-mutually-exclusive",
                    severity="error",
                    action="error",
                    message="--dry-run and --commit are mutually exclusive.",
                )
            ],
            next_action="Choose exactly one mode: --dry-run or --commit.",
        )

    if not dry_run and not commit:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-submit-mode",
                    severity="error",
                    action="error",
                    message="Provide exactly one mode: --dry-run or --commit.",
                )
            ],
            next_action="Provide --dry-run or --commit.",
        )

    root = root.resolve()

    if commit and events_file is None:
        return _candidate_summary(
            status="needs_input",
            source="candidate",
            candidate=candidate or {},
            task_id=(candidate.get("id") if isinstance(candidate, dict) else None) or "unknown",
            event_id=None,
            ledger_check=None,
            would_create=False,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action="Provide --events-file <path> when using --commit.",
            findings=[
                Finding(
                    rule_id="missing-events-file",
                    severity="error",
                    action="needs_input",
                    message="--events-file is required for --commit.",
                )
            ],
        )

    # Load the candidate task once so we can reuse it for A pre-check, B event
    # generation, combined simulation, and result reporting.
    if candidate is not None:
        candidate_used = candidate
        source = "candidate"
    else:
        loaded = _load_candidate_task(root, file=file, stdin=stdin)
        if isinstance(loaded, CheckResult):
            return loaded
        candidate_used, source = loaded

    # Resolve ledger paths early so we can run combined pre-checks and rollback.
    tasks_path_resolved = _resolve_ledger_path(
        root, tasks_file, "tasks/tasks.jsonl", "tasks"
    )
    if isinstance(tasks_path_resolved, CheckResult):
        return tasks_path_resolved
    events_path_resolved = _resolve_ledger_path(
        root, events_file, "tasks/events.jsonl", "events"
    )
    if isinstance(events_path_resolved, CheckResult):
        return events_path_resolved

    # A pre-check: reuse runtime_task_create in dry-run mode.
    pre_a = create_task(
        root,
        file=None,
        stdin=False,
        commit=False,
        tasks_file=tasks_file,
        events_file=events_file,
        candidate=candidate_used,
    )
    if pre_a.status in ("error", "validation_failed", "blocked"):
        return _candidate_summary(
            status=pre_a.status,
            source=source,
            candidate=candidate_used,
            task_id=candidate_used.get("id") or "unknown",
            event_id=None,
            ledger_check=None,
            would_create=False,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action=pre_a.next_action or "Fix the task candidate before retrying.",
            findings=list(pre_a.findings),
        )

    task_id = pre_a.task_id
    task_status = pre_a.task_status

    # Build the created event candidate for B.
    created_event = _build_created_event(
        root, task_id or "unknown", task_status or "planned", candidate_used, events_file
    )

    # Combined A+B pre-check via temp ledgers.
    combined_check = _simulate_ab_append_and_check(
        root,
        candidate_used,
        created_event,
        tasks_path_resolved,
        events_path_resolved,
    )
    if combined_check.status == "error":
        return CheckResult(
            status="error",
            findings=list(combined_check.findings),
            next_action="Fix ledger file paths before retrying.",
        )

    ledger_check = combined_check.status
    if combined_check.status == "validation_failed":
        findings = [
            Finding(
                rule_id=finding.rule_id,
                severity=finding.severity,
                action=finding.action,
                message=f"Ledger consistency: {finding.message}",
                line=finding.line,
                column=finding.column,
            )
            for finding in combined_check.findings
        ]
        return _candidate_summary(
            status="validation_failed",
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=False,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action="Fix the reported issues before submitting the task.",
            findings=findings,
        )

    if dry_run:
        return _candidate_summary(
            status="pass",
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=True,
            would_append_created_event=True,
            committed=False,
            created_event_committed=False,
            next_action="Dry-run passed. Re-run with --commit to persist the task and created event.",
        )

    # Commit path from here on.
    early_block = _is_blocked_for_commit(tasks_path_resolved, "tasks")
    if early_block is not None:
        return _candidate_summary(
            status=early_block.status,
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=False,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action=early_block.next_action or "Fix the task ledger before retrying.",
            findings=list(early_block.findings),
        )
    early_block = _is_blocked_for_commit(events_path_resolved, "events")
    if early_block is not None:
        return _candidate_summary(
            status=early_block.status,
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=False,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action=early_block.next_action or "Fix the events ledger before retrying.",
            findings=list(early_block.findings),
        )

    tasks_existed = tasks_path_resolved.exists()
    events_existed = events_path_resolved.exists()
    original_tasks_size = tasks_path_resolved.stat().st_size if tasks_existed else 0
    original_events_size = events_path_resolved.stat().st_size if events_existed else 0

    # A: append task.
    result_a = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file=tasks_file,
        events_file=events_file,
        candidate=candidate_used,
    )
    if result_a.status in ("error", "validation_failed", "blocked"):
        # create_task rolls back its own append on failure.
        return _candidate_summary(
            status=result_a.status,
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=True,
            would_append_created_event=False,
            committed=False,
            created_event_committed=False,
            next_action=result_a.next_action or "Task append failed; retry after fixing the issue.",
            findings=list(result_a.findings),
            rolled_back=getattr(result_a, "rolled_back", False),
            rollback_error=getattr(result_a, "rollback_error", None),
        )

    # B: append created event.
    result_b = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file=tasks_file,
        events_file=events_file,
        envelope_file=None,
        candidate=created_event,
    )
    if result_b.status in ("error", "validation_failed", "blocked"):
        # append_event rolls back its own event append on failure; we still need
        # to roll back the task ledger.
        rollback_ok, rollback_error = _rollback_file(
            tasks_path_resolved, original_tasks_size, created=not tasks_existed
        )
        return _candidate_summary(
            status="error" if not rollback_ok else result_b.status,
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=True,
            would_append_created_event=True,
            committed=False,
            created_event_committed=False,
            next_action=(
                "Created event append failed and task ledger rollback succeeded. Fix the issue before retrying."
                if rollback_ok
                else "Created event append failed and task ledger rollback failed. Restore the task ledger manually."
            ),
            findings=list(result_b.findings),
            rolled_back=rollback_ok,
            rollback_error=rollback_error,
        )

    # Combined post-check on the real persisted ledgers.
    post_validate_tasks = validate_records(
        root, _rel_to_root(root, tasks_path_resolved), "task"
    )
    post_validate_events = validate_records(
        root, _rel_to_root(root, events_path_resolved), "event"
    )
    post_ledger = check_ledger_consistency(
        root,
        tasks_file=_rel_to_root(root, tasks_path_resolved),
        events_file=_rel_to_root(root, events_path_resolved),
    )

    failures: list[Finding] = []
    if post_validate_tasks.status != "pass":
        failures.extend(post_validate_tasks.findings)
    if post_validate_events.status != "pass":
        failures.extend(post_validate_events.findings)
    if post_ledger.status != "pass":
        failures.extend(post_ledger.findings)

    if not failures:
        return _candidate_summary(
            status="pass",
            source=source,
            candidate=candidate_used,
            task_id=task_id or "unknown",
            event_id=created_event.get("event_id"),
            ledger_check=ledger_check,
            would_create=True,
            would_append_created_event=True,
            committed=True,
            created_event_committed=True,
            post_validate_tasks=post_validate_tasks.status,
            post_validate_events=post_validate_events.status,
            post_ledger_check=post_ledger.status,
            next_action="Task and created event submitted. Continue with orchestration route preview or preflight next.",
        )

    # Post-check failed: roll back both ledgers.
    rollback_events_ok, rollback_events_err = _rollback_file(
        events_path_resolved, original_events_size, created=not events_existed
    )
    rollback_tasks_ok, rollback_tasks_err = _rollback_file(
        tasks_path_resolved, original_tasks_size, created=not tasks_existed
    )
    rollback_error_parts: list[str] = []
    if not rollback_events_ok:
        rollback_error_parts.append(f"events rollback failed: {rollback_events_err}")
    if not rollback_tasks_ok:
        rollback_error_parts.append(f"tasks rollback failed: {rollback_tasks_err}")
    rollback_error = "; ".join(rollback_error_parts) if rollback_error_parts else None

    return _candidate_summary(
        status="error" if (not rollback_events_ok or not rollback_tasks_ok) else "validation_failed",
        source=source,
        candidate=candidate_used,
        task_id=task_id or "unknown",
        event_id=created_event.get("event_id"),
        ledger_check=ledger_check,
        would_create=True,
        would_append_created_event=True,
        committed=False,
        created_event_committed=False,
        post_validate_tasks=post_validate_tasks.status,
        post_validate_events=post_validate_events.status,
        post_ledger_check=post_ledger.status,
        next_action=(
            "Post-submit checks failed and rollback succeeded. Fix the issue before retrying."
            if (rollback_events_ok and rollback_tasks_ok)
            else "Post-submit checks failed and rollback failed. Restore the ledgers manually."
        ),
        findings=failures,
        rolled_back=rollback_events_ok and rollback_tasks_ok,
        rollback_error=rollback_error,
    )

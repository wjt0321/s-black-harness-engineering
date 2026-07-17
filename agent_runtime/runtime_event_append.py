"""Dry-run and commit append for task events.

This module implements a narrow controlled-write boundary:

* ``runtime event append --dry-run`` simulates appending a candidate event and
  reports whether the append would be safe. No ledger files are modified.
* ``runtime event append --commit`` appends exactly one JSON object as the last
  line of an event ledger JSONL file, then validates the resulting ledger and
  rolls back this command's append if a post-check fails.

No adapter execution, network access, messaging, or credential files are
involved.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .ledger_consistency import check_ledger_consistency
from .loader import is_safe_to_read, load_schema, normalize_path
from .policy import check_text
from .result import CheckResult, Finding
from .runtime_ledger import check_runtime_ledger
from .task_validation import validate_records
from .tasks import find_task

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_public_scan_spec = importlib.util.spec_from_file_location(
    "public_scan", _TOOLS_DIR / "public_scan.py"
)
_public_scan = importlib.util.module_from_spec(_public_scan_spec)
_public_scan_spec.loader.exec_module(_public_scan)
_PUBLIC_SCAN_RULES: list[dict[str, str]] = _public_scan.SCAN_RULES



@dataclass
class EventAppendDryRunResult(CheckResult):
    """Result of simulating a task event append.

    The summary only exposes safe identifiers and status fields. It does not
    include the event message, metadata values, artifacts, evidence payloads,
    or any raw adapter payload.
    """

    source: str | None = None
    event_id: str | None = None
    task_id: str | None = None
    event_type: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    would_append: bool = False
    ledger_check: str | None = None
    runtime_audit: str | None = None
    metadata_keys: list[str] = field(default_factory=list)
    artifact_count: int | None = None
    committed: bool = False
    post_validate: str | None = None
    post_ledger_check: str | None = None
    post_runtime_audit: str | None = None
    rolled_back: bool = False
    rollback_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.source is not None:
            d["source"] = self.source
        if self.event_id is not None:
            d["event_id"] = self.event_id
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.event_type is not None:
            d["event_type"] = self.event_type
        if self.from_status is not None:
            d["from_status"] = self.from_status
        if self.to_status is not None:
            d["to_status"] = self.to_status
        d["would_append"] = self.would_append
        if self.ledger_check is not None:
            d["ledger_check"] = self.ledger_check
        if self.runtime_audit is not None:
            d["runtime_audit"] = self.runtime_audit
        if self.metadata_keys:
            d["metadata_keys"] = self.metadata_keys
        if self.artifact_count is not None:
            d["artifact_count"] = self.artifact_count
        d["committed"] = self.committed
        if self.post_validate is not None:
            d["post_validate"] = self.post_validate
        if self.post_ledger_check is not None:
            d["post_ledger_check"] = self.post_ledger_check
        if self.post_runtime_audit is not None:
            d["post_runtime_audit"] = self.post_runtime_audit
        d["rolled_back"] = self.rolled_back
        if self.rollback_error is not None:
            d["rollback_error"] = self.rollback_error
        return d


VALID_EVENT_TYPES = {
    "created",
    "status_changed",
    "assigned",
    "progress",
    "blocked",
    "unblocked",
    "artifact_added",
    "evidence_added",
    "finished",
    "failed",
}

RESERVED_EXECUTION_EVENT_TYPES = frozenset(
    {
        "execution_attempt_started",
        "execution_succeeded",
        "execution_failed",
        "execution_cancelled",
    }
)


def reserved_execution_event_type_finding(
    candidate: dict[str, Any], *, line: int | None = None
) -> Finding | None:
    """Return a value-safe finding when a generic entry uses a reserved type."""
    event_type = candidate.get("event_type")
    if not isinstance(event_type, str) or event_type not in RESERVED_EXECUTION_EVENT_TYPES:
        return None
    return Finding(
        rule_id="reserved-execution-event-type",
        severity="block",
        action="deny",
        message="Execution lifecycle events require the dedicated audit writer.",
        line=line,
    )


def _line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _public_scan_text(text: str) -> list[Finding]:
    """Run public-release risk rules over a text string.

    Findings include the rule id and line number but never the matched text.
    """
    findings: list[Finding] = []
    for rule in _PUBLIC_SCAN_RULES:
        compiled = re.compile(rule["regex"])
        for match in compiled.finditer(text):
            line = _line_number(text, match.start())
            findings.append(
                Finding(
                    rule_id=rule["id"],
                    severity="block",
                    action="deny",
                    message=f"Public scan rule hit at line {line}: {rule['title']}",
                    line=line,
                )
            )
    return findings


def _scan_candidate_content(root: Path, candidate: dict[str, Any]) -> list[Finding]:
    """Run policy secret scan and public-release scan over the serialized event."""
    text = json.dumps(candidate, ensure_ascii=False, indent=2)
    findings: list[Finding] = []
    secret_result = check_text(root, text)
    for finding in secret_result.findings:
        # Override message so the matched secret is never echoed.
        finding.message = (
            f"Secret scan rule hit at line {finding.line or '?'}: {finding.rule_id}"
        )
        findings.append(finding)
    findings.extend(_public_scan_text(text))
    return findings


def _safe_event_schema_error(exc: JsonSchemaValidationError) -> str:
    """Return a short, value-free validation error summary."""
    path = ".".join(str(part) for part in exc.path) if exc.path else "(root)"
    validator = exc.validator or "schema"
    if validator == "required":
        parts = exc.message.split("'")
        field = parts[1] if len(parts) >= 2 else path
        return f"required field missing: {field}"
    if validator == "enum":
        return f"value not in allowed enum at {path}"
    if validator == "type":
        return f"type mismatch at {path}"
    if validator == "pattern":
        return f"pattern mismatch at {path}"
    if validator == "additionalProperties":
        return f"unexpected field at {path}"
    if validator == "format":
        return f"format error at {path}"
    return f"validation failed at {path}"


def _validate_event_schema(root: Path, candidate: dict[str, Any]) -> CheckResult | None:
    """Validate a candidate event against tasks/event.schema.json."""
    schema = load_schema(root, "tasks/event.schema.json")
    try:
        validate(instance=candidate, schema=schema)
    except JsonSchemaValidationError as exc:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="event-schema-validation-failed",
                    severity="error",
                    action="error",
                    message=_safe_event_schema_error(exc),
                )
            ],
            next_action="Fix the candidate event to match tasks/event.schema.json.",
        )
    return None


def _load_candidate_event(
    root: Path, file: str | None, stdin: bool
) -> CheckResult | tuple[dict[str, Any], str]:
    """Load a candidate event from a file or stdin."""
    if file is not None:
        path = (root / file).resolve()
        if path != root and root not in path.parents:
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-outside-root",
                        severity="error",
                        action="error",
                        message="Candidate file must be inside project root.",
                    )
                ],
                next_action="Choose a project-local candidate JSON file.",
            )
        if not is_safe_to_read(path) or path.suffix.lower() != ".json":
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="unsafe-candidate-file",
                        severity="error",
                        action="error",
                        message="Candidate file must be a safe JSON file.",
                    )
                ],
                next_action="Choose a safe .json candidate file.",
            )
        if not path.is_file():
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-not-found",
                        severity="error",
                        action="error",
                        message=f"Candidate file not found: {file}",
                    )
                ],
                next_action="Check the candidate file path.",
            )
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-invalid-json",
                        severity="error",
                        action="error",
                        message=f"Invalid JSON in candidate file: {exc.msg}",
                    )
                ],
                next_action="Fix the candidate JSON syntax.",
            )
        if not isinstance(candidate, dict):
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-not-object",
                        severity="error",
                        action="error",
                        message="Candidate event must be a JSON object.",
                    )
                ],
                next_action="Provide a single event object as JSON.",
            )
        return candidate, normalize_path(path.relative_to(root))

    if stdin:
        raw = sys.stdin.read()
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError as exc:
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-invalid-json",
                        severity="error",
                        action="error",
                        message=f"Invalid JSON from stdin: {exc.msg}",
                    )
                ],
                next_action="Fix the candidate JSON syntax.",
            )
        if not isinstance(candidate, dict):
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-not-object",
                        severity="error",
                        action="error",
                        message="Candidate event must be a JSON object.",
                    )
                ],
                next_action="Provide a single event object as JSON.",
            )
        return candidate, "stdin"

    return CheckResult(
        status="error",
        findings=[
            Finding(
                rule_id="missing-source",
                severity="error",
                action="error",
                message="Provide either --file or --stdin.",
            )
        ],
        next_action="Add --file <path> or --stdin.",
    )


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
                if event_id:
                    event_ids.add(event_id)
    return event_ids


def _simulate_append_and_check(
    root: Path,
    candidate: dict[str, Any],
    tasks_file: str | None,
    events_file: str | None,
    envelope_file: str | None,
) -> tuple[CheckResult, CheckResult | None]:
    """Write a temp JSONL with existing events + candidate and run checks."""
    events_path = (root / (events_file or "tasks/events.jsonl")).resolve()
    tasks_path = (root / (tasks_file or "tasks/tasks.jsonl")).resolve()

    existing_lines: list[str] = []
    if events_path.is_file() and is_safe_to_read(events_path):
        existing_lines = events_path.read_text(encoding="utf-8").splitlines()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
    ) as tmp:
        for line in existing_lines:
            tmp.write(line + "\n")
        tmp.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        tmp_name = tmp.name

    try:
        tmp_rel = normalize_path(Path(tmp_name).relative_to(root))
        ledger_result = check_ledger_consistency(
            root,
            tasks_file=normalize_path(tasks_path.relative_to(root)),
            events_file=tmp_rel,
        )
        audit_result: CheckResult | None = None
        if envelope_file:
            audit_result = check_runtime_ledger(
                root,
                tasks_file=normalize_path(tasks_path.relative_to(root)),
                events_file=tmp_rel,
                envelope_file=envelope_file,
            )
        return ledger_result, audit_result
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def _candidate_summary(
    *,
    status: str,
    source: str,
    candidate: dict[str, Any],
    task_id: str,
    ledger_check: str | None,
    runtime_audit: str | None,
    would_append: bool,
    committed: bool,
    next_action: str,
    findings: list[Finding] | None = None,
) -> EventAppendDryRunResult:
    metadata = candidate.get("metadata")
    artifacts = candidate.get("artifacts")
    return EventAppendDryRunResult(
        status=status,
        findings=findings or [],
        source=source,
        event_id=candidate.get("event_id"),
        task_id=task_id,
        event_type=candidate.get("event_type"),
        from_status=candidate.get("from_status"),
        to_status=candidate.get("to_status"),
        would_append=would_append,
        ledger_check=ledger_check,
        runtime_audit=runtime_audit,
        metadata_keys=sorted(metadata.keys()) if isinstance(metadata, dict) else [],
        artifact_count=len(artifacts) if isinstance(artifacts, list) else None,
        committed=committed,
        next_action=next_action,
    )


def _prepare_append(
    root: Path,
    file: str | None,
    stdin: bool,
    tasks_file: str | None,
    events_file: str | None,
    envelope_file: str | None,
    candidate: dict[str, Any] | None,
) -> CheckResult | tuple[dict[str, Any], str, str, str | None, str | None]:
    """Run all write-before checks and return the safe candidate summary state."""
    if candidate is not None:
        source = "candidate"
    else:
        loaded = _load_candidate_event(root, file=file, stdin=stdin)
        if isinstance(loaded, CheckResult):
            return loaded
        candidate, source = loaded

    reserved_finding = reserved_execution_event_type_finding(candidate)
    if reserved_finding is not None:
        return CheckResult(
            status="blocked",
            findings=[reserved_finding],
            next_action="Use the dedicated execution audit writer for reserved lifecycle events.",
        )

    schema_result = _validate_event_schema(root, candidate)
    if schema_result is not None:
        return schema_result

    task_id = candidate.get("task_id")
    if not task_id:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="missing-task-id",
                    severity="error",
                    action="error",
                    message="Candidate event is missing task_id.",
                )
            ],
            next_action="Add a task_id to the candidate event.",
        )

    candidate_event_id = candidate.get("event_id")
    existing_event_ids = _load_existing_event_ids(root, events_file)
    if candidate_event_id in existing_event_ids:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="duplicate-event-id",
                    severity="error",
                    action="error",
                    message="event_id already exists in the target events ledger.",
                )
            ],
            next_action="Use a unique event_id for the candidate event.",
        )

    task = find_task(root, task_id, explicit_file=tasks_file)
    if task is None:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unknown-task-id",
                    severity="error",
                    action="error",
                    message=f"task_id {task_id} not found in task ledger.",
                )
            ],
            next_action="Append only events for existing tasks.",
        )

    scan_findings = _scan_candidate_content(root, candidate)
    if scan_findings:
        return CheckResult(
            status="blocked",
            findings=scan_findings,
            next_action="Redact sensitive or public-release-risk content before appending.",
        )

    ledger_result, audit_result = _simulate_append_and_check(
        root, candidate, tasks_file, events_file, envelope_file
    )

    if ledger_result.status == "error":
        return CheckResult(
            status="error",
            findings=list(ledger_result.findings),
            next_action="Fix ledger file paths before retrying.",
        )

    findings: list[Finding] = []
    ledger_check = ledger_result.status
    runtime_audit = None

    if ledger_result.status == "validation_failed":
        for finding in ledger_result.findings:
            finding.message = f"Ledger consistency: {finding.message}"
            findings.append(finding)

    if audit_result is not None:
        runtime_audit = audit_result.status
        if audit_result.status in ("error", "validation_failed"):
            for finding in audit_result.findings:
                finding.message = f"Runtime audit: {finding.message}"
                findings.append(finding)

    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Fix the reported issues before appending the event.",
        )

    return candidate, source, task_id, ledger_check, runtime_audit


def _resolve_commit_events_path(root: Path, events_file: str | None) -> CheckResult | Path:
    events_path = (root / (events_file or "tasks/events.jsonl")).resolve()
    if events_path != root and root not in events_path.parents:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="events-file-outside-root",
                    severity="error",
                    action="error",
                    message="Events file must be inside the project root.",
                )
            ],
            next_action="Choose a project-local JSONL event ledger.",
        )
    if not is_safe_to_read(events_path) or events_path.suffix.lower() != ".jsonl":
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsafe-events-file",
                    severity="error",
                    action="error",
                    message="Events file must be a safe JSONL file.",
                )
            ],
            next_action="Choose a safe .jsonl event ledger path.",
        )
    rel = normalize_path(events_path.relative_to(root))
    if rel in {"tasks/examples.jsonl", "tasks/events.examples.jsonl"}:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="sample-ledger-write-blocked",
                    severity="error",
                    action="error",
                    message="Sample event ledgers are not valid commit targets.",
                )
            ],
            next_action="Use tasks/events.jsonl or another project-local runtime ledger.",
        )
    return events_path


def _has_trailing_newline(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return True
    with open(path, "rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) == b"\n"


def _rel_to_root(root: Path, path: Path) -> str:
    return normalize_path(path.resolve().relative_to(root.resolve()))


def _rollback_events_file(path: Path, original_size: int, created: bool) -> tuple[bool, str | None]:
    try:
        if created:
            path.unlink(missing_ok=True)
        else:
            with open(path, "r+b") as fh:
                fh.truncate(original_size)
        return True, None
    except OSError as exc:
        return False, str(exc)


def append_event(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
    commit: bool = False,
    tasks_file: str | None = None,
    events_file: str | None = None,
    envelope_file: str | None = None,
    candidate: dict[str, Any] | None = None,
) -> CheckResult:
    """Append or dry-run append a candidate event to the event ledger."""
    root = root.resolve()
    prepared = _prepare_append(
        root, file, stdin, tasks_file, events_file, envelope_file, candidate
    )
    if isinstance(prepared, CheckResult):
        return prepared
    candidate, source, task_id, ledger_check, runtime_audit = prepared

    if not commit:
        return _candidate_summary(
            status="pass",
            source=source,
            candidate=candidate,
            task_id=task_id,
            ledger_check=ledger_check,
            runtime_audit=runtime_audit,
            would_append=False,
            committed=False,
            next_action="Dry-run passed. Re-run with --commit to persist exactly one event ledger line.",
        )

    resolved_events = _resolve_commit_events_path(root, events_file)
    if isinstance(resolved_events, CheckResult):
        return resolved_events
    events_path = resolved_events
    if not _has_trailing_newline(events_path):
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id="events-file-missing-trailing-newline",
                    severity="block",
                    action="deny",
                    message="Events file must end with a newline before append.",
                )
            ],
            next_action="Fix the ledger newline explicitly, then retry the append.",
        )

    if not events_path.parent.is_dir():
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id="events-parent-missing",
                    severity="block",
                    action="deny",
                    message="Events file parent directory must already exist.",
                )
            ],
            next_action="Create the ledger directory explicitly before committing an event append.",
        )

    existed = events_path.exists()
    original_size = events_path.stat().st_size if existed else 0
    line = json.dumps(candidate, ensure_ascii=False) + "\n"
    with open(events_path, "a", encoding="utf-8", newline="") as fh:
        fh.write(line)

    post_validate = validate_records(root, _rel_to_root(root, events_path), "event")
    post_ledger = check_ledger_consistency(
        root,
        tasks_file=tasks_file or "tasks/tasks.jsonl",
        events_file=_rel_to_root(root, events_path),
    )
    post_runtime = None
    if envelope_file:
        post_runtime = check_runtime_ledger(
            root,
            tasks_file=tasks_file or "tasks/tasks.jsonl",
            events_file=_rel_to_root(root, events_path),
            envelope_file=envelope_file,
        )

    failures: list[Finding] = []
    if post_validate.status != "pass":
        failures.extend(post_validate.findings)
    if post_ledger.status != "pass":
        failures.extend(post_ledger.findings)
    if post_runtime is not None and post_runtime.status not in {"pass", "warn"}:
        failures.extend(post_runtime.findings)

    result = _candidate_summary(
        status="pass",
        source=source,
        candidate=candidate,
        task_id=task_id,
        ledger_check=ledger_check,
        runtime_audit=runtime_audit,
        would_append=True,
        committed=True,
        next_action="Event appended. Review runtime report before further actions.",
    )
    result.post_validate = post_validate.status
    result.post_ledger_check = post_ledger.status
    result.post_runtime_audit = post_runtime.status if post_runtime is not None else None

    if not failures:
        return result

    rollback_ok, rollback_error = _rollback_events_file(
        events_path, original_size, created=not existed
    )
    result.status = "error" if not rollback_ok else "validation_failed"
    result.findings = failures
    result.committed = False
    result.rolled_back = rollback_ok
    result.rollback_error = rollback_error
    result.next_action = (
        "Post-append checks failed and rollback succeeded. Fix the event or ledger before retrying."
        if rollback_ok
        else "Post-append checks failed and rollback failed. Restore the event ledger manually."
    )
    return result


def append_event_dry_run(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
    dry_run: bool = False,
    tasks_file: str | None = None,
    events_file: str | None = None,
    envelope_file: str | None = None,
    candidate: dict[str, Any] | None = None,
) -> CheckResult:
    """Dry-run append a candidate event to the event ledger.

    Read-only: no ledger files are modified. The optional ``candidate``
    argument is provided for unit tests; when omitted, the event is read
    from ``file`` or ``stdin``.
    """
    if not dry_run:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-dry-run",
                    severity="error",
                    action="error",
                    message="--dry-run is required for runtime event append.",
                )
            ],
            next_action="Add --dry-run to simulate the append without writing.",
        )
    return append_event(
        root,
        file=file,
        stdin=stdin,
        commit=False,
        tasks_file=tasks_file,
        events_file=events_file,
        envelope_file=envelope_file,
        candidate=candidate,
    )

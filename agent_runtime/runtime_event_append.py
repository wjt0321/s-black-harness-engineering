"""Dry-run append for task events.

This module is read-only: it simulates appending a candidate event to the
event ledger and reports whether the append would be safe. No ledger files
are modified.
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

    if candidate is not None:
        source = "candidate"
    else:
        loaded = _load_candidate_event(root, file=file, stdin=stdin)
        if isinstance(loaded, CheckResult):
            return loaded
        candidate, source = loaded

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

    metadata = candidate.get("metadata")
    artifacts = candidate.get("artifacts")

    return EventAppendDryRunResult(
        status="pass",
        findings=[],
        source=source,
        event_id=candidate.get("event_id"),
        task_id=task_id,
        event_type=candidate.get("event_type"),
        from_status=candidate.get("from_status"),
        to_status=candidate.get("to_status"),
        would_append=False,
        ledger_check=ledger_check,
        runtime_audit=runtime_audit,
        metadata_keys=sorted(metadata.keys()) if isinstance(metadata, dict) else [],
        artifact_count=len(artifacts) if isinstance(artifacts, list) else None,
        next_action="Dry-run passed. Use runtime event append --commit (not yet implemented) to persist.",
    )

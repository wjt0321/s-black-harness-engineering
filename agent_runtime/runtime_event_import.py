"""Dry-run batch import for task events.

This module implements a read-only preflight for ``runtime event import --dry-run``:

* Loads a candidate JSONL file containing one event object per line.
* Validates each candidate line for JSON syntax, object shape, schema validity,
  secret/public scan clearance, and duplicate event ids.
* Simulates appending the whole batch to the existing events ledger in a
  temporary file, then runs the same schema and ledger-consistency checks that
  would apply to the real ledger.
* Reports a safe summary and deletes the temporary file.

No ledger files are modified, no adapter is executed, no network access is
performed, and no credential files are read.
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .ledger_consistency import check_ledger_consistency
from .loader import is_safe_to_read, load_schema, normalize_path
from .policy import check_text
from .result import CheckResult, Finding
from .task_validation import validate_records

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_public_scan_spec = importlib.util.spec_from_file_location(
    "public_scan", _TOOLS_DIR / "public_scan.py"
)
_public_scan = importlib.util.module_from_spec(_public_scan_spec)
_public_scan_spec.loader.exec_module(_public_scan)
_PUBLIC_SCAN_RULES: list[dict[str, str]] = _public_scan.SCAN_RULES


@dataclass
class EventImportDryRunResult(CheckResult):
    """Result of simulating a batch event import.

    The summary only exposes safe identifiers and counts. It never includes
    event messages, metadata values, artifact payloads, evidence descriptions,
    targets, inputs, or raw/decision refs.
    """

    source: str | None = None
    event_count: int = 0
    blank_line_count: int = 0
    task_count: int = 0
    event_type_counts: dict[str, int] = field(default_factory=dict)
    candidate_event_ids_present: list[str] = field(default_factory=list)
    would_import: bool = False
    ledger_check: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.source is not None:
            d["source"] = self.source
        d["event_count"] = self.event_count
        d["blank_line_count"] = self.blank_line_count
        d["task_count"] = self.task_count
        if self.event_type_counts:
            d["event_type_counts"] = dict(self.event_type_counts)
        if self.candidate_event_ids_present:
            d["candidate_event_ids_present"] = list(self.candidate_event_ids_present)
        d["would_import"] = self.would_import
        if self.ledger_check is not None:
            d["ledger_check"] = self.ledger_check
        return d


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


def _validate_candidate_event_schema(
    root: Path, candidate: dict[str, Any]
) -> CheckResult | None:
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


def _resolve_candidate_file(root: Path, file: str) -> CheckResult | Path:
    """Validate the candidate import file path."""
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
            next_action="Choose a project-local candidate JSONL file.",
        )
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & {".git", "credential", "credentials", "secret", "secrets"}:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsafe-candidate-file",
                    severity="error",
                    action="error",
                    message="Candidate file must not point to git internals or credential paths.",
                )
            ],
            next_action="Choose a safe project-local .jsonl candidate file.",
        )
    if not is_safe_to_read(path) or path.suffix.lower() != ".jsonl":
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsafe-candidate-file",
                    severity="error",
                    action="error",
                    message="Candidate file must be a safe .jsonl file.",
                )
            ],
            next_action="Choose a safe project-local .jsonl candidate file.",
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
    return path


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


def _load_existing_event_lines(root: Path, events_file: str | None) -> int:
    """Return the number of raw lines in the existing events ledger."""
    events_path = (root / (events_file or "tasks/events.jsonl")).resolve()
    if not events_path.is_file() or not is_safe_to_read(events_path):
        return 0
    with open(events_path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _load_existing_task_ids(root: Path, tasks_file: str | None) -> set[str]:
    """Collect task id values already present in the target tasks ledger."""
    tasks_path = (root / (tasks_file or "tasks/tasks.jsonl")).resolve()
    task_ids: set[str] = set()
    if not tasks_path.is_file() or not is_safe_to_read(tasks_path):
        return task_ids
    with open(tasks_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                task_id = record.get("id")
                if task_id:
                    task_ids.add(task_id)
    return task_ids


def _simulate_import_and_check(
    root: Path,
    candidates: list[tuple[int, dict[str, Any]]],
    tasks_file: str | None,
    events_file: str | None,
) -> tuple[CheckResult, CheckResult]:
    """Write a temp JSONL with existing events + candidates and run checks.

    Each candidate is paired with its 1-based source line number so that any
    post-check findings can be mapped back to the original input line. Returns
    the schema validation result and the ledger consistency result.
    """
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
        for _line_no, candidate in candidates:
            tmp.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        tmp_name = tmp.name

    try:
        tmp_rel = normalize_path(Path(tmp_name).relative_to(root))
        validate_result = validate_records(root, tmp_rel, "event")
        ledger_result = check_ledger_consistency(
            root,
            tasks_file=normalize_path(tasks_path.relative_to(root)),
            events_file=tmp_rel,
        )
        return validate_result, ledger_result
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def _coalesce_findings_status(findings: list[Finding]) -> str:
    """Map a list of findings to a single result status."""
    statuses: list[str] = []
    for finding in findings:
        if finding.severity == "block":
            statuses.append("blocked")
        else:
            statuses.append("validation_failed")
    if "blocked" in statuses:
        return "blocked"
    if statuses:
        return "validation_failed"
    return "pass"


def import_events_dry_run(
    root: Path,
    file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
) -> CheckResult:
    """Dry-run batch import candidate events from a JSONL file.

    Read-only: no ledger files are modified. The candidate file is parsed line
    by line, each line is validated and scanned, and the whole batch is checked
    against the existing task/events ledgers via a temporary file.

    Each retained candidate is stored as ``(source_line_no, event_dict)`` so
    that all downstream findings map back to the exact input line, even when
    preceding lines were blank, invalid, or filtered out.
    """
    root = root.resolve()

    resolved_path = _resolve_candidate_file(root, file)
    if isinstance(resolved_path, CheckResult):
        return resolved_path

    source = normalize_path(resolved_path.relative_to(root))

    findings: list[Finding] = []
    candidates: list[tuple[int, dict[str, Any]]] = []
    blank_line_count = 0
    seen_candidate_event_ids: dict[str, int] = {}

    try:
        with open(resolved_path, "r", encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    blank_line_count += 1
                    continue

                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    findings.append(
                        Finding(
                            rule_id="invalid-json",
                            severity="error",
                            action="error",
                            message=f"Invalid JSON: {exc.msg}",
                            line=line_no,
                        )
                    )
                    continue

                if not isinstance(record, dict):
                    findings.append(
                        Finding(
                            rule_id="candidate-not-object",
                            severity="error",
                            action="error",
                            message="Candidate event must be a JSON object.",
                            line=line_no,
                        )
                    )
                    continue

                schema_result = _validate_candidate_event_schema(root, record)
                if schema_result is not None:
                    finding = schema_result.findings[0]
                    finding.line = line_no
                    findings.append(finding)
                    continue

                scan_findings = _scan_candidate_content(root, record)
                if scan_findings:
                    for finding in scan_findings:
                        finding.line = line_no
                    findings.extend(scan_findings)
                    continue

                event_id = record.get("event_id")
                if event_id in seen_candidate_event_ids:
                    findings.append(
                        Finding(
                            rule_id="duplicate-candidate-event-id",
                            severity="error",
                            action="error",
                            message="event id duplicates an earlier candidate event.",
                            line=line_no,
                        )
                    )
                    continue
                if event_id:
                    seen_candidate_event_ids[event_id] = line_no

                candidates.append((line_no, record))
    except OSError as exc:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="read-error",
                    severity="error",
                    action="error",
                    message=f"Could not read candidate file: {exc}",
                )
            ],
            next_action="Check the candidate file path and permissions.",
        )

    existing_event_ids = _load_existing_event_ids(root, events_file)
    for line_no, candidate in candidates:
        event_id = candidate.get("event_id")
        if event_id and event_id in existing_event_ids:
            findings.append(
                Finding(
                    rule_id="duplicate-event-id",
                    severity="error",
                    action="error",
                    message="event_id already exists in the target events ledger.",
                    line=line_no,
                )
            )

    existing_task_ids = _load_existing_task_ids(root, tasks_file)
    for line_no, candidate in candidates:
        task_id = candidate.get("task_id")
        if task_id and task_id not in existing_task_ids:
            findings.append(
                Finding(
                    rule_id="unknown-task-id",
                    severity="error",
                    action="error",
                    message=f"task_id {task_id} not found in task ledger.",
                    line=line_no,
                )
            )

    if findings:
        status = _coalesce_findings_status(findings)
        return EventImportDryRunResult(
            status=status,
            findings=findings,
            source=source,
            event_count=len(candidates),
            blank_line_count=blank_line_count,
            task_count=len({c[1].get("task_id") for c in candidates if c[1].get("task_id")}),
            event_type_counts={},
            candidate_event_ids_present=[c[1].get("event_id") for c in candidates if c[1].get("event_id")],
            would_import=False,
            ledger_check=None,
            next_action="Fix the reported issues before importing the event batch.",
        )

    validate_result, ledger_result = _simulate_import_and_check(
        root, candidates, tasks_file, events_file
    )

    ledger_check = ledger_result.status
    if validate_result.status != "pass":
        ledger_check = "validation_failed"
        for finding in validate_result.findings:
            finding.message = f"Schema validation: {finding.message}"
            findings.append(finding)

    if ledger_result.status == "validation_failed":
        # Ledger consistency findings reference lines inside the temporary file.
        # Map them back to the original candidate source lines when possible.
        existing_event_line_count = _load_existing_event_lines(root, events_file)
        for finding in ledger_result.findings:
            tmp_line = finding.line
            if tmp_line is not None:
                candidate_idx = tmp_line - existing_event_line_count - 1
                if 0 <= candidate_idx < len(candidates):
                    finding.line = candidates[candidate_idx][0]
            finding.message = f"Ledger consistency: {finding.message}"
            findings.append(finding)
    elif ledger_result.status == "error":
        return CheckResult(
            status="error",
            findings=list(ledger_result.findings),
            next_action="Fix ledger file paths before retrying.",
        )

    event_type_counts: dict[str, int] = {}
    for _line_no, candidate in candidates:
        event_type = candidate.get("event_type")
        if event_type:
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

    if findings:
        status = _coalesce_findings_status(findings)
        return EventImportDryRunResult(
            status=status,
            findings=findings,
            source=source,
            event_count=len(candidates),
            blank_line_count=blank_line_count,
            task_count=len({c[1].get("task_id") for c in candidates if c[1].get("task_id")}),
            event_type_counts=event_type_counts,
            candidate_event_ids_present=[c[1].get("event_id") for c in candidates if c[1].get("event_id")],
            would_import=False,
            ledger_check=ledger_check,
            next_action="Fix the reported ledger issues before importing the event batch.",
        )

    return EventImportDryRunResult(
        status="pass",
        findings=[],
        source=source,
        event_count=len(candidates),
        blank_line_count=blank_line_count,
        task_count=len({c[1].get("task_id") for c in candidates if c[1].get("task_id")}),
        event_type_counts=event_type_counts,
        candidate_event_ids_present=[c[1].get("event_id") for c in candidates if c[1].get("event_id")],
        would_import=True,
        ledger_check="pass",
        next_action="Dry-run passed. Review the event batch before any future commit command.",
    )

"""Read-only validation for task/event ledger records before write."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import FormatChecker
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from .loader import is_safe_to_read, load_schema
from .result import CheckResult, Finding


SCHEMA_MAP = {
    "task": "tasks/task.schema.json",
    "event": "tasks/event.schema.json",
}

_EXECUTION_AUDIT_EVENT_TYPES = {
    "execution_attempt_started",
    "execution_succeeded",
    "execution_failed",
    "execution_cancelled",
}
_RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
DATE_TIME_FORMAT_CHECKER = FormatChecker()


@DATE_TIME_FORMAT_CHECKER.checks("date-time")
def _is_rfc3339_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if _RFC3339_RE.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _safe_error_message(line_no: int, schema_type: str, exc: JsonSchemaValidationError) -> str:
    """Return a short, value-free validation error summary."""
    path = ".".join(str(part) for part in exc.path) if exc.path else "(root)"
    validator = exc.validator or "schema"

    if validator == "required":
        # message shape: "'id' is a required property"
        parts = exc.message.split("'")
        field = parts[1] if len(parts) >= 2 else path
        return f"Line {line_no} ({schema_type}): required field missing: {field}"
    if validator == "enum":
        return f"Line {line_no} ({schema_type}): value not in allowed enum at {path}"
    if validator == "type":
        return f"Line {line_no} ({schema_type}): type mismatch at {path}"
    if validator == "pattern":
        return f"Line {line_no} ({schema_type}): pattern mismatch at {path}"
    if validator == "additionalProperties":
        return f"Line {line_no} ({schema_type}): unexpected field at {path}"
    if validator == "format":
        return f"Line {line_no} ({schema_type}): format error at {path}"

    return f"Line {line_no} ({schema_type}): validation failed at {path}"


def validate_records(
    root: Path,
    record_file: str,
    schema_type: str,
) -> CheckResult:
    """Validate each line of a JSONL file against the task or event schema.

    This function is read-only: it opens the file, validates each record, and
    returns a result. It never writes, appends, or modifies the ledger.
    """
    schema_type = schema_type.lower()
    schema_rel = SCHEMA_MAP.get(schema_type)
    if schema_rel is None:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsupported-schema",
                    severity="error",
                    action="error",
                    message=f"Unsupported schema type: {schema_type}. Use 'task' or 'event'.",
                )
            ],
            next_action="Specify --schema task or --schema event.",
        )

    schema = load_schema(root, schema_rel)
    root = root.resolve()
    path = (root / record_file).resolve()

    if path != root and root not in path.parents:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="path-outside-root",
                    severity="error",
                    action="error",
                    message="Record file must be inside the project root.",
                )
            ],
            next_action="Choose a project-local JSONL ledger file.",
        )

    if not is_safe_to_read(path) or path.suffix.lower() != ".jsonl":
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsafe-record-file",
                    severity="error",
                    action="error",
                    message="Record file must be a safe JSONL file.",
                )
            ],
            next_action="Choose a project-local JSONL ledger file.",
        )

    if not path.is_file():
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="file-not-found",
                    severity="error",
                    action="error",
                    message=f"Record file not found: {record_file}",
                )
            ],
            next_action="Check the record file path.",
        )

    findings: list[Finding] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    findings.append(
                        Finding(
                            rule_id="invalid-json",
                            severity="error",
                            action="error",
                            message=f"Line {line_no} ({schema_type}): invalid JSON - {exc.msg}",
                            line=line_no,
                        )
                    )
                    continue

                try:
                    validate(
                        instance=record,
                        schema=schema,
                        format_checker=DATE_TIME_FORMAT_CHECKER,
                    )
                except JsonSchemaValidationError as exc:
                    findings.append(
                        Finding(
                            rule_id="schema-validation-failed",
                            severity="error",
                            action="error",
                            message=_safe_error_message(line_no, schema_type, exc),
                            line=line_no,
                        )
                    )
                    continue

                if (
                    schema_type == "event"
                    and isinstance(record, dict)
                    and record.get("event_type") in _EXECUTION_AUDIT_EVENT_TYPES
                ):
                    execution_schema = load_schema(
                        root, "tasks/execution-audit-event.schema.json"
                    )
                    try:
                        validate(
                            instance=record,
                            schema=execution_schema,
                            format_checker=DATE_TIME_FORMAT_CHECKER,
                        )
                    except JsonSchemaValidationError as exc:
                        findings.append(
                            Finding(
                                rule_id="execution-audit-schema-validation-failed",
                                severity="error",
                                action="error",
                                message=_safe_error_message(
                                    line_no, "execution-audit-event", exc
                                ),
                                line=line_no,
                            )
                        )
    except OSError as exc:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="read-error",
                    severity="error",
                    action="error",
                    message=f"Could not read {record_file}: {exc}",
                )
            ],
            next_action="Check file permissions.",
        )

    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Fix the reported records before writing to the ledger.",
        )
    return CheckResult(
        status="pass",
        findings=[],
        next_action="All records passed schema validation.",
    )

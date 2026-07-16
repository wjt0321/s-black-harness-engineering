"""Doctor: validate project structure, JSON/JSONL syntax, schemas, and public scan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .loader import (
    load_json,
    load_jsonl,
    load_schema,
    iter_text_files,
    is_safe_to_read,
    discover_policies,
    load_agents,
    load_adapters,
)
from .policy import check_text
from .result import CheckResult, Finding


REQUIRED_DIRECTORIES = ["docs", "policies", "agents", "adapters", "automation", "tasks"]
REQUIRED_FILES = ["README.md"]

SCHEMA_FILES = [
    "policies/policy.schema.json",
    "agents/agents.schema.json",
    "adapters/adapter.schema.json",
    "adapters/execution-envelope.schema.json",
    "adapters/execution-readiness.schema.json",
    "automation/automation-profiles.schema.json",
    "tasks/task.schema.json",
    "tasks/event.schema.json",
]

SAMPLE_TO_SCHEMA: list[tuple[str, str]] = [
    ("policies/*.sample.policy.json", "policies/policy.schema.json"),
    ("agents/agents.sample.json", "agents/agents.schema.json"),
    ("adapters/adapters.sample.json", "adapters/adapter.schema.json"),
    ("adapters/execution-envelope.examples.json", "adapters/execution-envelope.schema.json"),
    ("adapters/execution-readiness.sample.json", "adapters/execution-readiness.schema.json"),
    ("automation/automation-profiles.sample.json", "automation/automation-profiles.schema.json"),
]

JSONL_PATTERNS = ["tasks/*.jsonl"]


def _validate_json_file(path: Path) -> None:
    load_json(path)


def _validate_json_against_schema(path: Path, schema: dict[str, Any]) -> None:
    data = load_json(path)
    validate(instance=data, schema=schema)


def _validate_jsonl_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        load_jsonl(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: {exc}")
    return errors


def _scan_text_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        result = check_text(root, text)
        for finding in result.findings:
            # Keep path but never echo secret content.
            finding.message = f"{path.relative_to(root)}: {finding.message}"
            findings.append(finding)
    return findings


def run_doctor(root: Path) -> CheckResult:
    """Run all doctor checks and return a single result."""
    findings: list[Finding] = []

    # Required directories
    for name in REQUIRED_DIRECTORIES:
        directory = root / name
        if not directory.is_dir():
            findings.append(
                Finding(
                    rule_id="missing-directory",
                    severity="block",
                    action="deny",
                    message=f"Required directory missing: {name}",
                )
            )

    # Required files
    for name in REQUIRED_FILES:
        file_path = root / name
        if not file_path.is_file():
            findings.append(
                Finding(
                    rule_id="missing-file",
                    severity="block",
                    action="deny",
                    message=f"Required file missing: {name}",
                )
            )

    # JSON schemas valid
    schema_cache: dict[str, dict[str, Any]] = {}
    for schema_rel in SCHEMA_FILES:
        schema_path = root / schema_rel
        try:
            schema_cache[schema_rel] = load_schema(root, schema_rel)
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                Finding(
                    rule_id="invalid-schema",
                    severity="block",
                    action="deny",
                    message=f"Schema invalid or unreadable: {schema_rel} ({exc})",
                )
            )

    # Sample files validate against schemas
    for pattern, schema_rel in SAMPLE_TO_SCHEMA:
        if schema_rel not in schema_cache:
            continue
        schema = schema_cache[schema_rel]
        for path in sorted(root.glob(pattern)):
            if not is_safe_to_read(path):
                continue
            try:
                _validate_json_against_schema(path, schema)
            except (OSError, json.JSONDecodeError, JsonSchemaValidationError) as exc:
                findings.append(
                    Finding(
                        rule_id="schema-validation-failed",
                        severity="block",
                        action="deny",
                        message=f"{path.relative_to(root)} failed {schema_rel}: {exc}",
                    )
                )

    # JSONL files
    for pattern in JSONL_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not is_safe_to_read(path):
                continue
            for error in _validate_jsonl_file(path):
                findings.append(
                    Finding(
                        rule_id="invalid-jsonl",
                        severity="block",
                        action="deny",
                        message=error,
                    )
                )

    # Public scan
    scan_findings = _scan_text_files(root)
    findings.extend(scan_findings)

    if findings:
        return CheckResult(
            status="error" if any(f.severity == "error" for f in findings) else "blocked",
            findings=findings,
            next_action="Fix validation errors or redact secrets before proceeding.",
        )
    return CheckResult(status="pass", next_action="All checks passed.")

"""Dry-run and commit create for task snapshots.

This module implements a narrow controlled-write boundary:

* ``runtime task create --dry-run`` simulates appending a candidate task to the
task ledger and reports whether the append would be safe. No ledger files are
modified.

* ``runtime task create --commit`` appends exactly one JSON object as the last
line of a task ledger JSONL file, then validates the resulting ledger and
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
from .task_validation import validate_records

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_public_scan_spec = importlib.util.spec_from_file_location(
    "public_scan", _TOOLS_DIR / "public_scan.py"
)
_public_scan = importlib.util.module_from_spec(_public_scan_spec)
_public_scan_spec.loader.exec_module(_public_scan)
_PUBLIC_SCAN_RULES: list[dict[str, str]] = _public_scan.SCAN_RULES


@dataclass
class TaskCreateDryRunResult(CheckResult):
    """Result of simulating or committing a task snapshot create.

    The summary only exposes safe identifiers and status/count fields. It does
    not include the task title, summary, evidence descriptions, or any free-text
    payload.
    """

    source: str | None = None
    task_id: str | None = None
    task_status: str | None = None
    title_present: bool = False
    assignee_present: bool = False
    tag_count: int | None = None
    artifact_count: int | None = None
    evidence_count: int | None = None
    would_create: bool = False
    ledger_check: str | None = None
    metadata_keys: list[str] = field(default_factory=list)
    committed: bool = False
    post_validate: str | None = None
    post_ledger_check: str | None = None
    rolled_back: bool = False
    rollback_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.source is not None:
            d["source"] = self.source
        if self.task_id is not None:
            d["task_id"] = self.task_id
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
        if self.ledger_check is not None:
            d["ledger_check"] = self.ledger_check
        if self.metadata_keys:
            d["metadata_keys"] = self.metadata_keys
        d["committed"] = self.committed
        if self.post_validate is not None:
            d["post_validate"] = self.post_validate
        if self.post_ledger_check is not None:
            d["post_ledger_check"] = self.post_ledger_check
        d["rolled_back"] = self.rolled_back
        if self.rollback_error is not None:
            d["rollback_error"] = self.rollback_error
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
    """Run policy secret scan and public-release scan over the serialized task."""
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


def _safe_task_schema_error(exc: JsonSchemaValidationError) -> str:
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


def _validate_task_schema(root: Path, candidate: dict[str, Any]) -> CheckResult | None:
    """Validate a candidate task against tasks/task.schema.json."""
    schema = load_schema(root, "tasks/task.schema.json")
    try:
        validate(instance=candidate, schema=schema)
    except JsonSchemaValidationError as exc:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="task-schema-validation-failed",
                    severity="error",
                    action="error",
                    message=_safe_task_schema_error(exc),
                )
            ],
            next_action="Fix the candidate task to match tasks/task.schema.json.",
        )
    return None


def _load_candidate_task(
    root: Path, file: str | None, stdin: bool
) -> CheckResult | tuple[dict[str, Any], str]:
    """Load a candidate task from a file or stdin."""
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
                        message="Candidate task must be a JSON object.",
                    )
                ],
                next_action="Provide a single task object as JSON.",
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
                        message="Candidate task must be a JSON object.",
                    )
                ],
                next_action="Provide a single task object as JSON.",
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


def _load_existing_task_ids(tasks_path: Path) -> set[str]:
    """Collect task id values already present in the target tasks ledger."""
    task_ids: set[str] = set()
    if not tasks_path.is_file():
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


def _simulate_append_and_check(
    root: Path,
    candidate: dict[str, Any],
    tasks_path: Path,
    events_path: Path,
) -> CheckResult:
    """Write a temp JSONL with existing tasks + candidate and run ledger checks.

    If the events ledger does not yet exist, an empty temporary events file is
    used so that newly created tasks (which have no events yet) are not blocked.
    """
    existing_task_lines: list[str] = []
    if tasks_path.is_file():
        existing_task_lines = tasks_path.read_text(encoding="utf-8").splitlines()

    tmp_events_name: str | None = None
    if not events_path.is_file():
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
        ) as tmp_events:
            tmp_events_name = tmp_events.name

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
    ) as tmp_tasks:
        for line in existing_task_lines:
            tmp_tasks.write(line + "\n")
        tmp_tasks.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        tmp_tasks_name = tmp_tasks.name

    try:
        tmp_tasks_rel = normalize_path(Path(tmp_tasks_name).relative_to(root))
        events_file_arg = (
            normalize_path(Path(tmp_events_name).relative_to(root))
            if tmp_events_name
            else normalize_path(events_path.relative_to(root))
        )
        ledger_result = check_ledger_consistency(
            root,
            tasks_file=tmp_tasks_rel,
            events_file=events_file_arg,
        )
        return ledger_result
    finally:
        Path(tmp_tasks_name).unlink(missing_ok=True)
        if tmp_events_name:
            Path(tmp_events_name).unlink(missing_ok=True)


def _resolve_commit_tasks_path(root: Path, tasks_file: str | None) -> CheckResult | Path:
    """Validate the commit target tasks ledger path.

    Reuses the basic ledger path guard and additionally blocks sample ledgers.
    """
    resolved = _resolve_ledger_path(
        root, tasks_file, "tasks/tasks.jsonl", "tasks"
    )
    if isinstance(resolved, CheckResult):
        return resolved
    rel = normalize_path(resolved.relative_to(root))
    rel_lower = rel.lower()
    if rel_lower == "tasks/examples.jsonl" or rel_lower.endswith(".examples.jsonl"):
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="sample-ledger-write-blocked",
                    severity="error",
                    action="error",
                    message="Sample ledgers are not valid commit targets.",
                )
            ],
            next_action="Use tasks/tasks.jsonl or another project-local runtime ledger.",
        )
    return resolved


def _has_trailing_newline(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return True
    with open(path, "rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) == b"\n"


def _rel_to_root(root: Path, path: Path) -> str:
    return normalize_path(path.resolve().relative_to(root.resolve()))


def _rollback_tasks_file(path: Path, original_size: int, created: bool) -> tuple[bool, str | None]:
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
    ledger_check: str | None,
    would_create: bool,
    committed: bool,
    next_action: str,
    findings: list[Finding] | None = None,
    post_validate: str | None = None,
    post_ledger_check: str | None = None,
    rolled_back: bool = False,
    rollback_error: str | None = None,
) -> TaskCreateDryRunResult:
    title = candidate.get("title")
    assignee = candidate.get("assignee")
    tags = candidate.get("tags")
    artifacts = candidate.get("artifacts")
    evidence = candidate.get("evidence")
    metadata = candidate.get("metadata")
    return TaskCreateDryRunResult(
        status=status,
        findings=findings or [],
        source=source,
        task_id=task_id,
        task_status=candidate.get("status"),
        title_present=isinstance(title, str) and len(title) > 0,
        assignee_present=assignee is not None,
        tag_count=len(tags) if isinstance(tags, list) else None,
        artifact_count=len(artifacts) if isinstance(artifacts, list) else None,
        evidence_count=len(evidence) if isinstance(evidence, list) else None,
        would_create=would_create,
        ledger_check=ledger_check,
        metadata_keys=sorted(metadata.keys()) if isinstance(metadata, dict) else [],
        committed=committed,
        post_validate=post_validate,
        post_ledger_check=post_ledger_check,
        rolled_back=rolled_back,
        rollback_error=rollback_error,
        next_action=next_action,
    )


def _prepare_create(
    root: Path,
    file: str | None,
    stdin: bool,
    tasks_file: str | None,
    events_file: str | None,
    candidate: dict[str, Any] | None,
) -> CheckResult | tuple[dict[str, Any], str, str, Path, Path]:
    """Run all write-before checks and return the candidate plus resolved paths."""
    root = root.resolve()

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

    if candidate is not None:
        source = "candidate"
        if not isinstance(candidate, dict):
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="candidate-not-object",
                        severity="error",
                        action="error",
                        message="Candidate task must be a JSON object.",
                    )
                ],
                next_action="Provide a single task object as JSON.",
            )
    else:
        loaded = _load_candidate_task(root, file=file, stdin=stdin)
        if isinstance(loaded, CheckResult):
            return loaded
        candidate, source = loaded

    schema_result = _validate_task_schema(root, candidate)
    if schema_result is not None:
        return schema_result

    task_id = candidate.get("id")
    if not task_id:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="missing-task-id",
                    severity="error",
                    action="error",
                    message="Candidate task is missing id.",
                )
            ],
            next_action="Add an id to the candidate task.",
        )

    existing_task_ids = _load_existing_task_ids(tasks_path_resolved)
    if task_id in existing_task_ids:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="duplicate-task-id",
                    severity="error",
                    action="error",
                    message="task id already exists in the target tasks ledger.",
                )
            ],
            next_action="Use a unique task id for the candidate task.",
        )

    scan_findings = _scan_candidate_content(root, candidate)
    if scan_findings:
        return CheckResult(
            status="blocked",
            findings=scan_findings,
            next_action="Redact sensitive or public-release-risk content before creating.",
        )

    return candidate, source, task_id, tasks_path_resolved, events_path_resolved


def create_task(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
    commit: bool = False,
    tasks_file: str | None = None,
    events_file: str | None = None,
    candidate: dict[str, Any] | None = None,
) -> CheckResult:
    """Dry-run or commit create a candidate task snapshot.

    The optional ``candidate`` argument is provided for unit tests; when omitted,
    the task is read from ``file`` or ``stdin``.
    """
    prepared = _prepare_create(
        root, file, stdin, tasks_file, events_file, candidate
    )
    if isinstance(prepared, CheckResult):
        return prepared
    candidate, source, task_id, tasks_path, events_path = prepared

    ledger_result = _simulate_append_and_check(
        root, candidate, tasks_path, events_path
    )

    if ledger_result.status == "error":
        return CheckResult(
            status="error",
            findings=list(ledger_result.findings),
            next_action="Fix ledger file paths before retrying.",
        )

    findings: list[Finding] = []
    ledger_check = ledger_result.status

    if ledger_result.status == "validation_failed":
        for finding in ledger_result.findings:
            finding.message = f"Ledger consistency: {finding.message}"
            findings.append(finding)

    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Fix the reported issues before creating the task.",
        )

    if not commit:
        return _candidate_summary(
            status="pass",
            source=source,
            candidate=candidate,
            task_id=task_id,
            ledger_check=ledger_check,
            would_create=False,
            committed=False,
            next_action="Dry-run passed. Re-run with --commit to persist exactly one task ledger line.",
        )

    resolved_tasks = _resolve_commit_tasks_path(root, tasks_file)
    if isinstance(resolved_tasks, CheckResult):
        return resolved_tasks

    if not _has_trailing_newline(resolved_tasks):
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id="tasks-file-missing-trailing-newline",
                    severity="block",
                    action="deny",
                    message="Tasks file must end with a newline before append.",
                )
            ],
            next_action="Fix the ledger newline explicitly, then retry the create.",
        )

    if not resolved_tasks.parent.is_dir():
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id="tasks-parent-missing",
                    severity="block",
                    action="deny",
                    message="Tasks file parent directory must already exist.",
                )
            ],
            next_action="Create the ledger directory explicitly before committing a task create.",
        )

    existed = resolved_tasks.exists()
    original_size = resolved_tasks.stat().st_size if existed else 0
    line = json.dumps(candidate, ensure_ascii=False) + "\n"
    with open(resolved_tasks, "a", encoding="utf-8", newline="") as fh:
        fh.write(line)

    post_validate = validate_records(root, _rel_to_root(root, resolved_tasks), "task")

    tmp_events_name: str | None = None
    events_file_arg = events_file or "tasks/events.jsonl"
    if not events_path.is_file():
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8", dir=root
        ) as tmp_events:
            tmp_events_name = tmp_events.name
        events_file_arg = _rel_to_root(root, Path(tmp_events_name))

    try:
        post_ledger = check_ledger_consistency(
            root,
            tasks_file=_rel_to_root(root, resolved_tasks),
            events_file=events_file_arg,
        )
    finally:
        if tmp_events_name:
            Path(tmp_events_name).unlink(missing_ok=True)

    failures: list[Finding] = []
    if post_validate.status != "pass":
        failures.extend(post_validate.findings)
    if post_ledger.status != "pass":
        failures.extend(post_ledger.findings)

    result = _candidate_summary(
        status="pass",
        source=source,
        candidate=candidate,
        task_id=task_id,
        ledger_check=ledger_check,
        would_create=True,
        committed=True,
        post_validate=post_validate.status,
        post_ledger_check=post_ledger.status,
        next_action="Task appended. Consider appending a created event before further runtime planning.",
    )

    if not failures:
        return result

    rollback_ok, rollback_error = _rollback_tasks_file(
        resolved_tasks, original_size, created=not existed
    )
    result.status = "error" if not rollback_ok else "validation_failed"
    result.findings = failures
    result.committed = False
    result.rolled_back = rollback_ok
    result.rollback_error = rollback_error
    result.next_action = (
        "Post-create checks failed and rollback succeeded. Fix the task or ledger before retrying."
        if rollback_ok
        else "Post-create checks failed and rollback failed. Restore the task ledger manually."
    )
    return result


def create_task_dry_run(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
    dry_run: bool = False,
    tasks_file: str | None = None,
    events_file: str | None = None,
    candidate: dict[str, Any] | None = None,
) -> CheckResult:
    """Dry-run create a candidate task snapshot.

    Read-only: no ledger files are modified. The optional ``candidate``
    argument is provided for unit tests; when omitted, the task is read
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
                    message="--dry-run is required for runtime task create.",
                )
            ],
            next_action="Add --dry-run to simulate the task create without writing.",
        )
    return create_task(
        root,
        file=file,
        stdin=stdin,
        commit=False,
        tasks_file=tasks_file,
        events_file=events_file,
        candidate=candidate,
    )

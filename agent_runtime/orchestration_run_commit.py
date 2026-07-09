"""Controlled commit for orchestration run plans.

This module persists an already-reviewed run plan as:

* A. an adapter execution envelope draft file.
* B. run lifecycle events appended to the event ledger.

It does **not** execute adapters, access networks, send messages, or perform
any real external action. The A+B sequence is all-or-nothing: if B fails, A is
deleted and B is rolled back to its original byte size.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .loader import is_safe_to_read, normalize_path
from .orchestration_run_dry_run import RunDryRunResult, dry_run_run
from .result import CheckResult, Finding
from .runtime_draft_export import (
    _post_write_check,
    _rollback_file,
    _scan_export_content,
    _validate_drafts_runtime_path,
    _validate_output_path,
    _write_envelope_file,
)
from .ledger_consistency import check_ledger_consistency
from .runtime_ledger import check_runtime_ledger
from .task_validation import validate_records
from .runtime_event_append import (
    _has_trailing_newline,
    _load_existing_event_ids,
    _resolve_commit_events_path,
    _rollback_events_file,
    _scan_candidate_content,
    _validate_event_schema,
)


@dataclass
class RunCommitResult:
    """Result of an orchestration run commit attempt."""

    status: str
    task_id: str
    request_id: str
    requested_capability: str
    mode: str = "commit"
    plan_hash: str | None = None
    expected_plan_hash: str | None = None
    freeze_check: str = "not_run"
    dry_run_summary: dict[str, Any] = field(default_factory=dict)
    write_summary: dict[str, Any] = field(default_factory=dict)
    artifact_ref: dict[str, Any] = field(default_factory=dict)
    event_refs: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "requested_capability": self.requested_capability,
            "mode": self.mode,
            "freeze_check": self.freeze_check,
            "dry_run_summary": self.dry_run_summary,
            "write_summary": self.write_summary,
            "artifact_ref": self.artifact_ref,
            "event_refs": self.event_refs,
        }
        if self.plan_hash is not None:
            d["plan_hash"] = self.plan_hash
        if self.expected_plan_hash is not None:
            d["expected_plan_hash"] = self.expected_plan_hash
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _dry_run_summary(dry_run: RunDryRunResult) -> dict[str, Any]:
    """Return a safe subset of the dry-run result for commit output."""
    return {
        "status": dry_run.status,
        "route": {
            "selected_adapter_id": dry_run.route.get("selected_adapter_id"),
            "capability": dry_run.route.get("capability"),
            "operation": dry_run.route.get("operation"),
            "risk_level": dry_run.route.get("risk_level"),
            "requires_approval": dry_run.route.get("requires_approval"),
            "requires_dry_run": dry_run.route.get("requires_dry_run"),
        },
        "preflight": {
            "status": dry_run.preflight.get("status"),
            "effective_mode": dry_run.preflight.get("effective_mode"),
        },
        "candidate_envelope_summary": dry_run.candidate_envelope_summary,
    }


def _artifact_ref(rel_output: str, dry_run: RunDryRunResult) -> dict[str, Any]:
    summary = dry_run.candidate_envelope_summary
    return {
        "artifact_type": "envelope_draft",
        "path": rel_output,
        "request_id": dry_run.request_id,
        "adapter_id": summary.get("adapter_id"),
        "operation": summary.get("operation"),
    }


def _event_ref(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata", {})
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "task_id": event.get("task_id"),
        "request_id": metadata.get("request_id"),
        "adapter_id": metadata.get("adapter_id"),
        "operation": metadata.get("operation"),
    }


def _generate_event_id(
    existing_ids: set[str],
    event_type: str,
    index: int,
) -> str:
    """Return a unique event_id matching the event schema pattern.

    The id format is ``evt-YYYYMMDD-NNN`` with a sequential suffix. If the
    generated id already exists in ``existing_ids``, the suffix is incremented
    until a unique value is found.
    """
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    seq = index + 1
    while True:
        candidate = f"evt-{date_part}-{seq:03d}"
        if candidate not in existing_ids:
            return candidate
        seq += 1


def _build_lifecycle_event(
    *,
    event_type: str,
    task_id: str,
    request_id: str,
    capability: str,
    adapter_id: str | None,
    operation: str | None,
    mode: str,
    plan_hash: str,
    envelope_path: str | None,
    freeze_check: str,
    approval_status: str,
    artifact_type: str | None,
    existing_ids: set[str],
    index: int,
    actor: str = "cli",
) -> dict[str, Any]:
    """Return a safe run lifecycle event dict."""
    event_id = _generate_event_id(existing_ids, event_type, index)
    existing_ids.add(event_id)

    if event_type == "run_planned":
        message = "Run plan generated and frozen."
    elif event_type == "run_draft_exported":
        message = "Run envelope draft exported."
    elif event_type == "run_blocked":
        message = "Run blocked by guardrail or freeze check."
    else:
        message = f"Run lifecycle event: {event_type}."

    metadata: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": adapter_id,
        "capability": capability,
        "operation": operation,
        "mode": mode,
        "plan_hash": plan_hash,
        "freeze_check": freeze_check,
        "approval_status": approval_status,
    }
    if envelope_path is not None:
        metadata["envelope_path"] = envelope_path
    if artifact_type is not None:
        metadata["artifact_type"] = artifact_type

    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "event_type": event_type,
        "message": message,
        "metadata": metadata,
    }


def _build_lifecycle_events(
    *,
    dry_run: RunDryRunResult,
    envelope_path: str | None,
    events_file: str,
    root: Path,
    actor: str = "cli",
) -> tuple[list[dict[str, Any]], list[Finding]] | None:
    """Build the run_planned + run_draft_exported event batch.

    Returns ``(events, findings)`` on success, or ``None`` if any event fails
    schema validation or security scan.
    """
    existing_ids = _load_existing_event_ids(root, events_file)
    base_ids = set(existing_ids)

    route = dry_run.route
    approval_status = "required" if route.get("requires_approval") else "not_required"
    envelope_rel = envelope_path

    events: list[dict[str, Any]] = []
    for idx, event_type in enumerate(["run_planned", "run_draft_exported"]):
        event = _build_lifecycle_event(
            event_type=event_type,
            task_id=dry_run.task_id,
            request_id=dry_run.request_id,
            capability=dry_run.requested_capability,
            adapter_id=route.get("selected_adapter_id"),
            operation=route.get("operation"),
            mode=dry_run.mode,
            plan_hash=dry_run.plan_hash or "",
            envelope_path=envelope_rel,
            freeze_check="pass",
            approval_status=approval_status,
            artifact_type="envelope_draft" if event_type == "run_draft_exported" else None,
            existing_ids=base_ids,
            index=idx,
            actor=actor,
        )

        schema_result = _validate_event_schema(root, event)
        if schema_result is not None:
            return None, list(schema_result.findings)

        scan_findings = _scan_candidate_content(root, event)
        if scan_findings:
            return None, scan_findings

        events.append(event)

    return events, []


def _append_events_block(
    root: Path,
    events_path: Path,
    events: list[dict[str, Any]],
    tasks_file: str | None,
    envelope_path: str | None,
) -> tuple[str, str | None, int, list[Finding]]:
    """Append a batch of events to the events ledger and run post-checks.

    Returns ``(post_validate, post_ledger_check, appended_line_count, findings)``.
    On failure the caller is responsible for rolling back.
    """
    original_size = events_path.stat().st_size if events_path.is_file() else 0
    created = not events_path.is_file()

    rel_envelope = normalize_path(Path(envelope_path).relative_to(root)) if envelope_path else None

    try:
        if created:
            events_path.parent.mkdir(parents=True, exist_ok=True)
            events_path.write_text("", encoding="utf-8")

        if not _has_trailing_newline(events_path):
            with open(events_path, "a", encoding="utf-8") as fh:
                fh.write("\n")

        with open(events_path, "a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        _rollback_events_file(events_path, original_size, created)
        return (
            "failed",
            None,
            0,
            [
                Finding(
                    rule_id="events-write-failed",
                    severity="error",
                    action="error",
                    message=f"Could not append lifecycle events: {exc}",
                )
            ],
        )

    rel_events_file = normalize_path(events_path.relative_to(root))
    resolved_tasks_file = tasks_file or "tasks/tasks.jsonl"
    validate_result = validate_records(root, rel_events_file, "event")
    ledger_result = check_ledger_consistency(
        root,
        tasks_file=resolved_tasks_file,
        events_file=rel_events_file,
    )
    audit_result = None
    if rel_envelope:
        audit_result = check_runtime_ledger(
            root,
            tasks_file=resolved_tasks_file,
            events_file=rel_events_file,
            envelope_file=rel_envelope,
        )

    findings: list[Finding] = []
    if validate_result.status != "pass":
        for finding in validate_result.findings:
            finding.message = f"Event schema validation: {finding.message}"
            findings.append(finding)

    if ledger_result.status != "pass":
        for finding in ledger_result.findings:
            finding.message = f"Ledger consistency: {finding.message}"
            findings.append(finding)

    post_ledger_check = ledger_result.status

    if audit_result is not None:
        if audit_result.status not in {"pass", "warn"}:
            post_ledger_check = audit_result.status
            for finding in audit_result.findings:
                finding.message = f"Runtime audit: {finding.message}"
                findings.append(finding)

    return validate_result.status, post_ledger_check, len(events), findings


def _rollback_ab(
    path: Path,
    rel_output: str,
    events_path: Path,
    original_event_size: int,
    event_created: bool,
) -> list[Finding]:
    """Roll back both A (envelope draft) and B (events ledger)."""
    findings: list[Finding] = []

    rollback_ok, rollback_err = _rollback_events_file(
        events_path, original_event_size, event_created
    )
    if not rollback_ok:
        findings.append(
            Finding(
                rule_id="events-rollback-failed",
                severity="error",
                action="error",
                message=f"Event ledger rollback failed: {rollback_err}",
            )
        )

    draft_rollback = _rollback_file(path, rel_output)
    if draft_rollback is not None:
        findings.extend(draft_rollback.findings)

    return findings


def commit_run(
    root: Path,
    task_id: str,
    request_id: str,
    capability: str,
    output: str | None,
    expected_plan_hash: str | None,
    events_file: str | None = None,
    adapter_id: str | None = None,
    operation: str | None = None,
    target: str | None = None,
    require_dry_run: bool = False,
    explicit_policy: Path | None = None,
    profile: str | None = None,
    actor: str = "cli",
    tasks_file: str | None = None,
    args: Any | None = None,
) -> RunCommitResult:
    """Persist a run plan as an envelope draft file plus lifecycle events.

    Recomputes the dry-run plan, validates the freeze guard, writes the envelope
    draft under ``drafts/runtime/...`` (A), then appends run lifecycle events to
    the event ledger (B). On any B failure, A is deleted and B is rolled back to
    its original byte size.
    """
    missing: list[str] = []
    if not output:
        missing.append("--output")
    if not expected_plan_hash:
        missing.append("--expected-plan-hash")
    if not events_file:
        missing.append("--events-file")
    if missing:
        return RunCommitResult(
            status="needs_input",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            findings=[
                Finding(
                    rule_id="missing-required-args",
                    severity="block",
                    action="needs_input",
                    message=f"Missing required arguments for commit: {', '.join(missing)}.",
                )
            ],
            next_action=f"Provide {', '.join(missing)} for commit.",
        )

    dry_run = dry_run_run(
        root,
        task_id=task_id,
        request_id=request_id,
        capability=capability,
        adapter_id=adapter_id,
        operation=operation,
        target=target,
        requested_mode="dry-run",
        explicit_policy=explicit_policy,
        profile=profile,
        actor=actor,
        tasks_file=tasks_file,
        args=args,
    )

    if dry_run.status != "pass":
        status = "blocked" if dry_run.status == "needs_approval" else dry_run.status
        return RunCommitResult(
            status=status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            expected_plan_hash=expected_plan_hash,
            freeze_check="not_run",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(dry_run.findings),
            next_action=dry_run.next_action
            or "Resolve blockers and re-run dry-run before commit.",
        )

    if dry_run.plan_hash != expected_plan_hash:
        return RunCommitResult(
            status="blocked",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="failed",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=[
                Finding(
                    rule_id="plan-hash-mismatch",
                    severity="block",
                    action="deny",
                    message="Expected plan hash does not match the current run plan.",
                )
            ],
            next_action="Re-run orchestration run --dry-run and review the new plan_hash.",
        )

    path_guard = _validate_output_path(root, output)
    if isinstance(path_guard, tuple):
        path, rel_output = path_guard
    else:
        return RunCommitResult(
            status=path_guard.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(path_guard.findings),
            next_action=path_guard.next_action,
        )

    drafts_guard = _validate_drafts_runtime_path(rel_output)
    if drafts_guard is not None:
        return RunCommitResult(
            status=drafts_guard.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(drafts_guard.findings),
            next_action=drafts_guard.next_action,
        )

    envelope = dry_run.envelope_draft
    if envelope is None:
        return RunCommitResult(
            status="error",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=[
                Finding(
                    rule_id="missing-envelope-draft",
                    severity="error",
                    action="error",
                    message="Dry-run succeeded but no envelope draft is available to commit.",
                )
            ],
            next_action="Review the adapter, operation, and target.",
        )

    scan_findings = _scan_export_content(root, envelope)
    if scan_findings:
        return RunCommitResult(
            status="blocked",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=scan_findings,
            next_action="Redact sensitive or public-release-risk content before committing.",
        )

    events_path_guard = _resolve_commit_events_path(root, events_file)
    if isinstance(events_path_guard, CheckResult):
        return RunCommitResult(
            status=events_path_guard.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(events_path_guard.findings),
            next_action=events_path_guard.next_action,
        )
    events_path = events_path_guard
    rel_events_file = normalize_path(events_path.relative_to(root))

    event_original_size = events_path.stat().st_size if events_path.is_file() else 0
    event_created = not events_path.is_file()

    built = _build_lifecycle_events(
        dry_run=dry_run,
        envelope_path=rel_output,
        events_file=rel_events_file,
        root=root,
        actor=actor,
    )
    if built is None or built[1]:
        findings = built[1] if built else []
        return RunCommitResult(
            status="blocked",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=findings,
            next_action="Lifecycle event failed schema or security scan; review inputs.",
        )
    lifecycle_events = built[0]

    write_error = _write_envelope_file(path, envelope)
    if write_error is not None:
        return RunCommitResult(
            status=write_error.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(write_error.findings),
            next_action=write_error.next_action,
        )

    post = _post_write_check(root, rel_output)
    if isinstance(post, tuple):
        post_validate, post_inspect, post_summary = post
    else:
        rollback_findings = _rollback_ab(path, rel_output, events_path, event_original_size, event_created)
        post.findings.extend(rollback_findings)
        return RunCommitResult(
            status=post.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            write_summary={
                "output": rel_output,
                "committed": False,
                "rolled_back": True,
                "post_validate": None,
                "post_inspect": None,
            },
            findings=list(post.findings),
            next_action="Draft was rolled back due to post-write check failure. "
            + (post.next_action or ""),
        )

    event_validate, event_ledger_check, appended_count, event_findings = _append_events_block(
        root,
        events_path,
        lifecycle_events,
        tasks_file=tasks_file,
        envelope_path=str(path),
    )

    if event_findings:
        rollback_findings = _rollback_ab(path, rel_output, events_path, event_original_size, event_created)
        all_findings = list(event_findings)
        all_findings.extend(rollback_findings)
        return RunCommitResult(
            status="blocked",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            write_summary={
                "output": rel_output,
                "events_file": rel_events_file,
                "committed": False,
                "rolled_back": True,
                "post_validate": post_validate,
                "post_inspect": post_inspect,
            },
            findings=all_findings,
            next_action="Lifecycle event append failed; both draft and events ledger were rolled back.",
        )

    artifact_counts = post_summary.get("artifact_counts", {})
    return RunCommitResult(
        status="pass",
        task_id=task_id,
        request_id=request_id,
        requested_capability=capability,
        plan_hash=dry_run.plan_hash,
        expected_plan_hash=expected_plan_hash,
        freeze_check="pass",
        dry_run_summary=_dry_run_summary(dry_run),
        write_summary={
            "output": rel_output,
            "events_file": rel_events_file,
            "committed": True,
            "rolled_back": False,
            "post_validate": post_validate,
            "post_inspect": post_inspect,
            "event_post_validate": event_validate,
            "event_post_ledger_check": event_ledger_check,
            "appended_event_count": appended_count,
        },
        artifact_ref=_artifact_ref(rel_output, dry_run),
        event_refs=[_event_ref(e) for e in lifecycle_events],
        next_action="Draft and lifecycle events committed; run runtime gate check before adapter execution.",
    )

"""Controlled commit for orchestration run plans.

This module persists an already-reviewed run plan as an adapter execution
envelope draft file. It does **not** execute adapters, access networks, send
messages, or append event ledger entries (A-only strategy per docs/58).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import normalize_path
from .orchestration_run_dry_run import RunDryRunResult, dry_run_run
from .result import Finding
from .runtime_draft_export import (
    _post_write_check,
    _rollback_file,
    _scan_export_content,
    _validate_drafts_runtime_path,
    _validate_output_path,
    _write_envelope_file,
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


def commit_run(
    root: Path,
    task_id: str,
    request_id: str,
    capability: str,
    output: str | None,
    expected_plan_hash: str | None,
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
    """Persist a run plan as an envelope draft file.

    Recomputes the dry-run plan, validates the freeze guard, and writes the
    envelope draft under ``drafts/runtime/...``. On write/post-check failure the
    newly created file is deleted.
    """
    missing: list[str] = []
    if not output:
        missing.append("--output")
    if not expected_plan_hash:
        missing.append("--expected-plan-hash")
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
                "committed": True,
                "rolled_back": False,
                "post_validate": post_validate,
                "post_inspect": post_inspect,
                "artifact_counts": artifact_counts,
            },
            artifact_ref=_artifact_ref(rel_output, dry_run),
            next_action="Draft committed; run runtime gate check before adapter execution.",
        )

    rollback_error = _rollback_file(path, rel_output)
    if rollback_error is not None:
        return RunCommitResult(
            status=rollback_error.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            plan_hash=dry_run.plan_hash,
            expected_plan_hash=expected_plan_hash,
            freeze_check="pass",
            dry_run_summary=_dry_run_summary(dry_run),
            findings=list(rollback_error.findings),
            next_action=rollback_error.next_action,
        )

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

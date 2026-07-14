"""Minimal read-only CLI entry point for agent-runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .adapter_approval import ApprovalCheckResult, check_adapter_approval
from .adapter_gate import GateCheckResult, check_adapter_gate
from .adapter_plan import PlanResult, plan_adapter_action
from .adapter_response import ResponseCheckResult, check_adapter_response
from .adapter_validation import inspect_envelope_file, validate_envelope_file
from .doctor import run_doctor
from .docs_context import DocsContextResult, get_docs_context
from .loader import load_adapters, load_agents, load_policies, discover_policies, normalize_path
from .policy import check_action, check_path, check_text
from .policy_profile import resolve_profile
from .result import CheckResult, emit, EXIT_ERROR, EXIT_PASS, _STATUS_TO_EXIT, Finding
from .ledger_consistency import check_ledger_consistency
from .runtime_gate import RuntimeGateResult, check_runtime_gate
from .runtime_ledger import RuntimeLedgerResult, check_runtime_ledger
from .runtime_draft import inspect_runtime_draft, validate_runtime_draft
from .runtime_draft_export import DraftExportResult, export_draft
from .runtime_event_append import EventAppendDryRunResult, append_event
from .runtime_event_import import (
    EventImportCommitResult,
    EventImportDryRunResult,
    import_events_commit,
    import_events_dry_run,
)
from .runtime_plan import RuntimePlanResult, plan_runtime_action
from .runtime_task_create import TaskCreateDryRunResult, create_task, create_task_dry_run
from .runtime_report import RuntimeReportResult, check_runtime_report
from .orchestration_adapter import AdapterDetailResult, AdapterListResult, get_adapter, list_adapters
from .orchestration_contract import build_contract_manifest
from .orchestration_contract_check import check_contract_requirements
from .orchestration_overview import OverviewSummary, check_overview
from .orchestration_profile import (
    check_automation_profile,
    inspect_automation_profile,
    list_automation_profiles,
)
from .orchestration_tasks import TaskDetailResult, TaskListResult, get_task, list_tasks
from .orchestration_task_submit import submit_task, TaskSubmitResult
from .orchestration_approval import ApprovalDetailResult, ApprovalListResult, get_approval, list_approvals
from .orchestration_approval_resolve import ApprovalResolveResult, resolve_approval
from .orchestration_artifact import ArtifactDetailResult, ArtifactListResult, get_artifact, list_artifacts
from .orchestration_preflight import PreflightResult, check_preflight
from .orchestration_report import ReportGenerateResult, generate_report
from .orchestration_route import RouteConstraints, RoutePreviewResult, preview_route
from .orchestration_routing_snapshot import (
    RoutingDecisionSnapshot,
    build_preflight_snapshot,
    build_routing_snapshot,
)
from .orchestration_read_loop_snapshot import (
    OrchestrationReadLoopSnapshot,
    build_read_loop_snapshot,
)
from .orchestration_run import RunInspectResult, RunListResult, inspect_run, list_runs
from .orchestration_run_dry_run import RunDryRunResult, dry_run_run
from .orchestration_run_commit import RunCommitResult, commit_run
from .task_validation import validate_records
from .tasks import find_task, find_task_events, render_task_events, render_task_status


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=argparse.SUPPRESS, help="Project root directory")
    parser.add_argument("--policy", default=argparse.SUPPRESS, help="Explicit policy file")
    parser.add_argument(
        "--policy-profile",
        default=argparse.SUPPRESS,
        help="Policy profile to load: s-black, wangcai, dabai, or all",
    )
    parser.add_argument("--agent", default=argparse.SUPPRESS, help="Agent id for automatic policy profile selection")
    parser.add_argument("--assignee", default=argparse.SUPPRESS, help="Assignee id for automatic policy profile selection")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON")
    parser.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS, help="Disable color output")
    parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help="Only output necessary results")
    parser.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS, help="Output more diagnostic info")


def _ensure_global_defaults(args: argparse.Namespace) -> None:
    defaults = {
        "root": ".",
        "policy": None,
        "policy_profile": None,
        "agent": None,
        "assignee": None,
        "json": False,
        "no_color": False,
        "quiet": False,
        "verbose": False,
    }
    for name, value in defaults.items():
        if not hasattr(args, name):
            setattr(args, name, value)


def _root_path(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _explicit_policy(args: argparse.Namespace, root: Path) -> Path | None:
    if args.policy is None:
        return None
    return (root / args.policy).resolve()


def _build_route_constraints_from_args(args: argparse.Namespace) -> RouteConstraints | None:
    """Return RouteConstraints only when the user explicitly passed any flag."""
    if (
        getattr(args, "preferred_adapter", None) is not None
        or getattr(args, "max_risk", None) is not None
        or getattr(args, "require_background", False)
        or getattr(args, "require_artifacts", False)
    ):
        return RouteConstraints(
            preferred_adapter=getattr(args, "preferred_adapter", None),
            require_background=getattr(args, "require_background", False),
            require_artifacts=getattr(args, "require_artifacts", False),
            max_risk=getattr(args, "max_risk", None),
        )
    return None


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = run_doctor(root)
    return emit(result, json_output=args.json, no_color=args.no_color)


def _emit_docs_context_result(result: DocsContextResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("DOCS CONTEXT")
        milestone = result.milestone
        print(
            f"milestone={milestone.get('tag') or '-'} "
            f"commit={milestone.get('commit') or '-'}"
        )
        stage = result.current_stage
        if stage:
            print(
                f"current_stage={stage.get('stage') or '-'} "
                f"status={stage.get('status') or '-'}"
            )
            description = stage.get("description")
            if description:
                print(f"  {description}")
        else:
            print("current_stage=-")

        entry = result.next_design_entry
        if entry:
            print(
                f"next_design_entry={entry.get('stage') or '-'}: "
                f"{entry.get('title') or '-'}"
            )
            path = entry.get("path")
            if path:
                print(f"  doc={path}")
            focus = entry.get("focus")
            if focus:
                for item in focus:
                    print(f"  - {item}")
        else:
            print("next_design_entry=-")

        print(f"recommended={len(result.recommended)}")
        for doc in result.recommended:
            print(f"- {doc['path']} ({doc['reason']})")

        summary = result.docs_summary
        print(
            f"docs_summary: total={summary.get('total_docs', 0)} "
            f"range={summary.get('numbered_range') or '-'} "
            f"latest={', '.join(summary.get('latest_docs', [])) or '-'}"
        )
        handoff = summary.get("latest_handoff")
        if handoff:
            print(f"latest_handoff={handoff}")

        if result.findings:
            print("Findings:")
            for finding in result.findings:
                print(f"- {finding}")
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_docs_context(args: argparse.Namespace) -> int:
    """Render a compact project documentation context recovery summary."""
    root = _root_path(args)
    result = get_docs_context(root)
    return _emit_docs_context_result(result, json_output=args.json)


def _read_text_source(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file is not None:
        path = Path(args.file)
        return path.read_text(encoding="utf-8")
    if args.stdin:
        return sys.stdin.read()
    raise argparse.ArgumentError(None, "Provide one of --text, --file, or --stdin")


def _cmd_check_text(args: argparse.Namespace) -> int:
    root = _root_path(args)
    policy_path = _explicit_policy(args, root)
    text = _read_text_source(args)
    result = check_text(root, text, explicit_policy=policy_path, profile=resolve_profile(args, root))
    return emit(result, json_output=args.json, no_color=args.no_color)


def _cmd_check_path(args: argparse.Namespace) -> int:
    root = _root_path(args)
    policy_path = _explicit_policy(args, root)
    result = check_path(
        root,
        args.path,
        read=args.read,
        write=args.write,
        delete=args.delete,
        explicit_policy=policy_path,
        profile=resolve_profile(args, root),
    )
    return emit(result, json_output=args.json, no_color=args.no_color)


def _cmd_check_action(args: argparse.Namespace) -> int:
    root = _root_path(args)
    policy_path = _explicit_policy(args, root)
    if not args.adapter or not args.operation:
        result = CheckResult(
            status="error",
            findings=[],
            next_action="--adapter and --operation are required for check action.",
        )
        return emit(result, json_output=args.json, no_color=args.no_color)
    result = check_action(
        root,
        args.adapter,
        args.operation,
        target=args.target,
        explicit_policy=policy_path,
        profile=resolve_profile(args, root),
    )
    return emit(result, json_output=args.json, no_color=args.no_color)


def _cmd_adapter_plan(args: argparse.Namespace) -> int:
    root = _root_path(args)
    if not args.adapter or not args.operation:
        result = PlanResult(
            status="error",
            findings=[],
            next_action="--adapter and --operation are required for adapter plan.",
            envelope=None,
        )
        return _emit_plan_result(result, json_output=args.json)

    plan_result = plan_adapter_action(
        root,
        args.adapter,
        args.operation,
        target=args.target,
        actor=args.actor or "cli",
        task_id=args.task_id,
        args=args,
    )
    return _emit_plan_result(plan_result, json_output=args.json)


def _emit_plan_result(result: PlanResult, json_output: bool) -> int:
    if json_output:
        if result.envelope is not None:
            print(json.dumps(result.envelope, ensure_ascii=False, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "findings": [f.to_dict() for f in result.findings],
                        "next_action": result.next_action,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    else:
        print(result.status.upper())
        for finding in result.findings:
            print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
        if result.envelope is not None:
            print(_render_plan_summary(result.envelope))
            print("Use --json to print the full adapter execution envelope.")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _render_plan_summary(envelope: dict[str, Any]) -> str:
    """Render a compact human summary for an adapter execution envelope."""
    lines = ["Artifacts:"]
    for artifact in envelope.get("artifacts", []):
        artifact_type = artifact.get("artifact_type", "unknown")
        if artifact_type == "adapter_request":
            preflight = artifact.get("preflight", {}).get("status", "unknown")
            lines.append(
                "- adapter_request "
                f"{artifact.get('request_id', '-')} "
                f"adapter={artifact.get('adapter_id', '-')} "
                f"operation={artifact.get('operation', '-')} "
                f"target={artifact.get('target', '-')} "
                f"preflight={preflight}"
            )
        elif artifact_type == "approval_record":
            scope = artifact.get("scope", {})
            lines.append(
                "- approval_record "
                f"{artifact.get('approval_id', '-')} "
                f"status={artifact.get('status', '-')} "
                f"operation={scope.get('operation', '-')} "
                f"target={scope.get('target', '-')}"
            )
        elif artifact_type == "execution_event":
            lines.append(
                "- execution_event "
                f"{artifact.get('event_id', '-')} "
                f"event_type={artifact.get('event_type', '-')}"
            )
        else:
            lines.append(f"- {artifact_type}")
    return "\n".join(lines)


def _cmd_adapter_validate(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = validate_envelope_file(root, args.file)
    return emit(result, json_output=args.json, no_color=args.no_color)


def _render_inspect_summary(summary: dict[str, Any]) -> str:
    """Render a compact human-readable summary of an envelope."""
    lines = ["PASS"]
    lines.append(
        f"Envelope: version={summary['version']}, description={summary['description']}"
    )

    artifact_counts = summary.get("artifact_counts", {})
    if artifact_counts:
        counts = ", ".join(f"{kind}={count}" for kind, count in artifact_counts.items())
        lines.append(f"Artifact counts: {counts}")
    else:
        lines.append("Artifact counts: none")

    lines.append("Requests:")
    for request in summary.get("requests", []):
        lines.append(
            f"- {request['request_id']} "
            f"{request['adapter_id']} "
            f"{request['operation']} "
            f"target={request['target']} "
            f"preflight={request['preflight_status']} "
            f"requires_approval={request['requires_approval']}"
        )

    approvals = summary.get("approvals", [])
    if approvals:
        lines.append("Approvals:")
        for approval in approvals:
            lines.append(
                f"- {approval['approval_id']} "
                f"request={approval['request_id']} "
                f"status={approval['status']}"
            )

    responses = summary.get("responses", [])
    if responses:
        lines.append("Responses:")
        for response in responses:
            lines.append(
                f"- {response['response_id']} "
                f"request={response['request_id']} "
                f"status={response['status']} "
                f"evidence={response['evidence_count']}"
            )

    event_counts = summary.get("events", {})
    if event_counts:
        events = ", ".join(f"{kind}={count}" for kind, count in event_counts.items())
        lines.append(f"Events: {events}")

    overall = summary.get("overall", {})
    flags = ", ".join(f"{name}={value}" for name, value in overall.items())
    lines.append(f"Overall: {flags}")

    return "\n".join(lines)


def _cmd_adapter_inspect(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result, summary = inspect_envelope_file(root, args.file)
    if result.status != "pass":
        return emit(result, json_output=args.json, no_color=args.no_color)

    if args.json:
        print(json.dumps({"status": "pass", "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print(_render_inspect_summary(summary))
    return EXIT_PASS


def _render_approval_summary(result: ApprovalCheckResult) -> str:
    """Render a compact human-readable approval check summary."""
    lines = [result.status.upper()]
    approval = result.approval
    if approval:
        summary_parts = [
            f"request_id={approval.get('request_id', '-')}",
            f"adapter_id={approval.get('adapter_id', '-')}",
            f"operation={approval.get('operation', '-')}",
            f"target={approval.get('target', '-')}",
            f"requires_approval={approval.get('requires_approval', '-')}",
        ]
        if approval.get("approval_id") is not None:
            summary_parts.append(f"approval_id={approval['approval_id']}")
        if approval.get("approval_status") is not None:
            summary_parts.append(f"approval_status={approval['approval_status']}")
        if approval.get("decision_ref") is not None:
            summary_parts.append(f"decision_ref={approval['decision_ref']}")
        lines.append(" ".join(summary_parts))
    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_approval_result(result: ApprovalCheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_approval_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_adapter_approval_check(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_adapter_approval(root, args.file, args.request_id)
    return _emit_approval_result(result, json_output=args.json)


def _render_response_summary(result: ResponseCheckResult) -> str:
    """Render a compact human-readable response check summary."""
    lines = [result.status.upper()]
    response = result.response
    if response:
        summary_parts = [
            f"request_id={response.get('request_id', '-')}",
            f"adapter_id={response.get('adapter_id', '-')}",
            f"operation={response.get('operation', '-')}",
            f"target={response.get('target', '-')}",
        ]
        if response.get("response_id") is not None:
            summary_parts.append(f"response_id={response['response_id']}")
        if response.get("response_status") is not None:
            summary_parts.append(f"response_status={response['response_status']}")
        if response.get("response_id") is not None:
            summary_parts.append(f"artifact_count={response.get('artifact_count', 0)}")
            summary_parts.append(f"evidence_count={response.get('evidence_count', 0)}")
            summary_parts.append(f"raw_ref_present={response.get('raw_ref_present', False)}")
        lines.append(" ".join(summary_parts))
    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_response_result(result: ResponseCheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_response_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_adapter_response_check(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_adapter_response(root, args.file, args.request_id)
    return _emit_response_result(result, json_output=args.json)


def _render_gate_summary(result: GateCheckResult) -> str:
    """Render a compact human-readable gate check summary."""
    lines = [result.status.upper()]
    gate = result.gate
    if gate:
        summary_parts = [
            f"stage={gate.get('stage', '-')}",
            f"request_id={gate.get('request_id', '-')}",
            f"approval_status={gate.get('approval_status', '-')}",
            f"response_status={gate.get('response_status', '-')}",
            f"can_proceed={gate.get('can_proceed', False)}",
        ]
        lines.append(" ".join(summary_parts))
    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_gate_result(result: GateCheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_gate_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_adapter_gate_check(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_adapter_gate(root, args.file, args.request_id)
    return _emit_gate_result(result, json_output=args.json)


def _render_runtime_draft_summary(summary: dict[str, Any]) -> str:
    """Render a compact human-readable runtime draft summary."""
    lines = ["PASS"]
    lines.append(f"Source: {summary['source']}")
    if "task_id" in summary:
        lines.append(f"task_id: {summary['task_id']}")
    if "status" in summary:
        lines.append(f"plan_status: {summary['status']}")
    lines.append(
        f"Envelope: version={summary['version']}, description={summary['description']}"
    )

    artifact_counts = summary.get("artifact_counts", {})
    if artifact_counts:
        counts = ", ".join(f"{kind}={count}" for kind, count in artifact_counts.items())
        lines.append(f"Artifact counts: {counts}")
    else:
        lines.append("Artifact counts: none")

    lines.append("Requests:")
    for request in summary.get("requests", []):
        lines.append(
            f"- {request['request_id']} "
            f"{request['adapter_id']} "
            f"{request['operation']} "
            f"preflight={request['preflight_status']} "
            f"requires_approval={request['requires_approval']} "
            f"risk={request['risk_level']}"
        )

    approvals = summary.get("approvals", [])
    if approvals:
        lines.append("Approvals:")
        for approval in approvals:
            lines.append(
                f"- {approval['approval_id']} "
                f"request={approval['request_id']} "
                f"status={approval['status']}"
            )

    event_counts = summary.get("events", {})
    if event_counts:
        events = ", ".join(f"{kind}={count}" for kind, count in event_counts.items())
        lines.append(f"Events: {events}")

    overall = summary.get("overall", {})
    flags = ", ".join(f"{name}={value}" for name, value in overall.items())
    lines.append(f"Overall: {flags}")

    return "\n".join(lines)


def _cmd_runtime_draft_validate(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = validate_runtime_draft(root, file=args.file, stdin=args.stdin)
    return emit(result, json_output=args.json, no_color=args.no_color)


def _cmd_runtime_draft_inspect(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result, summary = inspect_runtime_draft(root, file=args.file, stdin=args.stdin)
    if result.status != "pass":
        return emit(result, json_output=args.json, no_color=args.no_color)

    if args.json:
        print(json.dumps({"status": "pass", "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_draft_summary(summary))
    return EXIT_PASS


def _render_runtime_draft_export_summary(result: DraftExportResult) -> str:
    """Render a compact human-readable export summary."""
    lines = [result.status.upper()]
    if result.source is not None:
        lines.append(f"Source: {result.source}")
    if result.output is not None:
        lines.append(f"Output: {result.output}")
    lines.append(f"Committed: {result.committed}")
    if result.validation is not None:
        lines.append(f"Validation: {result.validation}")
    if result.post_validate is not None:
        lines.append(f"Post validate: {result.post_validate}")
    if result.post_inspect is not None:
        lines.append(f"Post inspect: {result.post_inspect}")
    if result.artifact_counts:
        counts = ", ".join(
            f"{kind}={count}" for kind, count in result.artifact_counts.items()
        )
        lines.append(f"Artifact counts: {counts}")
    for finding in result.findings:
        loc = ""
        if finding.line is not None:
            loc = f" at line {finding.line}"
        lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_runtime_draft_export_result(
    result: DraftExportResult, json_output: bool
) -> int:
    """Print a draft export result and return the appropriate exit code."""
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_draft_export_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_runtime_draft_export(args: argparse.Namespace) -> int:
    root = _root_path(args)
    dry_run = getattr(args, "dry_run", False)
    commit = getattr(args, "commit", False)
    if dry_run and commit:
        result = DraftExportResult(
            status="error",
            findings=[
                Finding(
                    rule_id="dry-run-commit-mutually-exclusive",
                    severity="error",
                    action="error",
                    message="--dry-run and --commit are mutually exclusive.",
                )
            ],
            next_action="Provide either --dry-run or --commit, not both.",
        )
        return _emit_runtime_draft_export_result(result, json_output=args.json)

    if not dry_run and not commit:
        result = DraftExportResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-export-mode",
                    severity="error",
                    action="error",
                    message="Provide either --dry-run or --commit.",
                )
            ],
            next_action="Add --dry-run for read-only mode or --commit to persist the draft.",
        )
        return _emit_runtime_draft_export_result(result, json_output=args.json)

    result = export_draft(
        root,
        output=args.output,
        file=args.file,
        stdin=args.stdin,
        commit=commit,
    )
    return _emit_runtime_draft_export_result(result, json_output=args.json)


def _render_runtime_event_append_summary(result: CheckResult) -> str:
    """Render runtime event append dry-run output.

    EventAppendDryRunResult carries only safe identifiers/counts; fallback keeps
    ordinary CheckResult rendering for errors raised before a candidate is known.
    """
    if not isinstance(result, EventAppendDryRunResult):
        return result.render_human()

    lines = [result.status.upper()]
    if result.source is not None:
        lines.append(f"Source: {result.source}")
    if result.event_id is not None:
        lines.append(f"event_id={result.event_id}")
    if result.task_id is not None:
        lines.append(f"task_id={result.task_id}")
    if result.event_type is not None:
        lines.append(f"event_type={result.event_type}")
    if result.from_status is not None:
        lines.append(f"from_status={result.from_status}")
    if result.to_status is not None:
        lines.append(f"to_status={result.to_status}")
    lines.append(f"would_append={result.would_append}")
    if result.ledger_check is not None:
        lines.append(f"ledger_check={result.ledger_check}")
    if result.runtime_audit is not None:
        lines.append(f"runtime_audit={result.runtime_audit}")
    lines.append(f"committed={result.committed}")
    if result.post_validate is not None:
        lines.append(f"post_validate={result.post_validate}")
    if result.post_ledger_check is not None:
        lines.append(f"post_ledger_check={result.post_ledger_check}")
    if result.post_runtime_audit is not None:
        lines.append(f"post_runtime_audit={result.post_runtime_audit}")
    if result.rolled_back:
        lines.append(f"rolled_back={result.rolled_back}")
    if result.rollback_error is not None:
        lines.append(f"rollback_error={result.rollback_error}")
    if result.metadata_keys:
        lines.append("metadata_keys=" + ",".join(result.metadata_keys))
    if result.artifact_count is not None:
        lines.append(f"artifact_count={result.artifact_count}")
    for finding in result.findings:
        loc = ""
        if finding.line is not None:
            loc = f" at line {finding.line}"
        lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_runtime_event_append_result(result: CheckResult, json_output: bool, no_color: bool = False) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_event_append_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _render_runtime_event_import_summary(result: CheckResult) -> str:
    """Render runtime event import dry-run or commit output.

    Both result types carry only safe counts and identifiers; fallback keeps
    ordinary CheckResult rendering for errors raised before parsing.
    """
    if isinstance(result, EventImportDryRunResult):
        lines = [result.status.upper()]
        if result.source is not None:
            lines.append(f"Source: {result.source}")
        lines.append(f"event_count={result.event_count}")
        lines.append(f"blank_line_count={result.blank_line_count}")
        lines.append(f"task_count={result.task_count}")
        if result.event_type_counts:
            counts = ", ".join(f"{k}:{v}" for k, v in result.event_type_counts.items())
            lines.append(f"event_type_counts={counts}")
        else:
            lines.append("event_type_counts=")
        lines.append(f"would_import={result.would_import}")
        if result.ledger_check is not None:
            lines.append(f"ledger_check={result.ledger_check}")
        lines.append(f"freeze_mode={result.freeze_mode}")
        if result.candidate_fingerprint is not None:
            lines.append(f"candidate_fingerprint={result.candidate_fingerprint}")
        lines.append(f"events_ledger_exists={result.events_ledger_exists}")
        if result.events_ledger_fingerprint is not None:
            lines.append(f"events_ledger_fingerprint={result.events_ledger_fingerprint}")
        lines.append(f"events_ledger_size_bytes={result.events_ledger_size_bytes}")
        lines.append(f"events_ledger_line_count={result.events_ledger_line_count}")
        if result.plan_hash is not None:
            lines.append(f"plan_hash={result.plan_hash}")
        for finding in result.findings:
            loc = ""
            if finding.line is not None:
                loc = f" at line {finding.line}"
            lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
        if result.next_action:
            lines.append(f"Next: {result.next_action}")
        return "\n".join(lines)

    if isinstance(result, EventImportCommitResult):
        lines = [result.status.upper()]
        if result.source is not None:
            lines.append(f"Source: {result.source}")
        lines.append(f"event_count={result.event_count}")
        lines.append(f"blank_line_count={result.blank_line_count}")
        lines.append(f"task_count={result.task_count}")
        if result.event_type_counts:
            counts = ", ".join(f"{k}:{v}" for k, v in result.event_type_counts.items())
            lines.append(f"event_type_counts={counts}")
        else:
            lines.append("event_type_counts=")
        if result.target_events_file is not None:
            lines.append(f"target_events_file={result.target_events_file}")
        lines.append(f"committed={result.committed}")
        lines.append(f"appended_line_count={result.appended_line_count}")
        if result.post_validate is not None:
            lines.append(f"post_validate={result.post_validate}")
        if result.post_ledger_check is not None:
            lines.append(f"post_ledger_check={result.post_ledger_check}")
        if result.rolled_back:
            lines.append(f"rolled_back={result.rolled_back}")
        if result.rollback_error is not None:
            lines.append(f"rollback_error={result.rollback_error}")
        if result.freeze_check is not None:
            lines.append(f"freeze_check={result.freeze_check}")
        if result.expected_plan_hash is not None:
            lines.append(f"expected_plan_hash={result.expected_plan_hash}")
        if result.current_plan_hash is not None:
            lines.append(f"current_plan_hash={result.current_plan_hash}")
        for finding in result.findings:
            loc = ""
            if finding.line is not None:
                loc = f" at line {finding.line}"
            lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
        if result.next_action:
            lines.append(f"Next: {result.next_action}")
        return "\n".join(lines)

    return result.render_human()


def _emit_runtime_event_import_result(result: CheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_event_import_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_runtime_event_import(args: argparse.Namespace) -> int:
    root = _root_path(args)
    dry_run = getattr(args, "dry_run", False)
    commit = getattr(args, "commit", False)
    if dry_run and commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="dry-run-commit-mutually-exclusive",
                    severity="error",
                    action="error",
                    message="--dry-run and --commit are mutually exclusive.",
                )
            ],
            next_action="Provide either --dry-run or --commit, not both.",
        )
        return _emit_runtime_event_import_result(result, json_output=args.json)
    if not dry_run and not commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-import-mode",
                    severity="error",
                    action="error",
                    message="Provide either --dry-run or --commit.",
                )
            ],
            next_action="Add --dry-run to simulate the import or --commit to persist the batch.",
        )
        return _emit_runtime_event_import_result(result, json_output=args.json)

    require_dry_run = getattr(args, "require_dry_run", False)
    if require_dry_run and dry_run:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="require-dry-run-with-dry-run",
                    severity="error",
                    action="error",
                    message="--require-dry-run cannot be used with --dry-run.",
                )
            ],
            next_action="Use --require-dry-run only with --commit.",
        )
        return _emit_runtime_event_import_result(result, json_output=args.json)
    if require_dry_run and not commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="require-dry-run-requires-commit",
                    severity="error",
                    action="error",
                    message="--require-dry-run can only be used with --commit.",
                )
            ],
            next_action="Add --commit, or remove --require-dry-run.",
        )
        return _emit_runtime_event_import_result(result, json_output=args.json)

    if dry_run:
        result = import_events_dry_run(
            root,
            file=args.file,
            tasks_file=args.tasks_file,
            events_file=args.events_file,
        )
    else:
        result = import_events_commit(
            root,
            file=args.file,
            tasks_file=args.tasks_file,
            events_file=args.events_file,
            expected_plan_hash=getattr(args, "expected_plan_hash", None),
            require_dry_run=require_dry_run,
        )
    return _emit_runtime_event_import_result(result, json_output=args.json)


def _render_runtime_task_create_summary(result: CheckResult) -> str:
    """Render runtime task create dry-run output.

    TaskCreateDryRunResult carries only safe identifiers/counts; fallback keeps
    ordinary CheckResult rendering for errors raised before a candidate is known.
    """
    if not isinstance(result, TaskCreateDryRunResult):
        return result.render_human()

    lines = [result.status.upper()]
    if result.source is not None:
        lines.append(f"Source: {result.source}")
    if result.task_id is not None:
        lines.append(f"task_id={result.task_id}")
    if result.task_status is not None:
        lines.append(f"status={result.task_status}")
    lines.append(f"title_present={result.title_present}")
    lines.append(f"assignee_present={result.assignee_present}")
    if result.tag_count is not None:
        lines.append(f"tag_count={result.tag_count}")
    if result.artifact_count is not None:
        lines.append(f"artifact_count={result.artifact_count}")
    if result.evidence_count is not None:
        lines.append(f"evidence_count={result.evidence_count}")
    lines.append(f"would_create={result.would_create}")
    if result.ledger_check is not None:
        lines.append(f"ledger_check={result.ledger_check}")
    lines.append(f"committed={result.committed}")
    if result.post_validate is not None:
        lines.append(f"post_validate={result.post_validate}")
    if result.post_ledger_check is not None:
        lines.append(f"post_ledger_check={result.post_ledger_check}")
    if result.rolled_back:
        lines.append(f"rolled_back={result.rolled_back}")
    if result.rollback_error is not None:
        lines.append(f"rollback_error={result.rollback_error}")
    if result.metadata_keys:
        lines.append("metadata_keys=" + ",".join(result.metadata_keys))
    for finding in result.findings:
        loc = ""
        if finding.line is not None:
            loc = f" at line {finding.line}"
        lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_runtime_task_create_result(result: CheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_task_create_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _render_orchestration_task_submit_summary(result: CheckResult) -> str:
    """Render a compact human-readable orchestration task submit summary."""
    if not isinstance(result, TaskSubmitResult):
        return result.render_human()

    lines = [result.status.upper()]
    if result.source is not None:
        lines.append(f"Source: {result.source}")
    if result.task_id is not None:
        lines.append(f"task_id={result.task_id}")
    if result.event_id is not None:
        lines.append(f"event_id={result.event_id}")
    if result.task_status is not None:
        lines.append(f"status={result.task_status}")
    lines.append(f"title_present={result.title_present}")
    lines.append(f"assignee_present={result.assignee_present}")
    if result.tag_count is not None:
        lines.append(f"tag_count={result.tag_count}")
    if result.artifact_count is not None:
        lines.append(f"artifact_count={result.artifact_count}")
    if result.evidence_count is not None:
        lines.append(f"evidence_count={result.evidence_count}")
    lines.append(f"would_create={result.would_create}")
    lines.append(f"would_append_created_event={result.would_append_created_event}")
    if result.ledger_check is not None:
        lines.append(f"ledger_check={result.ledger_check}")
    lines.append(f"committed={result.committed}")
    lines.append(f"created_event_committed={result.created_event_committed}")
    if result.post_validate_tasks is not None:
        lines.append(f"post_validate_tasks={result.post_validate_tasks}")
    if result.post_validate_events is not None:
        lines.append(f"post_validate_events={result.post_validate_events}")
    if result.post_ledger_check is not None:
        lines.append(f"post_ledger_check={result.post_ledger_check}")
    if result.rolled_back:
        lines.append(f"rolled_back={result.rolled_back}")
    if result.rollback_error is not None:
        lines.append(f"rollback_error={result.rollback_error}")
    if result.metadata_keys:
        lines.append("metadata_keys=" + ",".join(result.metadata_keys))
    for finding in result.findings:
        loc = ""
        if finding.line is not None:
            loc = f" at line {finding.line}"
        lines.append(f"- {finding.rule_id}{loc}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_orchestration_task_submit_result(result: CheckResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_orchestration_task_submit_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_runtime_task_create(args: argparse.Namespace) -> int:
    root = _root_path(args)
    dry_run = getattr(args, "dry_run", False)
    commit = getattr(args, "commit", False)
    if dry_run and commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="dry-run-commit-mutually-exclusive",
                    severity="error",
                    action="error",
                    message="--dry-run and --commit are mutually exclusive.",
                )
            ],
            next_action="Provide either --dry-run or --commit, not both.",
        )
        return _emit_runtime_task_create_result(result, json_output=args.json)
    if not dry_run and not commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-create-mode",
                    severity="error",
                    action="error",
                    message="Provide either --dry-run or --commit.",
                )
            ],
            next_action="Add --dry-run for read-only mode or --commit to persist the task.",
        )
        return _emit_runtime_task_create_result(result, json_output=args.json)
    result = create_task(
        root,
        file=args.file,
        stdin=args.stdin,
        commit=commit,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
    )
    return _emit_runtime_task_create_result(result, json_output=args.json)


def _cmd_runtime_event_append(args: argparse.Namespace) -> int:
    root = _root_path(args)
    dry_run = getattr(args, "dry_run", False)
    commit = getattr(args, "commit", False)
    if dry_run and commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="dry-run-commit-mutually-exclusive",
                    severity="error",
                    action="error",
                    message="--dry-run and --commit are mutually exclusive.",
                )
            ],
            next_action="Provide either --dry-run or --commit, not both.",
        )
        return _emit_runtime_event_append_result(result, json_output=args.json, no_color=args.no_color)
    if not dry_run and not commit:
        result = CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-append-mode",
                    severity="error",
                    action="error",
                    message="Provide either --dry-run or --commit.",
                )
            ],
            next_action="Add --dry-run for read-only mode or --commit to persist the event.",
        )
        return _emit_runtime_event_append_result(result, json_output=args.json, no_color=args.no_color)
    result = append_event(
        root,
        file=args.file,
        stdin=args.stdin,
        commit=commit,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
        envelope_file=args.envelope,
    )
    return _emit_runtime_event_append_result(result, json_output=args.json, no_color=args.no_color)


def _render_runtime_gate_summary(result: RuntimeGateResult) -> str:
    """Render a compact human-readable runtime gate summary."""
    lines = [result.status.upper()]
    lines.append(
        f"task_id={result.task_id} "
        f"task_status={result.task_status or '-'} "
        f"request_id={result.request_id or '-'}"
    )

    gate = result.gate
    if gate:
        lines.append(
            f"gate: stage={gate.get('stage', '-')} "
            f"approval_status={gate.get('approval_status', '-')} "
            f"response_status={gate.get('response_status', '-')} "
            f"can_proceed={gate.get('can_proceed', False)}"
        )

    draft = result.suggested_event_draft
    if draft is not None:
        lines.append("Suggested event draft:")
        lines.append(f"- event_type: {draft.get('event_type', '-')}")
        lines.append(f"  from_status: {draft.get('from_status', '-')}")
        lines.append(f"  to_status: {draft.get('to_status', '-')}")
        lines.append(f"  message: {draft.get('message', '-')}")
        metadata = draft.get("metadata", {})
        metadata_str = ", ".join(f"{k}={v}" for k, v in metadata.items())
        lines.append(f"  metadata: {{{metadata_str}}}")

    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")

    if result.next_action:
        lines.append(f"Next: {result.next_action}")

    return "\n".join(lines)


def _emit_runtime_gate_result(result: RuntimeGateResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_gate_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _render_runtime_plan_summary(result: RuntimePlanResult) -> str:
    """Render a compact human-readable runtime plan summary."""
    lines = [result.status.upper()]
    lines.append(
        f"task_id={result.task_id} task_status={result.task_status or '-'}"
    )

    request = result.request_draft
    if request is not None:
        lines.append(
            f"request_draft: "
            f"request_id={request.get('request_id', '-')} "
            f"adapter={request.get('adapter_id', '-')} "
            f"operation={request.get('operation', '-')} "
            f"target={request.get('target', '-')} "
            f"profile={request.get('policy_profile', '-')} "
            f"risk={request.get('risk_level', '-')} "
            f"requires_approval={request.get('requires_approval', '-')} "
            f"preflight={request.get('preflight_status', '-')}"
        )

    approval = result.approval_draft
    if approval is not None:
        lines.append(
            f"approval_draft: "
            f"approval_id={approval.get('approval_id', '-')} "
            f"request_id={approval.get('request_id', '-')} "
            f"status={approval.get('status', '-')}"
        )

    event = result.event_draft
    if event is not None:
        parts = [
            f"event_id={event.get('event_id', '-')}",
            f"event_type={event.get('event_type', '-')}",
        ]
        if event.get("approval_id") is not None:
            parts.append(f"approval_id={event['approval_id']}")
        if event.get("adapter_id") is not None:
            parts.append(f"adapter={event['adapter_id']}")
        if event.get("operation") is not None:
            parts.append(f"operation={event['operation']}")
        lines.append(f"event_draft: {' '.join(parts)}")

    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")

    if result.next_action:
        lines.append(f"Next: {result.next_action}")

    return "\n".join(lines)


def _emit_runtime_plan_result(
    result: RuntimePlanResult, json_output: bool, draft_json: bool = False
) -> int:
    if draft_json:
        draft: dict[str, Any] = {
            "status": result.status,
            "task_id": result.task_id,
            "task_status": result.task_status,
            "envelope_draft": result.envelope_draft,
        }
        if result.findings:
            draft["findings"] = [f.to_dict() for f in result.findings]
        if result.next_action is not None:
            draft["next_action"] = result.next_action
        print(json.dumps(draft, ensure_ascii=False, indent=2))
    elif json_output:
        # Preserve the original compact summary shape for backward compatibility.
        summary = result.to_dict()
        summary.pop("envelope_draft", None)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_plan_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_runtime_plan(args: argparse.Namespace) -> int:
    root = _root_path(args)
    draft_json = getattr(args, "draft_json", False)
    if not args.adapter or not args.operation:
        result = RuntimePlanResult(
            status="error",
            task_id=args.task_id or "-",
            findings=[
                Finding(
                    rule_id="missing-args",
                    severity="error",
                    action="error",
                    message="--adapter and --operation are required for runtime plan.",
                )
            ],
            next_action="Provide --adapter and --operation.",
        )
        return _emit_runtime_plan_result(result, json_output=args.json, draft_json=draft_json)

    result = plan_runtime_action(
        root,
        task_id=args.task_id,
        adapter_id=args.adapter,
        operation=args.operation,
        target=args.target,
        actor=args.actor or "cli",
        args=args,
        tasks_file=args.tasks_file,
    )
    return _emit_runtime_plan_result(result, json_output=args.json, draft_json=draft_json)


def _render_runtime_ledger_summary(result: RuntimeLedgerResult) -> str:
    """Render a compact human-readable runtime ledger audit summary."""
    lines = [result.status.upper()]
    counts = result.counts
    if counts:
        parts = ", ".join(f"{k}={v}" for k, v in counts.items())
        lines.append(f"counts: {parts}")
    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")
    if result.next_action:
        lines.append(f"Next: {result.next_action}")
    return "\n".join(lines)


def _emit_runtime_ledger_result(result: RuntimeLedgerResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_ledger_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _render_runtime_report_summary(result: RuntimeReportResult) -> str:
    """Render a compact human-readable runtime report."""
    lines = [result.status.upper()]
    lines.append(
        f"Task: {result.task_id} "
        f"({result.task_status or '-'}): title_present={result.task_snapshot.get('title_present', False)}"
    )

    event_summary = result.event_summary
    if event_summary:
        total = event_summary.get("total", 0)
        latest = event_summary.get("latest", {})
        latest_type = latest.get("event_type", "-")
        latest_ts = latest.get("timestamp", "-")
        lines.append(f"Events: {total} events, latest={latest_type} at {latest_ts}")

    envelope = result.envelope_summary
    if envelope is not None:
        artifact_counts = envelope.get("artifact_counts", {})
        counts = ", ".join(f"{k}={v}" for k, v in artifact_counts.items())
        lines.append(f"Envelope: {counts or 'no artifacts'}")
    else:
        lines.append("Envelope: validation failed")

    gate = result.gate
    if gate is not None:
        lines.append(
            f"Gate: stage={gate.get('stage', '-')}, "
            f"can_proceed={gate.get('can_proceed', False)}"
        )
    else:
        lines.append("Gate: unavailable")

    ledger = result.ledger
    if ledger is not None:
        counts = ledger.get("counts", {})
        counts_str = ", ".join(f"{k}={v}" for k, v in counts.items())
        lines.append(f"Ledger: {ledger.get('status', '-')} ({counts_str})")
    else:
        lines.append("Ledger: unavailable")

    if result.blockers:
        lines.append("Blockers:")
        for blocker in result.blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("Blockers: none")

    for finding in result.findings:
        lines.append(f"- {finding.rule_id}: {finding.message}")

    if result.next_action:
        lines.append(f"Next: {result.next_action}")

    return "\n".join(lines)


def _emit_runtime_report_result(result: RuntimeReportResult, json_output: bool) -> int:
    """Print a runtime report and return the appropriate exit code."""
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_runtime_report_summary(result))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_runtime_report(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_runtime_report(
        root,
        task_id=args.task_id,
        request_id=args.request_id,
        envelope_file=args.envelope,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
    )
    return _emit_runtime_report_result(result, json_output=args.json)


def _cmd_runtime_check_ledger(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_runtime_ledger(
        root,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
        envelope_file=args.envelope,
    )
    return _emit_runtime_ledger_result(result, json_output=args.json)


def _cmd_runtime_gate_check(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_runtime_gate(
        root,
        task_id=args.task_id,
        request_id=args.request_id,
        envelope_file=args.envelope,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
    )
    return _emit_runtime_gate_result(result, json_output=args.json)


def _cmd_agents_list(args: argparse.Namespace) -> int:
    root = _root_path(args)
    data = load_agents(root)
    agents = data.get("agents", [])
    if args.capability:
        agents = [a for a in agents if args.capability in a.get("capabilities", [])]

    if args.json:
        print(json.dumps({"agents": agents}, ensure_ascii=False, indent=2))
        return EXIT_PASS

    for agent in agents:
        enabled = "enabled" if agent.get("enabled") else "disabled"
        caps = ", ".join(agent.get("capabilities", []))
        print(f"{agent['id']:<15} {enabled:<8} {caps}")
    return EXIT_PASS


def _cmd_adapters_list(args: argparse.Namespace) -> int:
    root = _root_path(args)
    data = load_adapters(root)
    adapters = data.get("adapters", [])
    if args.kind:
        adapters = [a for a in adapters if a.get("kind") == args.kind]
    if args.risk:
        adapters = [a for a in adapters if a.get("risk_level") == args.risk]

    if args.json:
        print(json.dumps({"adapters": adapters}, ensure_ascii=False, indent=2))
        return EXIT_PASS

    for adapter in adapters:
        approval = "approval required" if adapter.get("requires_approval") else "no default approval"
        print(f"{adapter['id']:<16} {adapter.get('kind', '-'):<12} {adapter.get('risk_level', '-'):<12} {approval}")
    return EXIT_PASS


def _cmd_policies_list(args: argparse.Namespace) -> int:
    root = _root_path(args)
    policy_paths = discover_policies(root, explicit=_explicit_policy(args, root), profile=resolve_profile(args, root))
    rows: list[dict[str, Any]] = []
    for path in policy_paths:
        policy = load_policies(root, explicit=path)[0]
        rows.append(
            {
                "path": normalize_path(path.relative_to(root)),
                "name": policy.get("name", ""),
                "path_rules": len(policy.get("path_rules", [])),
                "secret_patterns": len(policy.get("secret_patterns", [])),
                "command_rules": len(policy.get("command_rules", [])),
                "publish_rules": len(policy.get("publish_rules", [])),
                "completion_rules": len(policy.get("completion_rules", [])),
            }
        )

    if args.json:
        print(json.dumps({"policies": rows}, ensure_ascii=False, indent=2))
        return EXIT_PASS

    for row in rows:
        print(
            f"{row['path']:<48} "
            f"path={row['path_rules']} secret={row['secret_patterns']} "
            f"command={row['command_rules']} publish={row['publish_rules']} "
            f"completion={row['completion_rules']}"
        )
    return EXIT_PASS


def _cmd_orchestration_profile_list(args: argparse.Namespace) -> int:
    """List project Automation Profiles without executing requirements."""
    result = list_automation_profiles(_root_path(args))
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render_human())
    return result.exit_code()


def _cmd_orchestration_profile_inspect(args: argparse.Namespace) -> int:
    """Inspect one project Automation Profile."""
    result = inspect_automation_profile(_root_path(args), args.profile_id)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render_human())
    return result.exit_code()


def _cmd_orchestration_profile_check(args: argparse.Namespace) -> int:
    """Evaluate one project Automation Profile through the Requirement Gate."""
    result = check_automation_profile(_root_path(args), args.profile_id)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render_human())
    return result.exit_code()


def _cmd_orchestration_contract_check(args: argparse.Namespace) -> int:
    """Evaluate required contract capabilities without executing commands."""
    result = check_contract_requirements(
        args.required_contracts,
        allow_preview=args.allow_preview,
        max_access=args.max_access,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.render_human())
    return result.exit_code()


def _cmd_orchestration_contract_inspect(args: argparse.Namespace) -> int:
    """Render the machine-readable orchestration capability contract."""
    manifest = build_contract_manifest()
    payload = manifest.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("ORCHESTRATION CONTRACT")
        print(f"schema_version={manifest.schema_version}")
        summary = payload["summary"]
        print("summary: " + " ".join(f"{key}={value}" for key, value in summary.items()))
        print("entries:")
        for entry in manifest.entries:
            command = " | ".join(" ".join(parts) for parts in entry.commands) or "-"
            print(
                f"- {entry.contract_id} {entry.availability} "
                f"{entry.access} {command}"
            )
    return EXIT_PASS


def _cmd_orchestration_overview(args: argparse.Namespace) -> int:
    """Render a read-only orchestration overview summary."""
    root = _root_path(args)
    summary = check_overview(root)
    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("OVERVIEW")
        summary_dict = summary.to_dict()["summary"]
        summary_parts = " ".join(f"{k}={v}" for k, v in summary_dict.items())
        print(f"summary: {summary_parts}")
        if summary.recent_tasks:
            print("recent_tasks:")
            for task in summary.recent_tasks:
                capability = task.get("requested_capability") or "-"
                print(
                    f"- {task['task_id']} "
                    f"{task['status']} "
                    f"{capability} "
                    f"updated_at={task['updated_at']}"
                )
    return EXIT_PASS


def _cmd_orchestration_route_preview(args: argparse.Namespace) -> int:
    """Render a read-only capability routing preview."""
    root = _root_path(args)
    capability = args.capability
    requested_mode = getattr(args, "mode", "dry-run")
    if requested_mode not in {"dry-run", "commit"}:
        result = RoutePreviewResult(
            status="error",
            requested_capability=capability,
            findings=[
                Finding(
                    rule_id="invalid-mode",
                    severity="error",
                    action="error",
                    message="--mode must be 'dry-run' or 'commit'.",
                )
            ],
            next_action="Provide --mode dry-run or --mode commit.",
        )
        return _emit_route_preview_result(result, json_output=args.json)

    route_constraints: RouteConstraints | None = None
    if (
        getattr(args, "preferred_adapter", None) is not None
        or getattr(args, "max_risk", None) is not None
        or getattr(args, "require_background", False)
        or getattr(args, "require_artifacts", False)
    ):
        route_constraints = RouteConstraints(
            preferred_adapter=getattr(args, "preferred_adapter", None),
            require_background=getattr(args, "require_background", False),
            require_artifacts=getattr(args, "require_artifacts", False),
            max_risk=getattr(args, "max_risk", None),
        )

    result = preview_route(
        root,
        capability=capability,
        task_id=getattr(args, "task_id", None),
        adapter_id=getattr(args, "adapter", None),
        requested_mode=requested_mode,
        constraints=route_constraints,
        explain=getattr(args, "explain", False),
    )
    return _emit_route_preview_result(result, json_output=args.json)


def _cmd_orchestration_route_snapshot(args: argparse.Namespace) -> int:
    """Render a deterministic routing decision snapshot (read-only)."""
    root = _root_path(args)
    capability = args.capability
    requested_mode = getattr(args, "mode", "dry-run")
    task_id = getattr(args, "task_id", None)
    request_id = getattr(args, "request_id", None)
    if requested_mode not in {"dry-run", "commit"}:
        snapshot = RoutingDecisionSnapshot(
            schema_version="control-plane/routing-decision/v1",
            snapshot_id="",
            status="error",
            routing={
                "requested_capability": capability,
                "requested_mode": requested_mode,
            },
            constraints={},
            source={"task_id": task_id, "request_id": request_id},
        )
        return _emit_routing_snapshot(snapshot, json_output=args.json)

    route_constraints = _build_route_constraints_from_args(args)

    route = preview_route(
        root,
        capability=capability,
        task_id=task_id,
        adapter_id=getattr(args, "adapter", None),
        requested_mode=requested_mode,
        constraints=route_constraints,
        explain=getattr(args, "explain", False),
    )
    snapshot = build_routing_snapshot(
        route,
        task_id=task_id,
        request_id=request_id,
        explain=getattr(args, "explain", False),
    )
    return _emit_routing_snapshot(snapshot, json_output=args.json)


def _render_decision_trace(trace: dict[str, Any]) -> str:
    """Render a decision trace as a compact human-readable block."""
    lines = ["DECISION TRACE"]
    lines.append(f"  capability: {trace['capability']}")
    if trace["matched_candidates"]:
        lines.append("  matched candidates:")
        for c in trace["matched_candidates"]:
            lines.append(
                f"    - {c['adapter_id']} (idx={c['source_index']}, "
                f"risk={c['risk_level']}): {c['reason']}"
            )
    if trace["rejected_candidates"]:
        lines.append("  rejected candidates:")
        for c in trace["rejected_candidates"]:
            lines.append(f"    - {c['adapter_id']}: {', '.join(c['reasons'])}")
    if trace["eligible_candidates"]:
        lines.append("  eligible candidates:")
        for c in trace["eligible_candidates"]:
            lines.append(
                f"    - {c['adapter_id']} (idx={c['source_index']}, "
                f"risk={c['risk_level']}): {c['reason']}"
            )
    selected = trace["selected"]
    lines.append(
        f"  selected: {selected['adapter_id'] or '(none)'} — {selected['reason']}"
    )
    if trace["fallback_candidates"]:
        lines.append("  fallback candidates:")
        for c in trace["fallback_candidates"]:
            lines.append(
                f"    - {c['adapter_id']} (idx={c['source_index']}, "
                f"risk={c['risk_level']})"
            )
    return "\n".join(lines)


def _emit_route_preview_result(result: RoutePreviewResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ROUTE PREVIEW")
        print(
            f"capability={result.requested_capability} "
            f"adapter={result.selected_adapter_id or '-'} "
            f"operation={result.operation or '-'} "
            f"requested_mode={result.requested_mode} "
            f"selected_mode={result.selected_mode} "
            f"risk={result.risk_level or '-'} "
            f"requires_approval={result.requires_approval} "
            f"requires_dry_run={result.requires_dry_run}"
        )
        if result.task_id is not None:
            print(f"task_id={result.task_id}")
        if result.routing_reason:
            print(f"reason: {result.routing_reason}")
        if result.fallback_candidates:
            print("fallback_candidates:")
            for candidate in result.fallback_candidates:
                print(f"- {candidate.get('adapter_id', '-')}: {candidate.get('reason', '')}")
        if result.constraints:
            constraints = result.constraints
            print(
                f"constraints: kind={constraints.get('adapter_kind', '-')} "
                f"preflight_checks={','.join(constraints.get('preflight_checks', []))}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
        if result.decision_trace is not None:
            print(_render_decision_trace(result.decision_trace.to_dict()))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _emit_routing_snapshot(snapshot: RoutingDecisionSnapshot, json_output: bool) -> int:
    """Render a routing decision snapshot in JSON or compact human-readable form."""
    if json_output:
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ROUTING DECISION SNAPSHOT")
        print(f"schema_version={snapshot.schema_version}")
        print(f"snapshot_id={snapshot.snapshot_id}")
        print(f"status={snapshot.status}")
        routing = snapshot.routing
        print(
            f"adapter={routing.get('selected_adapter_id') or '-'} "
            f"capability={routing.get('requested_capability')} "
            f"operation={routing.get('operation') or '-'}"
        )
        print(
            f"mode={routing.get('requested_mode')} "
            f"risk={routing.get('risk_level') or '-'} "
            f"requires_approval={routing.get('requires_approval')} "
            f"requires_dry_run={routing.get('requires_dry_run')}"
        )
        if routing.get("routing_reason"):
            print(f"reason: {routing['routing_reason']}")
        if routing.get("fallback_adapter_ids"):
            print(f"fallback: {', '.join(routing['fallback_adapter_ids'])}")
        if snapshot.guardrail is not None:
            guardrail = snapshot.guardrail
            blocking = ",".join(guardrail.get("blocking_rule_ids", [])) or "-"
            print(
                f"guardrail_status={guardrail.get('status') or '-'} "
                f"finding_count={guardrail.get('finding_count', 0)} "
                f"blocking_rule_ids={blocking}"
            )
        if snapshot.trace is not None:
            print("trace: present")
    return _STATUS_TO_EXIT.get(snapshot.status, EXIT_ERROR)


def _cmd_orchestration_preflight(args: argparse.Namespace) -> int:
    """Render a read-only orchestration preflight handoff check."""
    root = _root_path(args)
    capability = args.capability
    requested_mode = getattr(args, "mode", "dry-run")
    if requested_mode not in {"dry-run", "commit"}:
        result = PreflightResult(
            status="error",
            requested_capability=capability,
            task_id=getattr(args, "task_id", None),
            requested_mode=requested_mode,
            selected_mode="dry-run",
            effective_mode="dry-run",
            findings=[
                Finding(
                    rule_id="invalid-mode",
                    severity="error",
                    action="error",
                    message="--mode must be 'dry-run' or 'commit'.",
                )
            ],
            next_action="Provide --mode dry-run or --mode commit.",
        )
        return _emit_preflight_result(result, json_output=args.json)

    route_constraints: RouteConstraints | None = None
    if (
        getattr(args, "preferred_adapter", None) is not None
        or getattr(args, "max_risk", None) is not None
        or getattr(args, "require_background", False)
        or getattr(args, "require_artifacts", False)
    ):
        route_constraints = RouteConstraints(
            preferred_adapter=getattr(args, "preferred_adapter", None),
            require_background=getattr(args, "require_background", False),
            require_artifacts=getattr(args, "require_artifacts", False),
            max_risk=getattr(args, "max_risk", None),
        )

    result = check_preflight(
        root,
        capability=capability,
        task_id=getattr(args, "task_id", None),
        adapter_id=getattr(args, "adapter", None),
        operation=getattr(args, "operation", None),
        target=getattr(args, "target", None),
        requested_mode=requested_mode,
        explicit_policy=_explicit_policy(args, root),
        profile=resolve_profile(args, root),
        constraints=route_constraints,
        explain=getattr(args, "explain", False),
    )
    if getattr(args, "snapshot", False):
        snapshot = build_preflight_snapshot(
            result,
            task_id=getattr(args, "task_id", None),
            request_id=getattr(args, "request_id", None),
            explain=getattr(args, "explain", False),
        )
        return _emit_routing_snapshot(snapshot, json_output=args.json)
    return _emit_preflight_result(result, json_output=args.json)


def _emit_preflight_result(result: PreflightResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("PREFLIGHT")
        print(
            f"capability={result.requested_capability} "
            f"adapter={result.route.get('selected_adapter_id') or '-'} "
            f"operation={result.route.get('operation') or '-'} "
            f"requested_mode={result.requested_mode} "
            f"selected_mode={result.selected_mode} "
            f"effective_mode={result.effective_mode} "
            f"requires_approval={result.requires_approval} "
            f"requires_dry_run={result.requires_dry_run}"
        )
        guardrail = result.guardrail
        print(
            f"route_status={result.route.get('status') or '-'} "
            f"guardrail_status={guardrail.get('status') or '-'} "
            f"finding_count={guardrail.get('finding_count', 0)}"
        )
        if result.task_id is not None:
            print(f"task_id={result.task_id}")
        if result.findings:
            for finding in result.findings:
                print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
        route_trace = result.route.get("decision_trace")
        if route_trace is not None:
            print(_render_decision_trace(route_trace))
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_task_submit(args: argparse.Namespace) -> int:
    """Submit a task through the orchestration namespace."""
    root = _root_path(args)
    result = submit_task(
        root,
        file=getattr(args, "file", None),
        stdin=getattr(args, "stdin", False),
        dry_run=getattr(args, "dry_run", False),
        commit=getattr(args, "commit", False),
        tasks_file=getattr(args, "tasks_file", None),
        events_file=getattr(args, "events_file", None),
    )
    return _emit_orchestration_task_submit_result(result, json_output=args.json)


def _cmd_orchestration_task_list(args: argparse.Namespace) -> int:
    """Render a read-only list of task snapshots."""
    root = _root_path(args)
    status_filter = getattr(args, "status", None)
    result = list_tasks(root, status_filter=status_filter)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"TASK LIST (count={len(result.tasks)})")
        for task in result.tasks:
            capability = task.get("requested_capability") or "-"
            print(
                f"- {task['task_id']} "
                f"{task['status']} "
                f"{capability} "
                f"assignee={task['assignee']} "
                f"updated_at={task['updated_at']}"
            )
    return EXIT_PASS


def _cmd_orchestration_task_get(args: argparse.Namespace) -> int:
    """Render a read-only task detail view with event timeline."""
    root = _root_path(args)
    result = get_task(root, args.task_id)
    if result.status != "pass":
        return emit(
            CheckResult(
                status=result.status,
                findings=[],
                next_action=result.next_action,
            ),
            json_output=args.json,
            no_color=args.no_color,
        )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        if result.task is not None:
            print("TASK DETAIL")
            print(f"Task: {result.task['task_id']}")
            print(f"Title: {result.task['title']}")
            print(f"Status: {result.task['status']}")
            print(f"Assignee: {result.task['assignee']}")
            if result.task.get("summary"):
                print(f"Summary: {result.task['summary']}")
            if result.task.get("requested_capability"):
                print(f"Capability: {result.task['requested_capability']}")
            if result.task.get("workspace"):
                print(f"Workspace: {result.task['workspace']}")
            if result.task.get("priority"):
                print(f"Priority: {result.task['priority']}")
            if result.task.get("labels"):
                print(f"Labels: {', '.join(str(label) for label in result.task['labels'])}")
            print(f"Created: {result.task['created_at']}")
            print(f"Updated: {result.task['updated_at']}")
        if result.event_timeline:
            print("Events:")
            for event in result.event_timeline:
                transition = ""
                if event.get("from_status") and event.get("to_status"):
                    transition = f" {event['from_status']} -> {event['to_status']}"
                elif event.get("to_status"):
                    transition = f" -> {event['to_status']}"
                message = event.get("message")
                suffix = f" - {message}" if message else ""
                print(
                    f"- {event['timestamp']} {event['event_type']}{transition}{suffix}"
                )
    return EXIT_PASS


def _cmd_orchestration_run_inspect(args: argparse.Namespace) -> int:
    """Render a read-only run inspect view (thin wrapper over runtime report)."""
    root = _root_path(args)
    result = inspect_run(
        root,
        task_id=args.task_id,
        request_id=args.request_id,
        envelope_file=args.envelope,
        tasks_file=getattr(args, "tasks_file", None),
        events_file=getattr(args, "events_file", None),
        aggregate_lineage=getattr(args, "aggregate_lineage", False),
        replay=getattr(args, "replay", False),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("RUN INSPECT")
        print(
            f"task_id={result.task_id} "
            f"request_id={result.request_id} "
            f"status={result.status} "
            f"task_status={result.task_status or '-'}"
        )
        if result.lineage_type:
            lineage_parts = [f"lineage_type={result.lineage_type}"]
            if result.retry_of:
                lineage_parts.append(f"retry_of={result.retry_of}")
            if result.fallback_from:
                lineage_parts.append(f"fallback_from={result.fallback_from}")
            if result.fallback_to:
                lineage_parts.append(f"fallback_to={result.fallback_to}")
            print(" ".join(lineage_parts))
        if result.recovery_lineage is not None:
            recovery = result.recovery_lineage
            print(
                "Recovery lineage: "
                f"status={recovery.status} "
                f"root={recovery.root_request_id or '-'} "
                f"latest={recovery.latest_request_id or '-'} "
                f"attempts={recovery.attempt_count} "
                f"leaves={','.join(recovery.leaf_request_ids) or '-'}"
            )
            for issue in recovery.issues:
                safe_ids = " ".join(
                    f"{key}={value}" for key, value in issue.items() if key != "code"
                )
                suffix = f" {safe_ids}" if safe_ids else ""
                print(f"- recovery_issue={issue['code']}{suffix}")
        if result.envelope_summary is not None:
            artifact_counts = result.envelope_summary.get("artifact_counts", {})
            counts = ", ".join(f"{k}={v}" for k, v in artifact_counts.items())
            print(f"Envelope: {counts or 'no artifacts'}")
        else:
            print("Envelope: validation failed")

        if result.gate is not None:
            print(
                f"Gate: stage={result.gate.get('stage', '-')}, "
                f"can_proceed={result.gate.get('can_proceed', False)}"
            )
        else:
            print("Gate: unavailable")

        if result.ledger is not None:
            counts = result.ledger.get("counts", {})
            counts_str = ", ".join(f"{k}={v}" for k, v in counts.items())
            print(f"Ledger: {result.ledger.get('status', '-')} ({counts_str})")
        else:
            print("Ledger: unavailable")

        if result.blockers:
            print("Blockers:")
            for blocker in result.blockers:
                print(f"- {blocker}")
        else:
            print("Blockers: none")

        if result.replay is not None:
            print(
                "Replay: "
                f"schema={result.replay.schema_version} "
                f"next_action={result.replay.next_action['code']}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_run_list(args: argparse.Namespace) -> int:
    """Render a read-only run list view from an envelope (envelope-scoped read model)."""
    root = _root_path(args)
    result = list_runs(
        root,
        envelope_file=args.envelope,
        task_id_filter=getattr(args, "task_id", None),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("RUN LIST")
        print(f"envelope={args.envelope}")
        if getattr(args, "task_id", None) is not None:
            print(f"task_id_filter={args.task_id}")
        print(f"runs={len(result.runs)}")
        for run in result.runs:
            parts = [
                f"- {run['request_id']}",
                f"task={run['task_id']}",
                f"adapter={run['adapter_id']}",
                f"capability={run['capability'] or '-'}",
                f"operation={run['operation']}",
                f"mode={run['mode']}",
                f"status={run['status']}",
                f"started={run['started_at'] or '-'}",
                f"ended={run['ended_at'] or '-'}",
            ]
            if run.get("lineage_type"):
                lineage_parts = [f"lineage_type={run['lineage_type']}"]
                if run.get("retry_of"):
                    lineage_parts.append(f"retry_of={run['retry_of']}")
                if run.get("fallback_from"):
                    lineage_parts.append(f"fallback_from={run['fallback_from']}")
                if run.get("fallback_to"):
                    lineage_parts.append(f"fallback_to={run['fallback_to']}")
                parts.append(" ".join(lineage_parts))
            print(" ".join(parts))
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _emit_run_dry_run_result(result: RunDryRunResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("RUN")
        print(
            f"task_id={result.task_id} "
            f"request_id={result.request_id} "
            f"capability={result.requested_capability} "
            f"mode={result.mode} "
            f"status={result.status}"
        )
        if result.lineage_type:
            lineage_parts = [f"lineage_type={result.lineage_type}"]
            if result.retry_of:
                lineage_parts.append(f"retry_of={result.retry_of}")
            if result.fallback_from:
                lineage_parts.append(f"fallback_from={result.fallback_from}")
            if result.fallback_to:
                lineage_parts.append(f"fallback_to={result.fallback_to}")
            print(" ".join(lineage_parts))
        route = result.route
        print(
            f"adapter={route.get('selected_adapter_id') or '-'} "
            f"operation={route.get('operation') or '-'} "
            f"risk_level={route.get('risk_level') or '-'} "
            f"requires_approval={route.get('requires_approval', False)}"
        )
        if result.plan_hash:
            print(f"plan_hash={result.plan_hash}")
        if result.routing_snapshot_id:
            print(f"routing_snapshot_id={result.routing_snapshot_id}")
        if result.candidate_envelope_summary:
            summary = result.candidate_envelope_summary
            print(
                f"candidate envelope: version={summary.get('version') or '-'} "
                f"artifacts={summary.get('artifact_count', 0)} "
                f"approval_required={summary.get('requires_approval', False)}"
            )
        if result.findings:
            for finding in result.findings:
                print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _emit_run_commit_result(result: RunCommitResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("RUN COMMIT")
        header = (
            f"task_id={result.task_id} "
            f"request_id={result.request_id} "
            f"capability={result.requested_capability} "
            f"mode={result.mode} "
            f"status={result.status}"
        )
        print(header)
        if result.lineage_type:
            lineage_parts = [f"lineage_type={result.lineage_type}"]
            if result.retry_of:
                lineage_parts.append(f"retry_of={result.retry_of}")
            if result.fallback_from:
                lineage_parts.append(f"fallback_from={result.fallback_from}")
            if result.fallback_to:
                lineage_parts.append(f"fallback_to={result.fallback_to}")
            print(" ".join(lineage_parts))
        print(
            f"plan_hash={result.plan_hash or '-'} "
            f"expected_plan_hash={result.expected_plan_hash or '-'} "
            f"freeze_check={result.freeze_check}"
        )
        write_summary = result.write_summary
        if write_summary:
            print(
                f"write: output={write_summary.get('output') or '-'} "
                f"events_file={write_summary.get('events_file') or '-'} "
                f"committed={write_summary.get('committed', False)} "
                f"rolled_back={write_summary.get('rolled_back', False)} "
                f"post_validate={write_summary.get('post_validate') or '-'} "
                f"post_inspect={write_summary.get('post_inspect') or '-'} "
                f"events={write_summary.get('appended_event_count', 0)}"
            )
        if result.artifact_ref:
            ref = result.artifact_ref
            print(
                f"artifact: type={ref.get('artifact_type')} "
                f"path={ref.get('path')} "
                f"adapter={ref.get('adapter_id') or '-'} "
                f"operation={ref.get('operation') or '-'}"
            )
        if result.event_refs:
            print("events:")
            for ref in result.event_refs:
                print(
                    f"- {ref.get('event_id')} "
                    f"type={ref.get('event_type')} "
                    f"task={ref.get('task_id')} "
                    f"request={ref.get('request_id')}"
                )
        if result.findings:
            for finding in result.findings:
                print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _emit_read_loop_snapshot(
    snapshot: OrchestrationReadLoopSnapshot, json_output: bool
) -> int:
    """Render a read-loop snapshot in JSON or compact human-readable form."""
    if json_output:
        print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("READ LOOP SNAPSHOT")
        print(f"schema_version={snapshot.schema_version}")
        print(f"snapshot_id={snapshot.snapshot_id}")
        print(f"status={snapshot.status}")
        run = snapshot.run
        print(
            f"run: task_id={run.get('task_id')} "
            f"request_id={run.get('request_id')} "
            f"adapter={run.get('adapter_id') or '-'} "
            f"capability={run.get('capability')} "
            f"operation={run.get('operation') or '-'} "
            f"run_status={run.get('status')} "
            f"gate_status={run.get('gate_status')}"
        )
        print(
            f"run: mode={run.get('mode')} "
            f"risk={run.get('risk_level') or '-'} "
            f"requires_approval={run.get('requires_approval')} "
            f"requires_dry_run={run.get('requires_dry_run')}"
        )
        if run.get("plan_hash"):
            print(f"run: plan_hash={run['plan_hash']}")
        if run.get("routing_snapshot_id"):
            print(f"run: routing_snapshot_id={run['routing_snapshot_id']}")
        if run.get("lineage_type"):
            lineage_parts = [f"lineage_type={run['lineage_type']}"]
            if run.get("retry_of"):
                lineage_parts.append(f"retry_of={run['retry_of']}")
            if run.get("fallback_from"):
                lineage_parts.append(f"fallback_from={run['fallback_from']}")
            if run.get("fallback_to"):
                lineage_parts.append(f"fallback_to={run['fallback_to']}")
            print("run: " + " ".join(lineage_parts))
        print(f"events: count={len(snapshot.events)}")
        for event in snapshot.events:
            print(f"- event_type={event.get('event_type')} status={event.get('status')}")
        report = snapshot.report
        print(
            f"report: status={report.get('status')} "
            f"gate_status={report.get('gate_status')} "
            f"candidate_event_count={report.get('candidate_event_count')} "
            f"artifact_candidate_count={report.get('artifact_candidate_count')} "
            f"evidence_candidate_count={report.get('evidence_candidate_count')} "
            f"requires_approval={report.get('requires_approval')}"
        )
        if report.get("status_summary"):
            print(f"report: status_summary={report['status_summary']}")
        if report.get("candidate_event_types"):
            types = ", ".join(f"{k}:{v}" for k, v in report["candidate_event_types"].items())
            print(f"report: candidate_event_types={types}")
        if report.get("artifact_candidate_type_counts"):
            types = ", ".join(f"{k}:{v}" for k, v in report["artifact_candidate_type_counts"].items())
            print(f"report: artifact_candidate_type_counts={types}")
        if report.get("finding_count"):
            print(
                f"report: finding_count={report['finding_count']} "
                f"finding_rule_ids={','.join(report.get('finding_rule_ids', []))}"
            )
        if report.get("next_action"):
            print(f"Next: {report['next_action']}")
    return _STATUS_TO_EXIT.get(snapshot.status, EXIT_ERROR)


def _cmd_orchestration_run(args: argparse.Namespace) -> int:
    """Render a read-only run dry-run preview or commit an envelope draft."""
    root = _root_path(args)
    task_id = getattr(args, "task_id", None)
    request_id = getattr(args, "request_id", None)
    capability = getattr(args, "capability", None)

    missing = []
    if not task_id:
        missing.append("--task-id")
    if not request_id:
        missing.append("--request-id")
    if not capability:
        missing.append("--capability")
    if missing:
        result = RunDryRunResult(
            status="needs_input",
            task_id=task_id or "-",
            request_id=request_id or "-",
            requested_capability=capability or "-",
            findings=[
                Finding(
                    rule_id="missing-required-args",
                    severity="block",
                    action="needs_input",
                    message=f"Missing required arguments: {', '.join(missing)}.",
                )
            ],
            next_action=f"Provide {', '.join(missing)}.",
        )
        return _emit_run_dry_run_result(result, json_output=args.json)

    if getattr(args, "commit", False):
        if getattr(args, "snapshot", False):
            result = RunCommitResult(
                status="blocked",
                task_id=task_id,
                request_id=request_id,
                requested_capability=capability,
                findings=[
                    Finding(
                        rule_id="snapshot-not-supported-in-commit",
                        severity="block",
                        action="blocked",
                        message="--snapshot is only supported for --dry-run preview; remove it for --commit.",
                    )
                ],
                next_action="Re-run with --dry-run --snapshot to preview the read-loop snapshot, or omit --snapshot for commit.",
            )
            return _emit_run_commit_result(result, json_output=args.json)

        if getattr(args, "routing_snapshot_id", None) is not None:
            result = RunCommitResult(
                status="blocked",
                task_id=task_id,
                request_id=request_id,
                requested_capability=capability,
                findings=[
                    Finding(
                        rule_id="routing-snapshot-id-not-supported-in-commit",
                        severity="block",
                        action="blocked",
                        message="--routing-snapshot-id is only supported for --dry-run preview; remove it for --commit.",
                    )
                ],
                next_action="Re-run with --dry-run to preview the routing snapshot reference, or omit --routing-snapshot-id for commit.",
            )
            return _emit_run_commit_result(result, json_output=args.json)

        retry_of = getattr(args, "retry_of", None)
        fallback_from = getattr(args, "fallback_from", None)
        fallback_to = getattr(args, "fallback_to", None)
        effective_adapter_id = fallback_to if fallback_to is not None else getattr(args, "adapter", None)
        result = commit_run(
            root,
            task_id=task_id,
            request_id=request_id,
            capability=capability,
            output=getattr(args, "output", None),
            expected_plan_hash=getattr(args, "expected_plan_hash", None),
            events_file=getattr(args, "events_file", None),
            adapter_id=effective_adapter_id,
            operation=getattr(args, "operation", None),
            target=getattr(args, "target", None),
            require_dry_run=getattr(args, "require_dry_run", False),
            explicit_policy=_explicit_policy(args, root),
            profile=resolve_profile(args, root),
            actor="cli",
            tasks_file=getattr(args, "tasks_file", None),
            args=args,
            retry_of=retry_of,
            fallback_from=fallback_from,
            fallback_to=fallback_to,
        )
        return _emit_run_commit_result(result, json_output=args.json)

    retry_of = getattr(args, "retry_of", None)
    fallback_from = getattr(args, "fallback_from", None)
    fallback_to = getattr(args, "fallback_to", None)
    effective_adapter_id = fallback_to if fallback_to is not None else getattr(args, "adapter", None)

    result = dry_run_run(
        root,
        task_id=task_id,
        request_id=request_id,
        capability=capability,
        adapter_id=effective_adapter_id,
        operation=getattr(args, "operation", None),
        target=getattr(args, "target", None),
        requested_mode="dry-run",
        explicit_policy=_explicit_policy(args, root),
        profile=resolve_profile(args, root),
        actor="cli",
        tasks_file=getattr(args, "tasks_file", None),
        args=args,
        retry_of=retry_of,
        fallback_from=fallback_from,
        fallback_to=fallback_to,
        routing_snapshot_id=getattr(args, "routing_snapshot_id", None),
    )
    if getattr(args, "snapshot", False):
        snapshot = build_read_loop_snapshot(result)
        return _emit_read_loop_snapshot(snapshot, json_output=args.json)
    return _emit_run_dry_run_result(result, json_output=args.json)


def _cmd_orchestration_approval_list(args: argparse.Namespace) -> int:
    """Render a read-only approval list view from an envelope (envelope-scoped read model)."""
    root = _root_path(args)
    result = list_approvals(
        root,
        envelope_file=args.envelope,
        status_filter=getattr(args, "status", None),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("APPROVAL LIST")
        print(f"envelope={args.envelope}")
        if getattr(args, "status", None) is not None:
            print(f"status_filter={args.status}")
        print(f"approvals={len(result.approvals)}")
        for approval in result.approvals:
            print(
                f"- {approval['approval_id']} "
                f"request={approval['request_id']} "
                f"task={approval['task_id']} "
                f"adapter={approval['adapter_id']} "
                f"operation={approval['operation']} "
                f"target={approval['target']} "
                f"status={approval['status']} "
                f"requested={approval['requested_at'] or '-'} "
                f"resolved={approval['resolved_at'] or '-'} "
                f"resolver={approval['resolver'] or '-'}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_approval_get(args: argparse.Namespace) -> int:
    """Render a read-only approval detail view from an envelope (envelope-scoped read model)."""
    root = _root_path(args)
    result = get_approval(
        root,
        approval_id=args.approval_id,
        envelope_file=args.envelope,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("APPROVAL GET")
        if result.approval is not None:
            approval = result.approval
            scope = approval.get("scope", {})
            print(
                f"approval_id={approval.get('approval_id', '-')} "
                f"request_id={approval.get('request_id', '-')} "
                f"status={approval.get('status', '-')}"
            )
            print(
                f"scope: task={scope.get('task_id', '-')} "
                f"adapter={scope.get('adapter_id', '-')} "
                f"operation={scope.get('operation', '-')} "
                f"target={scope.get('target', '-')}"
            )
            print(f"requested_at={approval.get('requested_at') or '-'}")
            print(f"resolved_at={approval.get('resolved_at') or '-'}")
            print(f"resolver={approval.get('resolver') or '-'}")
        if result.related_request is not None:
            req = result.related_request
            print(
                f"Related request: {req.get('request_id', '-')} "
                f"task={req.get('task_id', '-')} "
                f"adapter={req.get('adapter_id', '-')} "
                f"operation={req.get('operation', '-')} "
                f"target={req.get('target', '-')} "
                f"risk={req.get('risk_level', '-')} "
                f"capability={req.get('capability') or '-'} "
                f"dry_run={req.get('dry_run', False)} "
                f"requires_approval={req.get('requires_approval', False)}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_approval_resolve(args: argparse.Namespace) -> int:
    """Record an approval decision by appending a task event (dry-run or commit)."""
    root = _root_path(args)
    dry_run = getattr(args, "dry_run", False)
    commit = getattr(args, "commit", False)
    result = resolve_approval(
        root,
        approval_id=args.approval_id,
        task_id=args.task_id,
        request_id=args.request_id,
        decision=args.decision,
        reason=args.reason,
        envelope_file=args.envelope,
        dry_run=dry_run,
        commit=commit,
        events_file=getattr(args, "events_file", None),
        tasks_file=getattr(args, "tasks_file", None),
        actor="cli",
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("APPROVAL RESOLVE")
        print(
            f"approval_id={result.approval_id} "
            f"task_id={result.task_id} "
            f"request_id={result.request_id} "
            f"decision={result.decision} "
            f"mode={result.mode} "
            f"status={result.status}"
        )
        event = result.event_written or result.event_preview
        if event is not None:
            print(
                f"event: event_id={event.get('event_id', '-')} "
                f"event_type={event.get('event_type', '-')} "
                f"decision={event.get('decision', '-')}"
            )
        if result.write_summary is not None:
            ws = result.write_summary
            print(
                f"write_summary: committed={ws.get('committed', False)} "
                f"rolled_back={ws.get('rolled_back', False)} "
                f"post_validate={ws.get('post_validate') or '-'} "
                f"post_ledger_check={ws.get('post_ledger_check') or '-'}"
            )
        if result.findings:
            for finding in result.findings:
                print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_artifact_list(args: argparse.Namespace) -> int:
    """Render a read-only artifact list view from an envelope (envelope-scoped read model)."""
    root = _root_path(args)
    result = list_artifacts(
        root,
        envelope_file=args.envelope,
        type_filter=getattr(args, "type", None),
        request_id_filter=getattr(args, "request_id", None),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ARTIFACT LIST")
        print(f"envelope={args.envelope}")
        if getattr(args, "type", None) is not None:
            print(f"type_filter={args.type}")
        if getattr(args, "request_id", None) is not None:
            print(f"request_id_filter={args.request_id}")
        print(f"artifacts={len(result.artifacts)}")
        for artifact in result.artifacts:
            print(
                f"- {artifact['artifact_id']} "
                f"type={artifact['artifact_type']} "
                f"task={artifact['task_id'] or '-'} "
                f"request={artifact['request_id'] or '-'} "
                f"producer={artifact['producer']} "
                f"timestamp={artifact['timestamp'] or '-'} "
                f"safe={artifact['safe_to_preview']} "
                f"summary={artifact['summary']}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_artifact_get(args: argparse.Namespace) -> int:
    """Render a read-only artifact detail view from an envelope (envelope-scoped read model)."""
    root = _root_path(args)
    result = get_artifact(
        root,
        artifact_id=args.artifact_id,
        envelope_file=args.envelope,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ARTIFACT GET")
        if result.artifact is not None:
            artifact = result.artifact
            print(
                f"artifact_id={artifact.get('artifact_id', '-')} "
                f"type={artifact.get('artifact_type', '-')} "
                f"task={artifact.get('task_id') or '-'} "
                f"request={artifact.get('request_id') or '-'} "
                f"producer={artifact.get('producer', '-')} "
                f"safe={artifact.get('safe_to_preview', False)}"
            )
            print(f"timestamp={artifact.get('timestamp') or '-'}")
            print(f"summary={artifact.get('summary', '-')}")
            metadata = artifact.get("metadata", {})
            if metadata:
                print("metadata:")
                for key, value in metadata.items():
                    print(f"  {key}={value}")
        if result.related_request is not None:
            req = result.related_request
            print(
                f"Related request: {req.get('request_id', '-')} "
                f"task={req.get('task_id', '-')} "
                f"adapter={req.get('adapter_id', '-')} "
                f"operation={req.get('operation', '-')} "
                f"target={req.get('target', '-')} "
                f"risk={req.get('risk_level', '-')} "
                f"capability={req.get('capability') or '-'} "
                f"dry_run={req.get('dry_run', False)} "
                f"requires_approval={req.get('requires_approval', False)}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_adapter_list(args: argparse.Namespace) -> int:
    """Render a read-only adapter capability registry list."""
    root = _root_path(args)
    result = list_adapters(
        root,
        type_filter=getattr(args, "type", None),
        risk_filter=getattr(args, "risk", None),
        capability_filter=getattr(args, "capability", None),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ADAPTER LIST")
        if getattr(args, "type", None) is not None:
            print(f"type_filter={args.type}")
        if getattr(args, "risk", None) is not None:
            print(f"risk_filter={args.risk}")
        if getattr(args, "capability", None) is not None:
            print(f"capability_filter={args.capability}")
        print(f"adapters={len(result.adapters)}")
        for adapter in result.adapters:
            print(
                f"- {adapter['adapter_id']:<16} "
                f"type={adapter['adapter_type']:<8} "
                f"risk={adapter['risk_level']:<12} "
                f"enabled={adapter['enabled']:<5} "
                f"caps={adapter['capability_count']} "
                f"session={adapter['supports_session']} "
                f"background={adapter['supports_background']} "
                f"approval={adapter['supports_approval_roundtrip']} "
                f"artifacts={adapter['supports_artifacts']} "
                f"cancel={adapter['supports_cancel']}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_adapter_inspect(args: argparse.Namespace) -> int:
    """Render a read-only adapter capability registry inspect view."""
    root = _root_path(args)
    result = get_adapter(root, adapter_id=args.adapter_id)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("ADAPTER INSPECT")
        if result.adapter is not None:
            adapter = result.adapter
            print(f"adapter_id={adapter['adapter_id']}")
            print(f"display_name={adapter['display_name']}")
            print(f"adapter_type={adapter['adapter_type']}")
            print(f"risk_level={adapter['risk_level']}")
            print(f"capabilities={', '.join(adapter['capabilities'])}")
            print(
                f"supports: "
                f"session={adapter['supports_session']} "
                f"background={adapter['supports_background']} "
                f"approval_roundtrip={adapter['supports_approval_roundtrip']} "
                f"artifacts={adapter['supports_artifacts']} "
                f"cancel={adapter['supports_cancel']}"
            )
            timeout = adapter.get("timeout_profile", {})
            print(
                f"timeout_profile: default={timeout.get('default_seconds', '-')}s "
                f"max={timeout.get('max_seconds', '-')}s"
            )
            print(f"input_schema_ref={adapter['input_schema_ref']}")
            print(f"output_schema_ref={adapter['output_schema_ref']}")
            derived = adapter.get("derived", {})
            if derived:
                print("derived:")
                for key, note in derived.items():
                    print(f"  {key}: {note}")
        for finding in result.findings:
            print(f"- {finding.rule_id}: {finding.message}")
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_orchestration_report_generate(args: argparse.Namespace) -> int:
    """Render a read-only report for a task + request pair (runtime-report-backed read model)."""
    root = _root_path(args)
    result = generate_report(
        root,
        task_id=args.task_id,
        request_id=args.request_id,
        envelope_file=args.envelope,
        tasks_file=getattr(args, "tasks_file", None),
        events_file=getattr(args, "events_file", None),
        aggregate_lineage=getattr(args, "aggregate_lineage", False),
        replay=getattr(args, "replay", False),
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("REPORT GENERATE")
        print(
            f"task_id={result.task_id} "
            f"request_id={result.request_id} "
            f"task_status={result.task_status or '-'} "
            f"report_status={result.status}"
        )
        if result.lineage_type:
            lineage_parts = [f"lineage_type={result.lineage_type}"]
            if result.retry_of:
                lineage_parts.append(f"retry_of={result.retry_of}")
            if result.fallback_from:
                lineage_parts.append(f"fallback_from={result.fallback_from}")
            if result.fallback_to:
                lineage_parts.append(f"fallback_to={result.fallback_to}")
            print(" ".join(lineage_parts))
        print(f"status_summary={result.status_summary}")
        if result.recovery_lineage is not None:
            recovery = result.recovery_lineage
            latest = recovery.latest_request_id or "-"
            leaves = ",".join(recovery.leaf_request_ids) or "-"
            print(
                "Recovery lineage: "
                f"status={recovery.status} "
                f"root={recovery.root_request_id or '-'} "
                f"latest={latest} "
                f"attempts={recovery.attempt_count} "
                f"leaves={leaves}"
            )
        if result.key_findings:
            print("Key findings:")
            for finding in result.key_findings:
                print(f"- {finding}")
        else:
            print("Key findings: none")
        if result.event_summary:
            total = result.event_summary.get("total", 0)
            type_counts = result.event_summary.get("type_counts", {})
            counts = ", ".join(f"{k}:{v}" for k, v in type_counts.items())
            print(f"Events: total={total} type_counts={counts}")
        if result.gate is not None:
            print(
                f"Gate: stage={result.gate.get('stage', '-')} "
                f"can_proceed={result.gate.get('can_proceed', False)}"
            )
        if result.ledger is not None:
            print(f"Ledger: status={result.ledger.get('status', '-')}")
        if result.replay is not None:
            print(
                "Replay: "
                f"schema={result.replay.schema_version} "
                f"next_action={result.replay.next_action['code']}"
            )
        if result.next_action:
            print(f"Next: {result.next_action}")
    return _STATUS_TO_EXIT.get(result.status, EXIT_ERROR)


def _cmd_task_status(args: argparse.Namespace) -> int:
    root = _root_path(args)
    task = find_task(root, args.task_id)
    if task is None:
        result = CheckResult(
            status="needs_input",
            findings=[],
            next_action=f"Task not found: {args.task_id}",
        )
        return emit(result, json_output=args.json, no_color=args.no_color)

    if args.json:
        print(json.dumps({"task": task}, ensure_ascii=False, indent=2))
        return EXIT_PASS

    print(render_task_status(task))
    return EXIT_PASS


def _cmd_task_events(args: argparse.Namespace) -> int:
    root = _root_path(args)
    events = find_task_events(root, args.task_id)
    if not events:
        result = CheckResult(
            status="needs_input",
            findings=[],
            next_action=f"No events found for task: {args.task_id}",
        )
        return emit(result, json_output=args.json, no_color=args.no_color)

    if args.json:
        print(json.dumps({"events": events}, ensure_ascii=False, indent=2))
        return EXIT_PASS

    print(render_task_events(events))
    return EXIT_PASS


def _cmd_task_validate(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = validate_records(
        root,
        record_file=args.record_file,
        schema_type=args.schema,
    )
    return emit(result, json_output=args.json, no_color=args.no_color)


def _cmd_task_check_ledger(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = check_ledger_consistency(
        root,
        tasks_file=args.tasks_file,
        events_file=args.events_file,
    )
    return emit(result, json_output=args.json, no_color=args.no_color)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-runtime",
        description="Minimal read-only agent-runtime CLI POC.",
    )
    _add_global_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Validate project structure and samples")
    _add_global_args(doctor_parser)
    doctor_parser.set_defaults(func=_cmd_doctor)

    # docs context recovery
    docs_parser = subparsers.add_parser(
        "docs", help="Documentation context recovery helpers"
    )
    docs_subparsers = docs_parser.add_subparsers(dest="docs_command", required=True)

    docs_context_parser = docs_subparsers.add_parser(
        "context", help="Show compact project context recovery summary"
    )
    _add_global_args(docs_context_parser)
    docs_context_parser.set_defaults(func=_cmd_docs_context)

    # check
    check_parser = subparsers.add_parser("check", help="Run read-only checks")
    check_subparsers = check_parser.add_subparsers(dest="check_command", required=True)

    text_parser = check_subparsers.add_parser("text", help="Scan text for secrets")
    text_parser.add_argument("--text", default=None, help="Text to scan")
    text_parser.add_argument("--file", default=None, help="File to scan")
    text_parser.add_argument("--stdin", action="store_true", help="Read text from stdin")
    _add_global_args(text_parser)
    text_parser.set_defaults(func=_cmd_check_text)

    path_parser = check_subparsers.add_parser("path", help="Check a path against policy")
    path_parser.add_argument("path", help="Target path")
    path_parser.add_argument("--read", action="store_true", help="Check as read operation")
    path_parser.add_argument("--write", action="store_true", help="Check as write operation")
    path_parser.add_argument("--delete", action="store_true", help="Check as delete operation")
    _add_global_args(path_parser)
    path_parser.set_defaults(func=_cmd_check_path)

    action_parser = check_subparsers.add_parser("action", help="Check an action descriptor")
    action_parser.add_argument("--adapter", required=True, help="Adapter id")
    action_parser.add_argument("--operation", required=True, help="Operation name")
    action_parser.add_argument("--target", default=None, help="Operation target")
    _add_global_args(action_parser)
    action_parser.set_defaults(func=_cmd_check_action)

    # adapter plan
    adapter_parser = subparsers.add_parser("adapter", help="Plan adapter execution envelopes")
    adapter_subparsers = adapter_parser.add_subparsers(dest="adapter_command", required=True)

    adapter_plan_parser = adapter_subparsers.add_parser("plan", help="Generate an adapter execution envelope draft")
    adapter_plan_parser.add_argument("--adapter", required=True, help="Adapter id")
    adapter_plan_parser.add_argument("--operation", required=True, help="Operation name")
    adapter_plan_parser.add_argument("--target", default=None, help="Operation target")
    adapter_plan_parser.add_argument("--actor", default="cli", help="Actor identifier")
    adapter_plan_parser.add_argument("--task-id", default=None, help="Explicit task id")
    _add_global_args(adapter_plan_parser)
    adapter_plan_parser.set_defaults(func=_cmd_adapter_plan)

    adapter_validate_parser = adapter_subparsers.add_parser("validate", help="Validate an adapter execution envelope JSON file")
    adapter_validate_parser.add_argument("--file", required=True, help="Path to envelope JSON file")
    _add_global_args(adapter_validate_parser)
    adapter_validate_parser.set_defaults(func=_cmd_adapter_validate)

    adapter_inspect_parser = adapter_subparsers.add_parser("inspect", help="Inspect an adapter execution envelope JSON file and print a summary")
    adapter_inspect_parser.add_argument("--file", required=True, help="Path to envelope JSON file")
    _add_global_args(adapter_inspect_parser)
    adapter_inspect_parser.set_defaults(func=_cmd_adapter_inspect)

    adapter_approval_parser = adapter_subparsers.add_parser("approval", help="Check approval status for an adapter request")
    adapter_approval_subparsers = adapter_approval_parser.add_subparsers(dest="approval_command", required=True)

    adapter_approval_check_parser = adapter_approval_subparsers.add_parser(
        "check", help="Check whether a request has an approval record that allows it to proceed"
    )
    adapter_approval_check_parser.add_argument("--file", required=True, help="Path to envelope JSON file")
    adapter_approval_check_parser.add_argument("--request-id", required=True, help="Adapter request id")
    _add_global_args(adapter_approval_check_parser)
    adapter_approval_check_parser.set_defaults(func=_cmd_adapter_approval_check)

    adapter_response_parser = adapter_subparsers.add_parser("response", help="Check adapter response and evidence status")
    adapter_response_subparsers = adapter_response_parser.add_subparsers(dest="response_command", required=True)

    adapter_response_check_parser = adapter_response_subparsers.add_parser(
        "check", help="Check whether a request has a response and whether evidence is present"
    )
    adapter_response_check_parser.add_argument("--file", required=True, help="Path to envelope JSON file")
    adapter_response_check_parser.add_argument("--request-id", required=True, help="Adapter request id")
    _add_global_args(adapter_response_check_parser)
    adapter_response_check_parser.set_defaults(func=_cmd_adapter_response_check)

    adapter_gate_parser = adapter_subparsers.add_parser("gate", help="Aggregate approval + response check for an adapter request")
    adapter_gate_subparsers = adapter_gate_parser.add_subparsers(dest="gate_command", required=True)

    adapter_gate_check_parser = adapter_gate_subparsers.add_parser(
        "check", help="Check whether an adapter request may proceed"
    )
    adapter_gate_check_parser.add_argument("--file", required=True, help="Path to envelope JSON file")
    adapter_gate_check_parser.add_argument("--request-id", required=True, help="Adapter request id")
    _add_global_args(adapter_gate_check_parser)
    adapter_gate_check_parser.set_defaults(func=_cmd_adapter_gate_check)

    # runtime gate check
    runtime_parser = subparsers.add_parser("runtime", help="Read-only runtime gate checks over task ledger and adapter envelopes")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command", required=True)

    runtime_plan_parser = runtime_subparsers.add_parser(
        "plan", help="Plan an adapter action for a task without executing it"
    )
    runtime_plan_parser.add_argument("--task-id", required=True, help="Task id")
    runtime_plan_parser.add_argument("--adapter", required=True, help="Adapter id")
    runtime_plan_parser.add_argument("--operation", required=True, help="Operation name")
    runtime_plan_parser.add_argument("--target", default=None, help="Operation target")
    runtime_plan_parser.add_argument("--actor", default="cli", help="Actor identifier")
    runtime_plan_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_plan_parser.add_argument("--draft-json", action="store_true", default=argparse.SUPPRESS, help="Output full schema-valid envelope draft (JSON)")
    _add_global_args(runtime_plan_parser)
    runtime_plan_parser.set_defaults(func=_cmd_runtime_plan)

    runtime_gate_parser = runtime_subparsers.add_parser(
        "gate", help="Runtime gate checks for task + adapter request pairs"
    )
    runtime_gate_subparsers = runtime_gate_parser.add_subparsers(dest="gate_command", required=True)

    runtime_gate_check_parser = runtime_gate_subparsers.add_parser(
        "check", help="Check whether a task + adapter request pair may proceed"
    )
    runtime_gate_check_parser.add_argument("--task-id", required=True, help="Task id")
    runtime_gate_check_parser.add_argument("--request-id", required=True, help="Adapter request id")
    runtime_gate_check_parser.add_argument("--envelope", required=True, help="Path to adapter execution envelope JSON file")
    runtime_gate_check_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_gate_check_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)")
    _add_global_args(runtime_gate_check_parser)
    runtime_gate_check_parser.set_defaults(func=_cmd_runtime_gate_check)

    runtime_check_ledger_parser = runtime_subparsers.add_parser(
        "check-ledger", help="Check cross-system consistency between task/event ledgers and an adapter envelope"
    )
    runtime_check_ledger_parser.add_argument("--tasks-file", required=True, help="Path to tasks JSONL file")
    runtime_check_ledger_parser.add_argument("--events-file", required=True, help="Path to events JSONL file")
    runtime_check_ledger_parser.add_argument("--envelope", required=True, help="Path to adapter execution envelope JSON file")
    _add_global_args(runtime_check_ledger_parser)
    runtime_check_ledger_parser.set_defaults(func=_cmd_runtime_check_ledger)

    runtime_report_parser = runtime_subparsers.add_parser(
        "report", help="Generate an aggregated runtime report for a task + request pair"
    )
    runtime_report_parser.add_argument("--task-id", required=True, help="Task id")
    runtime_report_parser.add_argument("--request-id", required=True, help="Adapter request id")
    runtime_report_parser.add_argument("--envelope", required=True, help="Path to adapter execution envelope JSON file")
    runtime_report_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_report_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)")
    _add_global_args(runtime_report_parser)
    runtime_report_parser.set_defaults(func=_cmd_runtime_report)

    runtime_draft_parser = runtime_subparsers.add_parser(
        "draft", help="Validate and inspect runtime plan envelope drafts"
    )
    runtime_draft_subparsers = runtime_draft_parser.add_subparsers(dest="draft_command", required=True)

    runtime_draft_validate_parser = runtime_draft_subparsers.add_parser(
        "validate", help="Validate a runtime plan envelope draft JSON file or stdin"
    )
    source_group = runtime_draft_validate_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", default=None, help="Path to runtime draft JSON file")
    source_group.add_argument("--stdin", action="store_true", help="Read runtime draft JSON from stdin")
    _add_global_args(runtime_draft_validate_parser)
    runtime_draft_validate_parser.set_defaults(func=_cmd_runtime_draft_validate)

    runtime_draft_inspect_parser = runtime_draft_subparsers.add_parser(
        "inspect", help="Inspect a runtime plan envelope draft JSON file or stdin"
    )
    inspect_group = runtime_draft_inspect_parser.add_mutually_exclusive_group(required=True)
    inspect_group.add_argument("--file", default=None, help="Path to runtime draft JSON file")
    inspect_group.add_argument("--stdin", action="store_true", help="Read runtime draft JSON from stdin")
    _add_global_args(runtime_draft_inspect_parser)
    runtime_draft_inspect_parser.set_defaults(func=_cmd_runtime_draft_inspect)

    runtime_draft_export_parser = runtime_draft_subparsers.add_parser(
        "export", help="Export a runtime plan envelope draft to a project-local .json file"
    )
    export_source_group = runtime_draft_export_parser.add_mutually_exclusive_group(required=True)
    export_source_group.add_argument("--file", default=None, help="Path to runtime draft JSON file")
    export_source_group.add_argument("--stdin", action="store_true", help="Read runtime draft JSON from stdin")
    runtime_draft_export_parser.add_argument("--output", required=True, help="Project-local .json output path")
    runtime_draft_export_parser.add_argument(
        "--dry-run", action="store_true",
        help="Run in read-only dry-run mode (provide either --dry-run or --commit)"
    )
    runtime_draft_export_parser.add_argument(
        "--commit", action="store_true",
        help="Persist the draft to the output path (provide either --dry-run or --commit)"
    )
    _add_global_args(runtime_draft_export_parser)
    runtime_draft_export_parser.set_defaults(func=_cmd_runtime_draft_export)

    # runtime event append
    runtime_event_parser = runtime_subparsers.add_parser(
        "event", help="Task event ledger operations"
    )
    event_subparsers = runtime_event_parser.add_subparsers(dest="event_command", required=True)

    runtime_event_append_parser = event_subparsers.add_parser(
        "append", help="Dry-run or commit append a candidate event to the event ledger"
    )
    append_source_group = runtime_event_append_parser.add_mutually_exclusive_group(required=True)
    append_source_group.add_argument("--file", default=None, help="Path to candidate event JSON file")
    append_source_group.add_argument("--stdin", action="store_true", help="Read candidate event JSON from stdin")
    runtime_event_append_parser.add_argument("--dry-run", action="store_true", help="Run in read-only dry-run mode")
    runtime_event_append_parser.add_argument("--commit", action="store_true", help="Persist the event to the ledger")
    runtime_event_append_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_event_append_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)")
    runtime_event_append_parser.add_argument("--envelope", default=None, help="Path to adapter execution envelope JSON file for runtime audit")
    _add_global_args(runtime_event_append_parser)
    runtime_event_append_parser.set_defaults(func=_cmd_runtime_event_append)

    runtime_event_import_parser = event_subparsers.add_parser(
        "import", help="Dry-run or commit batch import candidate events from a JSONL file"
    )
    runtime_event_import_parser.add_argument("--file", required=True, help="Path to candidate events JSONL file")
    runtime_event_import_parser.add_argument("--dry-run", action="store_true", help="Run in read-only dry-run mode")
    runtime_event_import_parser.add_argument("--commit", action="store_true", help="Persist the batch to the event ledger")
    runtime_event_import_parser.add_argument("--expected-plan-hash", default=None, help="Expected plan hash from a previous dry-run (commit only)")
    runtime_event_import_parser.add_argument(
        "--require-dry-run", action="store_true",
        help="Require the commit to bind a previous dry-run plan (commit only)"
    )
    runtime_event_import_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_event_import_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)")
    _add_global_args(runtime_event_import_parser)
    runtime_event_import_parser.set_defaults(func=_cmd_runtime_event_import)

    # runtime task create (dry-run only)
    runtime_task_parser = runtime_subparsers.add_parser(
        "task", help="Task snapshot ledger operations"
    )
    runtime_task_subparsers = runtime_task_parser.add_subparsers(dest="task_command", required=True)

    runtime_task_create_parser = runtime_task_subparsers.add_parser(
        "create", help="Dry-run or commit create a task snapshot"
    )
    create_source_group = runtime_task_create_parser.add_mutually_exclusive_group(required=True)
    create_source_group.add_argument("--file", default=None, help="Path to candidate task JSON file")
    create_source_group.add_argument("--stdin", action="store_true", help="Read candidate task JSON from stdin")
    runtime_task_create_parser.add_argument("--dry-run", action="store_true", help="Run in read-only dry-run mode")
    runtime_task_create_parser.add_argument("--commit", action="store_true", help="Persist the task to the ledger")
    runtime_task_create_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    runtime_task_create_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)")
    _add_global_args(runtime_task_create_parser)
    runtime_task_create_parser.set_defaults(func=_cmd_runtime_task_create)

    # orchestration overview
    orchestration_parser = subparsers.add_parser(
        "orchestration", help="Orchestration control-plane operations and read models"
    )
    orchestration_subparsers = orchestration_parser.add_subparsers(
        dest="orchestration_command", required=True
    )

    orchestration_overview_parser = orchestration_subparsers.add_parser(
        "overview", help="Show a read-only overview of tasks and events"
    )
    _add_global_args(orchestration_overview_parser)
    orchestration_overview_parser.set_defaults(func=_cmd_orchestration_overview)

    # orchestration contract inspect
    orchestration_contract_parser = orchestration_subparsers.add_parser(
        "contract", help="Discover the versioned orchestration CLI contract"
    )
    orchestration_contract_subparsers = orchestration_contract_parser.add_subparsers(
        dest="contract_command", required=True
    )
    orchestration_contract_inspect_parser = orchestration_contract_subparsers.add_parser(
        "inspect", help="Render the stable/preview/unavailable capability manifest"
    )
    _add_global_args(orchestration_contract_inspect_parser)
    orchestration_contract_inspect_parser.set_defaults(
        func=_cmd_orchestration_contract_inspect
    )

    orchestration_contract_check_parser = orchestration_contract_subparsers.add_parser(
        "check", help="Check required capabilities against the contract manifest"
    )
    orchestration_contract_check_parser.add_argument(
        "--require",
        dest="required_contracts",
        action="append",
        required=True,
        help="Required contract id; repeat for multiple requirements",
    )
    orchestration_contract_check_parser.add_argument(
        "--allow-preview",
        action="store_true",
        help="Explicitly allow preview contract capabilities",
    )
    orchestration_contract_check_parser.add_argument(
        "--max-access",
        choices=["read_only", "controlled_write"],
        default="controlled_write",
        help="Maximum access level allowed by this requirement check",
    )
    _add_global_args(orchestration_contract_check_parser)
    orchestration_contract_check_parser.set_defaults(
        func=_cmd_orchestration_contract_check
    )

    # orchestration profile list/inspect/check
    orchestration_profile_parser = orchestration_subparsers.add_parser(
        "profile", help="Read and check project Automation Profiles"
    )
    orchestration_profile_subparsers = orchestration_profile_parser.add_subparsers(
        dest="profile_command", required=True
    )
    orchestration_profile_list_parser = orchestration_profile_subparsers.add_parser(
        "list", help="List source-backed Automation Profiles"
    )
    _add_global_args(orchestration_profile_list_parser)
    orchestration_profile_list_parser.set_defaults(
        func=_cmd_orchestration_profile_list
    )

    orchestration_profile_inspect_parser = orchestration_profile_subparsers.add_parser(
        "inspect", help="Inspect one source-backed Automation Profile"
    )
    orchestration_profile_inspect_parser.add_argument(
        "--profile-id", required=True, help="Automation Profile id"
    )
    _add_global_args(orchestration_profile_inspect_parser)
    orchestration_profile_inspect_parser.set_defaults(
        func=_cmd_orchestration_profile_inspect
    )

    orchestration_profile_check_parser = orchestration_profile_subparsers.add_parser(
        "check", help="Evaluate one Automation Profile through the Requirement Gate"
    )
    orchestration_profile_check_parser.add_argument(
        "--profile-id", required=True, help="Automation Profile id"
    )
    _add_global_args(orchestration_profile_check_parser)
    orchestration_profile_check_parser.set_defaults(
        func=_cmd_orchestration_profile_check
    )

    # orchestration route preview
    orchestration_route_preview_parser = orchestration_subparsers.add_parser(
        "route", help="Capability routing preview through orchestration namespace"
    )
    orchestration_route_subparsers = orchestration_route_preview_parser.add_subparsers(
        dest="route_command", required=True
    )

    orchestration_route_preview_parser = orchestration_route_subparsers.add_parser(
        "preview", help="Preview capability routing without executing adapters (read-only)"
    )
    orchestration_route_preview_parser.add_argument(
        "--capability", required=True, help="Requested capability"
    )
    orchestration_route_preview_parser.add_argument(
        "--task-id", default=None, help="Optional task id for context"
    )
    orchestration_route_preview_parser.add_argument(
        "--adapter", default=None, help="Explicit adapter id to validate against capability"
    )
    orchestration_route_preview_parser.add_argument(
        "--mode", default="dry-run", choices=["dry-run", "commit"], help="Requested execution mode"
    )
    orchestration_route_preview_parser.add_argument(
        "--preferred-adapter", default=None, help="Preferred adapter id (must still pass constraints)"
    )
    orchestration_route_preview_parser.add_argument(
        "--require-background", action="store_true", help="Require adapter to support background execution"
    )
    orchestration_route_preview_parser.add_argument(
        "--require-artifacts", action="store_true", help="Require adapter to support artifacts"
    )
    orchestration_route_preview_parser.add_argument(
        "--max-risk", default=None, choices=["local", "external", "destructive", "privileged"],
        help="Maximum acceptable risk level (inclusive)"
    )
    orchestration_route_preview_parser.add_argument(
        "--explain", action="store_true", help="Include a structured decision trace in the output"
    )
    _add_global_args(orchestration_route_preview_parser)
    orchestration_route_preview_parser.set_defaults(func=_cmd_orchestration_route_preview)

    # orchestration route snapshot
    orchestration_route_snapshot_parser = orchestration_route_subparsers.add_parser(
        "snapshot", help="Render a deterministic routing decision snapshot (read-only)"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--capability", required=True, help="Requested capability"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--task-id", default=None, help="Optional task id for context"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--request-id", default=None, help="Optional request id for source identity"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--adapter", default=None, help="Explicit adapter id to validate against capability"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--mode", default="dry-run", choices=["dry-run", "commit"], help="Requested execution mode"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--preferred-adapter", default=None, help="Preferred adapter id (must still pass constraints)"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--require-background", action="store_true", help="Require adapter to support background execution"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--require-artifacts", action="store_true", help="Require adapter to support artifacts"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--max-risk", default=None, choices=["local", "external", "destructive", "privileged"],
        help="Maximum acceptable risk level (inclusive)"
    )
    orchestration_route_snapshot_parser.add_argument(
        "--explain", action="store_true", help="Include a structured decision trace in the snapshot"
    )
    _add_global_args(orchestration_route_snapshot_parser)
    orchestration_route_snapshot_parser.set_defaults(func=_cmd_orchestration_route_snapshot)

    # orchestration preflight
    orchestration_preflight_parser = orchestration_subparsers.add_parser(
        "preflight", help="Run read-only orchestration preflight (routing + guardrail)"
    )
    orchestration_preflight_parser.add_argument(
        "--capability", required=True, help="Requested capability"
    )
    orchestration_preflight_parser.add_argument(
        "--task-id", default=None, help="Optional task id for context"
    )
    orchestration_preflight_parser.add_argument(
        "--request-id", default=None, help="Optional request id for source identity"
    )
    orchestration_preflight_parser.add_argument(
        "--adapter", default=None, help="Explicit adapter id to validate against capability"
    )
    orchestration_preflight_parser.add_argument(
        "--operation", default=None, help="Operation to check; uses route-derived operation if omitted"
    )
    orchestration_preflight_parser.add_argument(
        "--target", default=None, help="Target for guardrail check"
    )
    orchestration_preflight_parser.add_argument(
        "--mode", default="dry-run", choices=["dry-run", "commit"], help="Requested execution mode"
    )
    orchestration_preflight_parser.add_argument(
        "--preferred-adapter", default=None, help="Preferred adapter id (must still pass constraints)"
    )
    orchestration_preflight_parser.add_argument(
        "--require-background", action="store_true", help="Require adapter to support background execution"
    )
    orchestration_preflight_parser.add_argument(
        "--require-artifacts", action="store_true", help="Require adapter to support artifacts"
    )
    orchestration_preflight_parser.add_argument(
        "--max-risk", default=None, choices=["local", "external", "destructive", "privileged"],
        help="Maximum acceptable risk level (inclusive)"
    )
    orchestration_preflight_parser.add_argument(
        "--explain", action="store_true", help="Include a structured decision trace in the route summary"
    )
    orchestration_preflight_parser.add_argument(
        "--snapshot", action="store_true", help="Render a deterministic preflight decision snapshot instead of the default summary"
    )
    _add_global_args(orchestration_preflight_parser)
    orchestration_preflight_parser.set_defaults(func=_cmd_orchestration_preflight)

    # orchestration task submit/list/get
    orchestration_task_parser = orchestration_subparsers.add_parser(
        "task", help="Submit or query task ledger data through orchestration namespace"
    )
    orchestration_task_subparsers = orchestration_task_parser.add_subparsers(
        dest="task_command", required=True
    )

    orchestration_task_submit_parser = orchestration_task_subparsers.add_parser(
        "submit", help="Submit a task through the orchestration namespace"
    )
    orchestration_task_submit_source = orchestration_task_submit_parser.add_mutually_exclusive_group(required=True)
    orchestration_task_submit_source.add_argument("--file", default=None, help="Path to candidate task JSON file")
    orchestration_task_submit_source.add_argument("--stdin", action="store_true", help="Read candidate task JSON from stdin")
    orchestration_task_submit_parser.add_argument("--dry-run", action="store_true", help="Simulate task submit without writing (previews A+B)")
    orchestration_task_submit_parser.add_argument("--commit", action="store_true", help="Append one task record and one created event atomically")
    orchestration_task_submit_parser.add_argument("--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)")
    orchestration_task_submit_parser.add_argument("--events-file", default=None, help="Path to events JSONL file (required for --commit; default: tasks/events.jsonl)")
    _add_global_args(orchestration_task_submit_parser)
    orchestration_task_submit_parser.set_defaults(func=_cmd_orchestration_task_submit)

    orchestration_task_list_parser = orchestration_task_subparsers.add_parser(
        "list", help="List task snapshots"
    )
    orchestration_task_list_parser.add_argument(
        "--status", default=None, help="Filter tasks by status"
    )
    _add_global_args(orchestration_task_list_parser)
    orchestration_task_list_parser.set_defaults(func=_cmd_orchestration_task_list)

    orchestration_task_get_parser = orchestration_task_subparsers.add_parser(
        "get", help="Show a task snapshot with event timeline"
    )
    orchestration_task_get_parser.add_argument(
        "--task-id", required=True, help="Task id"
    )
    _add_global_args(orchestration_task_get_parser)
    orchestration_task_get_parser.set_defaults(func=_cmd_orchestration_task_get)

    # orchestration run (dry-run plan + inspect subcommands)
    orchestration_run_parser = orchestration_subparsers.add_parser(
        "run", help="Plan or inspect orchestration runs without executing adapters"
    )
    orchestration_run_parser.add_argument(
        "--task-id", default=None, help="Task id for run plan"
    )
    orchestration_run_parser.add_argument(
        "--request-id", default=None, help="Adapter request id for run plan"
    )
    orchestration_run_parser.add_argument(
        "--capability", default=None, help="Requested capability for run plan"
    )
    orchestration_run_parser.add_argument(
        "--adapter", default=None, help="Explicit adapter id"
    )
    orchestration_run_parser.add_argument(
        "--operation", default=None, help="Operation to plan"
    )
    orchestration_run_parser.add_argument(
        "--target", default=None, help="Target for guardrail check"
    )
    orchestration_run_parser.add_argument(
        "--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)"
    )
    orchestration_run_parser.add_argument(
        "--retry-of", default=None, help="Source request id for a retry dry-run preview"
    )
    orchestration_run_parser.add_argument(
        "--fallback-from", default=None, help="Source request id for a fallback dry-run preview"
    )
    orchestration_run_parser.add_argument(
        "--fallback-to", default=None, help="Fallback adapter id (requires --fallback-from)"
    )
    run_mode_group = orchestration_run_parser.add_mutually_exclusive_group()
    run_mode_group.add_argument(
        "--dry-run", action="store_true", help="Run in read-only dry-run mode (default)"
    )
    run_mode_group.add_argument(
        "--commit", action="store_true", help="Persist the run plan as an envelope draft (A-only)"
    )
    orchestration_run_parser.add_argument(
        "--output", default=None, help="Output envelope draft path (required for --commit)"
    )
    orchestration_run_parser.add_argument(
        "--expected-plan-hash", default=None, help="Expected plan hash from a prior dry-run (required for --commit)"
    )
    orchestration_run_parser.add_argument(
        "--events-file", default=None, help="Event ledger JSONL path for run lifecycle events (required for --commit)"
    )
    orchestration_run_parser.add_argument(
        "--require-dry-run", action="store_true", help="Require a dry-run review context (must provide expected plan hash)"
    )
    orchestration_run_parser.add_argument(
        "--routing-snapshot-id", default=None, help="Content-addressed routing snapshot id (sha256:<64 hex>)"
    )
    orchestration_run_parser.add_argument(
        "--snapshot", action="store_true", help="Render a deterministic read-loop snapshot instead of the default run dry-run summary"
    )
    _add_global_args(orchestration_run_parser)
    orchestration_run_parser.set_defaults(func=_cmd_orchestration_run)

    orchestration_run_subparsers = orchestration_run_parser.add_subparsers(
        dest="run_command", required=False
    )

    orchestration_run_list_parser = orchestration_run_subparsers.add_parser(
        "list", help="List runs from an adapter execution envelope (read-only, envelope-scoped)"
    )
    orchestration_run_list_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_run_list_parser.add_argument(
        "--task-id", default=None, help="Filter runs by task id"
    )
    _add_global_args(orchestration_run_list_parser)
    orchestration_run_list_parser.set_defaults(func=_cmd_orchestration_run_list)

    orchestration_run_inspect_parser = orchestration_run_subparsers.add_parser(
        "inspect", help="Inspect a run via task_id + request_id + envelope (read-only)"
    )
    orchestration_run_inspect_parser.add_argument(
        "--task-id", required=True, help="Task id"
    )
    orchestration_run_inspect_parser.add_argument(
        "--request-id", required=True, help="Adapter request id"
    )
    orchestration_run_inspect_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_run_inspect_parser.add_argument(
        "--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)"
    )
    orchestration_run_inspect_parser.add_argument(
        "--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)"
    )
    orchestration_run_inspect_parser.add_argument(
        "--aggregate-lineage",
        action="store_true",
        help="Aggregate the task recovery lineage from run lifecycle events",
    )
    orchestration_run_inspect_parser.add_argument(
        "--replay",
        action="store_true",
        help="Include the deterministic Stage 14 replay and structured next-action projection",
    )
    _add_global_args(orchestration_run_inspect_parser)
    orchestration_run_inspect_parser.set_defaults(func=_cmd_orchestration_run_inspect)

    # orchestration approval list/get
    orchestration_approval_parser = orchestration_subparsers.add_parser(
        "approval", help="Query read-only approval data through orchestration namespace"
    )
    orchestration_approval_subparsers = orchestration_approval_parser.add_subparsers(
        dest="approval_command", required=True
    )

    orchestration_approval_list_parser = orchestration_approval_subparsers.add_parser(
        "list", help="List approval records from an adapter execution envelope (read-only, envelope-scoped)"
    )
    orchestration_approval_list_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_approval_list_parser.add_argument(
        "--status", default=None, help="Filter approvals by status"
    )
    _add_global_args(orchestration_approval_list_parser)
    orchestration_approval_list_parser.set_defaults(func=_cmd_orchestration_approval_list)

    orchestration_approval_get_parser = orchestration_approval_subparsers.add_parser(
        "get", help="Show an approval record with related request summary (read-only, envelope-scoped)"
    )
    orchestration_approval_get_parser.add_argument(
        "--approval-id", required=True, help="Approval id"
    )
    orchestration_approval_get_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    _add_global_args(orchestration_approval_get_parser)
    orchestration_approval_get_parser.set_defaults(func=_cmd_orchestration_approval_get)

    orchestration_approval_resolve_parser = orchestration_approval_subparsers.add_parser(
        "resolve",
        help="Record an approval decision as a task event (dry-run or commit)",
    )
    orchestration_approval_resolve_parser.add_argument(
        "--approval-id", required=True, help="Approval id"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--task-id", required=True, help="Task id that matches the approval scope"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--request-id", required=True, help="Request id that matches the approval record"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--decision", default=None, help="Approval decision (granted, denied, expired)"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--reason", default=None, help="Reason for the decision"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--events-file", default=None, help="Target event ledger JSONL file"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--tasks-file", default=None, help="Task ledger JSONL file"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the decision event without writing"
    )
    orchestration_approval_resolve_parser.add_argument(
        "--commit", action="store_true", help="Append the decision event to the ledger"
    )
    _add_global_args(orchestration_approval_resolve_parser)
    orchestration_approval_resolve_parser.set_defaults(func=_cmd_orchestration_approval_resolve)

    # orchestration artifact list/get
    orchestration_artifact_parser = orchestration_subparsers.add_parser(
        "artifact", help="Query read-only artifact data through orchestration namespace"
    )
    orchestration_artifact_subparsers = orchestration_artifact_parser.add_subparsers(
        dest="artifact_command", required=True
    )

    orchestration_artifact_list_parser = orchestration_artifact_subparsers.add_parser(
        "list", help="List artifacts from an adapter execution envelope (read-only, envelope-scoped)"
    )
    orchestration_artifact_list_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_artifact_list_parser.add_argument(
        "--type", default=None, help="Filter artifacts by artifact_type"
    )
    orchestration_artifact_list_parser.add_argument(
        "--request-id", default=None, help="Filter artifacts by request_id"
    )
    _add_global_args(orchestration_artifact_list_parser)
    orchestration_artifact_list_parser.set_defaults(func=_cmd_orchestration_artifact_list)

    orchestration_artifact_get_parser = orchestration_artifact_subparsers.add_parser(
        "get", help="Show an artifact with related request summary (read-only, envelope-scoped)"
    )
    orchestration_artifact_get_parser.add_argument(
        "--artifact-id", required=True, help="Artifact id (native id or artifact-NNNN)"
    )
    orchestration_artifact_get_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    _add_global_args(orchestration_artifact_get_parser)
    orchestration_artifact_get_parser.set_defaults(func=_cmd_orchestration_artifact_get)

    # orchestration report generate
    orchestration_report_parser = orchestration_subparsers.add_parser(
        "report", help="Generate read-only reports through orchestration namespace"
    )
    orchestration_report_subparsers = orchestration_report_parser.add_subparsers(
        dest="report_command", required=True
    )

    orchestration_report_generate_parser = orchestration_report_subparsers.add_parser(
        "generate", help="Generate a report for a task + request pair (read-only, runtime-report-backed)"
    )
    orchestration_report_generate_parser.add_argument(
        "--task-id", required=True, help="Task id"
    )
    orchestration_report_generate_parser.add_argument(
        "--request-id", required=True, help="Adapter request id"
    )
    orchestration_report_generate_parser.add_argument(
        "--envelope", required=True, help="Path to adapter execution envelope JSON file"
    )
    orchestration_report_generate_parser.add_argument(
        "--tasks-file", default=None, help="Path to tasks JSONL file (default: tasks/tasks.jsonl)"
    )
    orchestration_report_generate_parser.add_argument(
        "--events-file", default=None, help="Path to events JSONL file (default: tasks/events.jsonl)"
    )
    orchestration_report_generate_parser.add_argument(
        "--aggregate-lineage",
        action="store_true",
        help="Aggregate the task recovery lineage from run lifecycle events",
    )
    orchestration_report_generate_parser.add_argument(
        "--replay",
        action="store_true",
        help="Include the deterministic Stage 14 replay and structured next-action projection",
    )
    _add_global_args(orchestration_report_generate_parser)
    orchestration_report_generate_parser.set_defaults(func=_cmd_orchestration_report_generate)

    # orchestration adapter list/inspect
    orchestration_adapter_parser = orchestration_subparsers.add_parser(
        "adapter", help="Query read-only adapter capability registry through orchestration namespace"
    )
    orchestration_adapter_subparsers = orchestration_adapter_parser.add_subparsers(
        dest="adapter_command", required=True
    )

    orchestration_adapter_list_parser = orchestration_adapter_subparsers.add_parser(
        "list", help="List adapters from the source-backed capability registry"
    )
    orchestration_adapter_list_parser.add_argument(
        "--type", default=None, choices=["agent", "tool", "service"], help="Filter by adapter type"
    )
    orchestration_adapter_list_parser.add_argument(
        "--risk", default=None, choices=["local", "external", "destructive", "privileged"], help="Filter by risk level"
    )
    orchestration_adapter_list_parser.add_argument(
        "--capability", default=None, help="Filter by supported capability"
    )
    _add_global_args(orchestration_adapter_list_parser)
    orchestration_adapter_list_parser.set_defaults(func=_cmd_orchestration_adapter_list)

    orchestration_adapter_inspect_parser = orchestration_adapter_subparsers.add_parser(
        "inspect", help="Inspect a single adapter from the source-backed capability registry"
    )
    orchestration_adapter_inspect_parser.add_argument(
        "adapter_id", help="Adapter id"
    )
    _add_global_args(orchestration_adapter_inspect_parser)
    orchestration_adapter_inspect_parser.set_defaults(func=_cmd_orchestration_adapter_inspect)

    # task queries
    task_parser = subparsers.add_parser("task", help="Query read-only task ledger data")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    task_status_parser = task_subparsers.add_parser("status", help="Show a task snapshot")
    task_status_parser.add_argument("task_id", help="Task id")
    _add_global_args(task_status_parser)
    task_status_parser.set_defaults(func=_cmd_task_status)

    task_events_parser = task_subparsers.add_parser("events", help="Show task event history")
    task_events_parser.add_argument("task_id", help="Task id")
    _add_global_args(task_events_parser)
    task_events_parser.set_defaults(func=_cmd_task_events)

    task_validate_parser = task_subparsers.add_parser("validate", help="Validate a JSONL ledger file against a schema")
    task_validate_parser.add_argument("--record-file", required=True, help="Path to JSONL record file")
    task_validate_parser.add_argument("--schema", required=True, choices=["task", "event"], help="Schema type: task or event")
    _add_global_args(task_validate_parser)
    task_validate_parser.set_defaults(func=_cmd_task_validate)

    task_check_ledger_parser = task_subparsers.add_parser("check-ledger", help="Check cross-record consistency between task and event ledgers")
    task_check_ledger_parser.add_argument("--tasks-file", required=True, help="Path to tasks JSONL file")
    task_check_ledger_parser.add_argument("--events-file", required=True, help="Path to events JSONL file")
    _add_global_args(task_check_ledger_parser)
    task_check_ledger_parser.set_defaults(func=_cmd_task_check_ledger)

    # agents list
    agents_parser = subparsers.add_parser("agents", help="List registered agents")
    agents_parser.add_argument("--capability", default=None, help="Filter by capability")
    _add_global_args(agents_parser)
    agents_parser.set_defaults(func=_cmd_agents_list)
    agents_sub = agents_parser.add_subparsers(dest="agents_command")
    agents_list_parser = agents_sub.add_parser("list", help="List agents")
    agents_list_parser.add_argument("--capability", default=None, help="Filter by capability")
    _add_global_args(agents_list_parser)
    agents_list_parser.set_defaults(func=_cmd_agents_list)

    # adapters list
    adapters_parser = subparsers.add_parser("adapters", help="List registered adapters")
    adapters_parser.add_argument("--kind", default=None, help="Filter by kind")
    adapters_parser.add_argument("--risk", default=None, help="Filter by risk level")
    _add_global_args(adapters_parser)
    adapters_parser.set_defaults(func=_cmd_adapters_list)
    adapters_sub = adapters_parser.add_subparsers(dest="adapters_command")
    adapters_list_parser = adapters_sub.add_parser("list", help="List adapters")
    adapters_list_parser.add_argument("--kind", default=None, help="Filter by kind")
    adapters_list_parser.add_argument("--risk", default=None, help="Filter by risk level")
    _add_global_args(adapters_list_parser)
    adapters_list_parser.set_defaults(func=_cmd_adapters_list)

    # policies list
    policies_parser = subparsers.add_parser("policies", help="List policy files")
    _add_global_args(policies_parser)
    policies_parser.set_defaults(func=_cmd_policies_list)
    policies_sub = policies_parser.add_subparsers(dest="policies_command")
    policies_list_parser = policies_sub.add_parser("list", help="List policies")
    _add_global_args(policies_list_parser)
    policies_list_parser.set_defaults(func=_cmd_policies_list)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _ensure_global_defaults(args)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        result = CheckResult(
            status="error",
            findings=[],
            next_action=f"File not found: {exc.filename}",
        )
        return emit(result, json_output=args.json, no_color=args.no_color)
    except Exception as exc:  # noqa: BLE001
        result = CheckResult(
            status="error",
            findings=[],
            next_action=f"Unexpected error: {exc}",
        )
        return emit(result, json_output=args.json, no_color=args.no_color)


if __name__ == "__main__":
    sys.exit(main())

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
from .loader import load_adapters, load_agents, load_policies, discover_policies, normalize_path
from .policy import check_action, check_path, check_text
from .policy_profile import resolve_profile
from .result import CheckResult, emit, EXIT_ERROR, EXIT_PASS, _STATUS_TO_EXIT
from .ledger_consistency import check_ledger_consistency
from .runtime_gate import RuntimeGateResult, check_runtime_gate
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = _root_path(args)
    result = run_doctor(root)
    return emit(result, json_output=args.json, no_color=args.no_color)


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

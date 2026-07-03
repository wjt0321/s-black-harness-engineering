"""Minimal read-only CLI entry point for agent-runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .doctor import run_doctor
from .loader import load_adapters, load_agents, load_policies, discover_policies, normalize_path
from .policy import check_action, check_path, check_text
from .result import CheckResult, emit, EXIT_ERROR, EXIT_PASS
from .tasks import find_task, find_task_events, render_task_events, render_task_status


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=argparse.SUPPRESS, help="Project root directory")
    parser.add_argument("--policy", default=argparse.SUPPRESS, help="Explicit policy file")
    parser.add_argument(
        "--policy-profile",
        default=argparse.SUPPRESS,
        help="Policy profile to load: s-black, wangcai, dabai, or all",
    )
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON")
    parser.add_argument("--no-color", action="store_true", default=argparse.SUPPRESS, help="Disable color output")
    parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help="Only output necessary results")
    parser.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS, help="Output more diagnostic info")


def _ensure_global_defaults(args: argparse.Namespace) -> None:
    defaults = {
        "root": ".",
        "policy": None,
        "policy_profile": None,
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


def _policy_profile(args: argparse.Namespace) -> str | None:
    if args.policy:
        return None
    return args.policy_profile or "all"


def _cmd_check_text(args: argparse.Namespace) -> int:
    root = _root_path(args)
    policy_path = _explicit_policy(args, root)
    text = _read_text_source(args)
    result = check_text(root, text, explicit_policy=policy_path, profile=_policy_profile(args))
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
        profile=_policy_profile(args),
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
        profile=_policy_profile(args),
    )
    return emit(result, json_output=args.json, no_color=args.no_color)


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
    policy_paths = discover_policies(root, profile=_policy_profile(args))
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

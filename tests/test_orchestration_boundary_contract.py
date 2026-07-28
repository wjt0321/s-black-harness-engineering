"""Contract tests for the reconciled orchestration CLI surface."""

from __future__ import annotations

import argparse

from agent_runtime.cli import build_parser
from agent_runtime.orchestration_contract import build_contract_manifest


def _nested_parser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    """Return a named argparse subparser from a parser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and name in action.choices:
            return action.choices[name]
    raise AssertionError(f"subparser not found: {name}")


def _subparser_names(parser: argparse.ArgumentParser) -> set[str]:
    """Return the explicitly registered choices for a parser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_orchestration_surface_matches_reconciliation_contract() -> None:
    """Freeze the real CLI commands used by the stable/preview matrix."""
    root = build_parser()
    orchestration = _nested_parser(root, "orchestration")

    assert _subparser_names(orchestration) == {
        "overview",
        "route",
        "preflight",
        "task",
        "run",
        "approval",
        "artifact",
        "report",
        "adapter",
        "collaboration",
        "socket",
        "contract",
        "profile",
        "workflow",
        "control-panel",
        "execution",
        "external-agent",
    }
    assert _subparser_names(_nested_parser(orchestration, "route")) == {
        "preview",
        "snapshot",
    }
    assert _subparser_names(_nested_parser(orchestration, "task")) == {
        "submit",
        "list",
        "get",
    }
    assert _subparser_names(_nested_parser(orchestration, "run")) == {
        "list",
        "inspect",
    }
    assert _subparser_names(_nested_parser(orchestration, "approval")) == {
        "list",
        "get",
        "resolve",
    }
    assert _subparser_names(_nested_parser(orchestration, "artifact")) == {
        "list",
        "get",
    }
    assert _subparser_names(_nested_parser(orchestration, "report")) == {
        "generate",
    }
    assert _subparser_names(_nested_parser(orchestration, "adapter")) == {
        "list",
        "inspect",
    }
    collaboration = _nested_parser(orchestration, "collaboration")
    assert _subparser_names(collaboration) == {
        "plan",
        "validate",
        "inspect",
        "dispatch",
        "manual-board",
        "run-state",
        "action-eligibility",
        "inbox",
    }
    assert _subparser_names(_nested_parser(collaboration, "manual-board")) == {
        "inspect",
    }
    assert _subparser_names(_nested_parser(collaboration, "dispatch")) == {
        "validate",
        "inspect",
    }
    assert _subparser_names(_nested_parser(collaboration, "run-state")) == {
        "inspect",
    }
    assert _subparser_names(
        _nested_parser(collaboration, "action-eligibility")
    ) == {"inspect"}
    assert _subparser_names(_nested_parser(collaboration, "inbox")) == {
        "inspect",
    }
    external_agent = _nested_parser(orchestration, "external-agent")
    assert _subparser_names(external_agent) == {"status"}
    external_status = _nested_parser(external_agent, "status")
    assert _subparser_names(external_status) == {"inspect"}
    external_status_options = {
        option
        for action in _nested_parser(external_status, "inspect")._actions
        for option in action.option_strings
    }
    assert {"--profile", "--evaluated-at", "--expected-after-generation"} <= external_status_options
    assert {
        "--snapshot-file",
        "--ttl-seconds",
        "--adapter-id",
        "--producer-id",
        "--transport-id",
        "--commit",
    }.isdisjoint(external_status_options)
    socket = _nested_parser(orchestration, "socket")
    assert _subparser_names(socket) == {
        "list",
        "inspect",
        "readiness",
    }
    assert _subparser_names(_nested_parser(socket, "readiness")) == {"collect"}
    assert _subparser_names(_nested_parser(orchestration, "contract")) == {
        "inspect",
        "check",
    }
    assert _subparser_names(_nested_parser(orchestration, "profile")) == {
        "list",
        "inspect",
        "check",
    }
    assert _subparser_names(_nested_parser(orchestration, "workflow")) == {
        "plan",
        "check",
    }
    control_panel = _nested_parser(orchestration, "control-panel")
    assert _subparser_names(control_panel) == {
        "handoff",
        "snapshot",
        "render",
        "live",
    }
    live_options = {
        option
        for action in _nested_parser(control_panel, "live")._actions
        for option in action.option_strings
    }
    assert {"--refresh-seconds", "--chain-limit"} <= live_options
    assert {"--commit", "--approval-binding-id", "--decision"}.isdisjoint(live_options)
    assert _subparser_names(_nested_parser(orchestration, "execution")) == {
        "git-status",
        "pi-binding",
        "pi-print",
        "readiness",
        "recovery",
        "single-work-item",
        "single-work-item-evidence",
        "single-work-item-evidence-recover",
        "single-work-item-review",
        "external-agent-chain",
        "trust",
    }
    execution = _nested_parser(orchestration, "execution")
    evidence_options = {
        option
        for action in _nested_parser(execution, "single-work-item-evidence")._actions
        for option in action.option_strings
    }
    assert {"--attempt-id", "--include-content"} <= evidence_options
    recovery_options = {
        option
        for action in _nested_parser(execution, "single-work-item-evidence-recover")._actions
        for option in action.option_strings
    }
    assert {"--attempt-id", "--approval-binding-id", "--commit"} <= recovery_options
    review_options = {
        option
        for action in _nested_parser(execution, "single-work-item-review")._actions
        for option in action.option_strings
    }
    assert {"--attempt-id", "--decision", "--comment", "--evaluated-at", "--approval-binding-id", "--commit"} <= review_options
    chain = _nested_parser(execution, "external-agent-chain")
    assert _subparser_names(chain) == {
        "inspect", "recover-final-decision", "start", "final-decision",
    }
    chain_start_options = {
        option
        for action in _nested_parser(chain, "start")._actions
        for option in action.option_strings
    }
    assert {"--chain-id", "--task-id", "--collaboration-file", "--goal", "--evaluated-at", "--approval-binding-id", "--commit"} <= chain_start_options
    chain_recover_options = {
        option
        for action in _nested_parser(chain, "recover-final-decision")._actions
        for option in action.option_strings
    }
    assert {"--chain-id", "--approval-binding-id", "--commit"} <= chain_recover_options
    assert _subparser_names(
        _nested_parser(_nested_parser(orchestration, "execution"), "trust")
    ) == {"bind", "inspect"}
    assert _subparser_names(
        _nested_parser(_nested_parser(orchestration, "execution"), "pi-binding")
    ) == {"bind", "inspect"}
    assert _subparser_names(
        _nested_parser(_nested_parser(orchestration, "execution"), "recovery")
    ) == {"close-open", "inspect", "list-open"}
    recovery = _nested_parser(_nested_parser(orchestration, "execution"), "recovery")
    close_options = {
        option
        for action in _nested_parser(recovery, "close-open")._actions
        for option in action.option_strings
    }
    assert {
        "--attempt-id",
        "--expected-started-event-id",
        "--expected-plan-hash",
        "--commit",
    } <= close_options
    assert {
        "--file",
        "--path",
        "--events-file",
        "--tasks-file",
        "--event-type",
        "--phase",
        "--failure-code",
        "--guard-status",
        "--evidence",
        "--actor",
        "--stdin",
    }.isdisjoint(close_options)

    trust = _nested_parser(_nested_parser(orchestration, "execution"), "trust")
    bind_options = {
        option
        for action in _nested_parser(trust, "bind")._actions
        for option in action.option_strings
    }
    assert {
        "--expected-binding-id",
        "--expected-executable-identity",
        "--expected-path-identity",
    } <= bind_options
    inspect_options = {
        option
        for action in _nested_parser(trust, "inspect")._actions
        for option in action.option_strings
    }
    assert {
        "--path",
        "--binding-path",
        "--executable",
        "--path-value",
        "--actor",
    }.isdisjoint(inspect_options)


def test_stage13_run_flags_keep_explicit_preview_and_lineage_boundaries() -> None:
    """Ensure preview, controlled-write, and lineage flags stay explicit."""
    root = build_parser()
    run = _nested_parser(_nested_parser(root, "orchestration"), "run")
    option_strings = {
        option
        for action in run._actions
        for option in action.option_strings
    }

    assert {"--dry-run", "--commit"} <= option_strings
    assert {"--retry-of", "--fallback-from", "--fallback-to"} <= option_strings
    assert "--snapshot" in option_strings
    assert "--aggregate-lineage" not in option_strings

    inspect = _nested_parser(run, "inspect")
    inspect_options = {
        option
        for action in inspect._actions
        for option in action.option_strings
    }
    assert "--aggregate-lineage" in inspect_options
    assert "--replay" in inspect_options
    assert "--snapshot" not in inspect_options

    report = _nested_parser(_nested_parser(_nested_parser(root, "orchestration"), "report"), "generate")
    report_options = {
        option
        for action in report._actions
        for option in action.option_strings
    }
    assert "--aggregate-lineage" in report_options
    assert "--replay" in report_options

def test_contract_manifest_available_commands_exist_in_cli_surface() -> None:
    """Prevent the machine-readable manifest from drifting from argparse."""
    root = build_parser()

    for entry in build_contract_manifest().entries:
        if entry.availability == "unavailable":
            assert entry.commands == ()
            continue

        for command in entry.commands:
            parser = root
            for segment in command:
                parser = _nested_parser(parser, segment)

def test_contract_manifest_key_flags_exist_on_declared_commands() -> None:
    """Freeze the flags that automation uses to select explicit boundaries."""
    root = build_parser()

    for entry in build_contract_manifest().entries:
        declared_options: set[str] = set()
        for command in entry.commands:
            parser = root
            for segment in command:
                parser = _nested_parser(parser, segment)
            declared_options.update(
                option
                for action in parser._actions
                for option in action.option_strings
            )

        assert set(entry.key_flags) <= declared_options

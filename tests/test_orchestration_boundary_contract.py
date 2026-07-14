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
        "contract",
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
    assert _subparser_names(_nested_parser(orchestration, "contract")) == {
        "inspect",
    }


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

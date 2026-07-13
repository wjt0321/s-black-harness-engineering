"""Contract tests for the Stage 13 orchestration CLI surface."""

from __future__ import annotations

import argparse

from agent_runtime.cli import build_parser


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


def test_stage13_orchestration_surface_matches_reconciliation_contract() -> None:
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
    assert "--snapshot" not in inspect_options

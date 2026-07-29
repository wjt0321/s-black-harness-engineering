"""Structured GUI approval envelope for existing bounded chain operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .orchestration_external_agent_chain import (
    ExternalAgentChainResult,
    abandon_chain_final_decision,
    commit_chain_final_decision,
    execute_chain_start,
    preview_abandon_chain_final_decision,
    preview_chain_final_decision,
    preview_chain_start,
)
from .result import Finding

SCHEMA_VERSION = "control-panel-approval/v1"


def _command_chain_id(command: object) -> str:
    if isinstance(command, dict) and isinstance(command.get("chain_id"), str):
        return command["chain_id"]
    return ""


def _invalid(chain_id: str = "") -> ExternalAgentChainResult:
    return ExternalAgentChainResult(
        "validation_failed",
        chain_id,
        findings=(
            Finding(
                "control-panel-approval-command-invalid",
                "error",
                "error",
                "图形界面确认请求不符合固定结构；不会调用链路操作。",
            ),
        ),
    )


def _start_fields(command: object) -> tuple[str, str, str, str] | None:
    if not isinstance(command, dict) or set(command) != {
        "version",
        "contract",
        "operation",
        "chain_id",
        "task_id",
        "collaboration_file",
        "goal",
    }:
        return None
    if (
        command.get("version") != 1
        or command.get("contract") != SCHEMA_VERSION
        or command.get("operation") != "start_chain"
    ):
        return None
    fields = tuple(command.get(name) for name in ("chain_id", "task_id", "collaboration_file", "goal"))
    if not all(isinstance(value, str) and value and "\x00" not in value for value in fields):
        return None
    return fields  # type: ignore[return-value]


def _abandon_final_fields(command: object) -> str | None:
    if not isinstance(command, dict) or set(command) != {
        "version",
        "contract",
        "operation",
        "chain_id",
    }:
        return None
    if (
        command.get("version") != 1
        or command.get("contract") != SCHEMA_VERSION
        or command.get("operation") != "abandon_final_decision"
    ):
        return None
    chain_id = command.get("chain_id")
    if not isinstance(chain_id, str) or not chain_id or "\x00" in chain_id:
        return None
    return chain_id


def _final_fields(command: object) -> tuple[str, str, str] | None:
    if not isinstance(command, dict) or set(command) != {
        "version",
        "contract",
        "operation",
        "chain_id",
        "decision",
        "comment",
    }:
        return None
    if (
        command.get("version") != 1
        or command.get("contract") != SCHEMA_VERSION
        or command.get("operation") != "final_decision"
    ):
        return None
    chain_id = command.get("chain_id")
    decision = command.get("decision")
    comment = command.get("comment")
    if (
        not isinstance(chain_id, str)
        or not chain_id
        or "\x00" in chain_id
        or not isinstance(decision, str)
            or decision not in {"approve", "request_changes"}
        or not isinstance(comment, str)
        or not comment
        or "\x00" in comment
    ):
        return None
    return chain_id, decision, comment


def preview_control_panel_approval(
    root: Path,
    *,
    command: dict[str, Any],
    evaluated_at: str,
) -> ExternalAgentChainResult:
    """Preview one strict GUI start request without executing it."""
    if not isinstance(evaluated_at, str) or not evaluated_at:
        return _invalid(_command_chain_id(command))
    start = _start_fields(command)
    if start is not None:
        chain_id, task_id, collaboration_file, goal = start
        return preview_chain_start(
            root.resolve(),
            chain_id=chain_id,
            task_id=task_id,
            collaboration_file=collaboration_file,
            goal=goal,
            evaluated_at=evaluated_at,
        )
    abandon_chain_id = _abandon_final_fields(command)
    if abandon_chain_id is not None:
        return preview_abandon_chain_final_decision(root.resolve(), chain_id=abandon_chain_id)
    final = _final_fields(command)
    if final is not None:
        chain_id, decision, comment = final
        return preview_chain_final_decision(
            root.resolve(),
            chain_id=chain_id,
            decision=decision,
            comment=comment,
            evaluated_at=evaluated_at,
        )
    return _invalid(_command_chain_id(command))


def commit_control_panel_approval(
    root: Path,
    *,
    command: dict[str, Any],
    approval_binding_id: str | None,
    evaluated_at: str,
) -> ExternalAgentChainResult:
    """Commit one strict GUI request through the matching existing chain operation."""
    if not isinstance(evaluated_at, str) or not evaluated_at:
        return _invalid(_command_chain_id(command))
    start = _start_fields(command)
    if start is not None:
        chain_id, task_id, collaboration_file, goal = start
        return execute_chain_start(
            root.resolve(),
            chain_id=chain_id,
            task_id=task_id,
            collaboration_file=collaboration_file,
            goal=goal,
            evaluated_at=evaluated_at,
            approval_binding_id=approval_binding_id,
            commit=True,
        )
    abandon_chain_id = _abandon_final_fields(command)
    if abandon_chain_id is not None:
        return abandon_chain_final_decision(
            root.resolve(),
            chain_id=abandon_chain_id,
            approval_binding_id=approval_binding_id,
            commit=True,
        )
    final = _final_fields(command)
    if final is not None:
        chain_id, decision, comment = final
        return commit_chain_final_decision(
            root.resolve(),
            chain_id=chain_id,
            decision=decision,
            comment=comment,
            evaluated_at=evaluated_at,
            approval_binding_id=approval_binding_id,
            commit=True,
        )
    return _invalid(_command_chain_id(command))

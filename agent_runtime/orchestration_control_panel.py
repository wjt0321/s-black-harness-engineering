"""Stage 16/17 deterministic Control Panel representations and host handoff."""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .loader import normalize_path
from .orchestration_adapter import list_adapters
from .orchestration_collaboration import inspect_collaboration_plan
from .orchestration_collaboration_dispatch import inspect_collaboration_dispatch
from .orchestration_collaboration_run_state import inspect_collaboration_run_state
from .orchestration_collaboration_action_eligibility import (
    inspect_collaboration_action_eligibility,
)
from .orchestration_collaboration_operator_inbox import (
    inspect_collaboration_operator_inbox,
)
from .orchestration_manual_board import inspect_manual_board
from .orchestration_external_agent_live_status import inspect_external_agent_live_status
from .orchestration_socket import list_sockets
from .orchestration_approval import list_approvals
from .orchestration_artifact import list_artifacts
from .orchestration_contract import build_contract_manifest
from .orchestration_overview import check_overview
from .orchestration_profile import list_automation_profiles
from .orchestration_run import list_runs
from .orchestration_tasks import list_tasks
from .result import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NEEDS_INPUT,
    EXIT_PASS,
    EXIT_VALIDATION_FAILED,
)

SCHEMA_VERSION = "control-plane/control-panel-snapshot/v1"
HANDOFF_SCHEMA_VERSION = "control-plane/control-panel-handoff/v1"
HTML_RENDERER_VERSION = "control-plane/control-panel-html/v1"
_SECTION_ORDER = (
    "overview",
    "tasks",
    "adapters",
    "automation",
    "runs",
    "approvals",
    "artifacts",
    "reports",
)
_STATUS_RANK = {
    "pass": 0,
    "unavailable": 0,
    "needs_input": 1,
    "blocked": 2,
    "validation_failed": 3,
    "error": 4,
}


def _exit_code(status: str) -> int:
    if status == "pass":
        return EXIT_PASS
    if status == "blocked":
        return EXIT_BLOCKED
    if status == "needs_input":
        return EXIT_NEEDS_INPUT
    if status == "validation_failed":
        return EXIT_VALIDATION_FAILED
    return EXIT_ERROR


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _safe_envelope_reference(root: Path, envelope_file: str | None) -> str | None:
    if envelope_file is None:
        return None
    resolved_root = root.resolve()
    resolved_path = (resolved_root / envelope_file).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        return None
    return normalize_path(resolved_path.relative_to(resolved_root))


def _section(payload: dict[str, Any], *, scope: str, availability: str) -> dict[str, Any]:
    return {
        **payload,
        "scope": scope,
        "availability": availability,
    }


def _unavailable_section(
    *,
    scope: str,
    availability: str,
    reason: str,
    message: str,
    command_hint: str,
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "scope": scope,
        "availability": availability,
        "reason": reason,
        "message": message,
        "command_hint": command_hint,
    }


def _deduplicate_findings(sections: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in sections.values():
        for finding in section.get("findings", []):
            key = json.dumps(finding, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)
    return tuple(findings)


def _aggregate_status(sections: dict[str, dict[str, Any]]) -> str:
    statuses = [
        section.get("status", "error")
        for section in sections.values()
        if section.get("status") != "unavailable"
    ]
    return max(statuses, key=lambda value: _STATUS_RANK.get(value, 4), default="pass")


@dataclass(frozen=True)
class ControlPanelSnapshot:
    """Versioned aggregate read model for the local static Control Panel."""

    status: str
    source: dict[str, Any]
    summary: dict[str, Any]
    sections: dict[str, dict[str, Any]]
    findings: tuple[dict[str, Any], ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = SCHEMA_VERSION

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def _payload_without_id(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "source": self.source,
            "summary": self.summary,
            "sections": self.sections,
            "guarantees": {
                "deterministic": True,
                "read_only": True,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
                "executes_commands": False,
                "executes_adapters": False,
                "starts_service": False,
            },
        }
        if self.findings:
            payload["findings"] = list(self.findings)
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_id()
        return {
            **payload,
            "snapshot_id": _canonical_hash(payload),
        }

    def render_human(self) -> str:
        payload = self.to_dict()
        summary = self.summary
        lines = [f"CONTROL PANEL SNAPSHOT {self.status.upper()}"]
        lines.append(f"snapshot_id={payload['snapshot_id']}")
        lines.append(
            "summary: "
            f"tasks={summary['total_tasks']} "
            f"blocked={summary['blocked_tasks']} "
            f"adapters={summary['total_adapters']} "
            f"runs={summary['run_count']} "
            f"pending_approvals={summary['pending_approval_count']} "
            f"artifacts={summary['artifact_count']}"
        )
        lines.append(
            "sections: "
            + " ".join(
                f"{name}={section['status']}"
                for name, section in self.sections.items()
            )
        )
        for finding in self.findings:
            lines.append(
                f"- {finding.get('rule_id', 'control-panel-source-error')}: "
                f"{finding.get('message', 'Source read model failed.')}"
            )
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ControlPanelHandoff:
    """Versioned stdio descriptor for host consumption of panel representations."""

    status: str
    source: dict[str, Any]
    snapshot: dict[str, Any]
    render: dict[str, Any]
    findings: tuple[dict[str, Any], ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = HANDOFF_SCHEMA_VERSION

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def _payload_without_id(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "source": self.source,
            "snapshot": self.snapshot,
            "render": self.render,
            "boundaries": {
                "read_only": True,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
                "starts_service": False,
                "executes_commands": False,
                "executes_adapters": False,
            },
            "findings": list(self.findings),
            "next_action": self.next_action,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_id()
        return {
            "status": payload["status"],
            "schema_version": payload["schema_version"],
            "handoff_id": _canonical_hash(payload),
            "source": payload["source"],
            "snapshot": payload["snapshot"],
            "render": payload["render"],
            "boundaries": payload["boundaries"],
            "findings": payload["findings"],
            "next_action": payload["next_action"],
        }

    def render_human(self) -> str:
        payload = self.to_dict()
        lines = [f"CONTROL PANEL HANDOFF {self.status.upper()}"]
        lines.append(f"handoff_id={payload['handoff_id']}")
        lines.append(f"snapshot_id={self.snapshot['snapshot_id']}")
        lines.append(f"render_id={self.render['render_id']}")
        lines.append(
            "representations: "
            f"snapshot={self.snapshot['media_type']} "
            f"render={self.render['media_type']}"
        )
        for finding in self.findings:
            lines.append(
                f"- {finding.get('rule_id', 'control-panel-source-error')}: "
                f"{finding.get('message', 'Source read model failed.')}"
            )
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


def build_control_panel_snapshot(
    root: Path,
    *,
    envelope_file: str | None = None,
    collaboration_file: str | None = None,
    dispatch_file: str | None = None,
    manual_board_file: str | None = None,
    collaboration_run_file: str | None = None,
    collaboration_action_file: str | None = None,
    collaboration_inbox_file: str | None = None,
    external_agent_evaluated_at: str | None = None,
) -> ControlPanelSnapshot:
    """Aggregate existing safe read models without executing or writing."""
    overview = _section(
        check_overview(root).to_dict(),
        scope="project",
        availability="stable",
    )
    tasks = _section(
        list_tasks(root).to_dict(),
        scope="project",
        availability="stable",
    )
    adapters = _section(
        list_adapters(root).to_dict(),
        scope="registry",
        availability="stable",
    )
    sockets = list_sockets(root).to_dict()
    adapters["agent_sockets"] = sockets.get("sockets", [])
    adapters["agent_socket_status"] = sockets["status"]
    if sockets.get("findings"):
        adapters.setdefault("findings", []).extend(sockets["findings"])

    manifest = build_contract_manifest().to_dict()
    profiles = list_automation_profiles(root).to_dict()
    automation_status = profiles["status"]
    automation: dict[str, Any] = {
        "status": automation_status,
        "scope": "project",
        "availability": "stable",
        "contract_schema_version": manifest["schema_version"],
        "contract_summary": manifest["summary"],
        "profiles_schema_version": profiles["schema_version"],
        "profiles": profiles.get("profiles", []),
    }
    if "findings" in profiles:
        automation["findings"] = profiles["findings"]
    if "next_action" in profiles:
        automation["next_action"] = profiles["next_action"]

    if envelope_file is None:
        runs = _unavailable_section(
            scope="envelope",
            availability="stable_limited",
            reason="envelope_required",
            message="Run collection is envelope-scoped; provide --envelope to project it.",
            command_hint="orchestration control-panel snapshot --envelope <path>",
        )
        approvals = _unavailable_section(
            scope="envelope",
            availability="stable_limited",
            reason="envelope_required",
            message="Approval collection is envelope-scoped; provide --envelope to project it.",
            command_hint="orchestration control-panel snapshot --envelope <path>",
        )
        artifacts = _unavailable_section(
            scope="envelope",
            availability="stable_limited",
            reason="envelope_required",
            message="Artifact collection is envelope-scoped; provide --envelope to project it.",
            command_hint="orchestration control-panel snapshot --envelope <path>",
        )
    else:
        runs = _section(
            list_runs(root, envelope_file).to_dict(),
            scope="envelope",
            availability="stable_limited",
        )
        approvals = _section(
            list_approvals(root, envelope_file).to_dict(),
            scope="envelope",
            availability="stable_limited",
        )
        artifacts = _section(
            list_artifacts(root, envelope_file).to_dict(),
            scope="envelope",
            availability="stable_limited",
        )

    reports = _unavailable_section(
        scope="request",
        availability="stable_limited",
        reason="request_context_required",
        message=(
            "Reports remain request-scoped and are not presented as a persistent collection."
        ),
        command_hint=(
            "orchestration report generate --task-id <id> --request-id <id> "
            "--envelope <path>"
        ),
    )

    sections = {
        "overview": overview,
        "tasks": tasks,
        "adapters": adapters,
        "automation": automation,
        "runs": runs,
        "approvals": approvals,
        "artifacts": artifacts,
        "reports": reports,
    }
    if external_agent_evaluated_at is not None:
        live_results = [
            inspect_external_agent_live_status(
                root,
                external_agent_evaluated_at,
                profile_id=profile_id,
            )
            for profile_id in ("pi-local", "omp-local")
        ]
        live_findings = [
            finding.to_dict()
            for result in live_results
            for finding in result.findings
        ]
        live_status = max(
            (result.status for result in live_results),
            key=lambda value: _STATUS_RANK.get(value, 4),
            default="pass",
        )
        sections["external_agents"] = {
            "status": live_status,
            "scope": "runtime",
            "availability": "live_read_only",
            "evaluated_at": external_agent_evaluated_at,
            "dispatch_authorized": False,
            "agents": [
                result.gui_projection
                for result in live_results
                if result.gui_projection is not None
            ],
            "observations": [
                {
                    "profile_id": result.profile_id,
                    "observed_at": (
                        result.evidence.get("observed_at")
                        if result.evidence is not None
                        else None
                    ),
                    "expires_at": (
                        result.evidence.get("expires_at")
                        if result.evidence is not None
                        else None
                    ),
                    "evidence_valid": bool(
                        result.evidence is not None
                        and result.gui_projection
                        and result.gui_projection.get("readiness", {}).get("binding_valid")
                    ),
                }
                for result in live_results
            ],
            "findings": live_findings,
            "safe_summary_zh": "仅展示 Pi/OMP 宿主进程内扩展发布的安全状态；不授予派发或执行权限。",
        }
    if collaboration_file is not None:
        sections["collaboration"] = _section(
            inspect_collaboration_plan(root, collaboration_file).to_dict(),
            scope="file",
            availability="stable_limited",
        )
    if dispatch_file is not None:
        sections["dispatch"] = _section(
            inspect_collaboration_dispatch(root, dispatch_file).to_dict(),
            scope="file",
            availability="experimental",
        )
    if manual_board_file is not None:
        sections["manual_board"] = _section(
            inspect_manual_board(root, manual_board_file).to_dict(),
            scope="file",
            availability="fixture",
        )
    if collaboration_run_file is not None:
        sections["collaboration_run"] = _section(
            inspect_collaboration_run_state(root, collaboration_run_file).to_dict(),
            scope="file",
            availability="fixture",
        )
    if collaboration_action_file is not None:
        sections["collaboration_actions"] = _section(
            inspect_collaboration_action_eligibility(
                root, collaboration_action_file
            ).to_dict(),
            scope="file",
            availability="fixture",
        )
    if collaboration_inbox_file is not None:
        sections["collaboration_inbox"] = _section(
            inspect_collaboration_operator_inbox(root, collaboration_inbox_file).to_dict(),
            scope="file",
            availability="fixture",
        )
    findings = _deduplicate_findings(sections)
    status = _aggregate_status(sections)

    overview_summary = overview["summary"]
    adapter_rows = adapters.get("adapters", [])
    approval_rows = approvals.get("approvals", [])
    summary = {
        "total_tasks": len(tasks.get("tasks", [])),
        "blocked_tasks": overview_summary.get("blocked_tasks", 0),
        "running_tasks": overview_summary.get("running_tasks", 0),
        "total_events": overview_summary.get("total_events", 0),
        "total_adapters": len(adapter_rows),
        "enabled_adapters": sum(bool(item.get("enabled")) for item in adapter_rows),
        "agent_socket_count": len(adapters.get("agent_sockets", [])),
        "enabled_agent_socket_count": sum(
            bool(item.get("enabled")) for item in adapters.get("agent_sockets", [])
        ),
        "automation_profile_count": len(automation.get("profiles", [])),
        "run_count": len(runs.get("runs", [])),
        "pending_approval_count": sum(
            item.get("status") == "pending" for item in approval_rows
        ),
        "artifact_count": len(artifacts.get("artifacts", [])),
        "unavailable_sections": [
            name
            for name, section in sections.items()
            if section.get("status") == "unavailable"
        ],
        "section_statuses": {
            name: section.get("status", "error")
            for name, section in sections.items()
        },
    }
    collaboration_run = sections.get("collaboration_run")
    if collaboration_run is not None:
        summary["collaboration_run_status"] = collaboration_run.get("run", {}).get("status")
    collaboration_actions = sections.get("collaboration_actions")
    if collaboration_actions is not None:
        action_summary = collaboration_actions.get("summary", {})
        summary["eligible_operator_action_count"] = action_summary.get(
            "eligible_count", 0
        )
        summary["blocked_operator_action_count"] = action_summary.get(
            "blocked_count", 0
        )
    collaboration_inbox = sections.get("collaboration_inbox")
    if collaboration_inbox is not None:
        inbox_summary = collaboration_inbox.get("summary", {})
        summary["current_inbox_eligible_count"] = inbox_summary.get(
            "eligible_count", 0
        )
        summary["current_inbox_blocked_count"] = inbox_summary.get(
            "blocked_count", 0
        )
        summary["current_inbox_pending_approval_count"] = inbox_summary.get(
            "pending_approval_count", 0
        )
    next_action = (
        {
            "code": "review_control_panel",
            "message": "Review the local read-only control panel projection.",
        }
        if status == "pass"
        else {
            "code": "fix_control_panel_sources",
            "message": "Fix the failing source read models and rebuild the panel.",
        }
    )
    source: dict[str, Any] = {
        "envelope_file": _safe_envelope_reference(root, envelope_file),
    }
    if external_agent_evaluated_at is not None:
        source["external_agent_evaluated_at"] = external_agent_evaluated_at
    if collaboration_file is not None:
        source["collaboration_file"] = _safe_envelope_reference(root, collaboration_file)
    if dispatch_file is not None:
        source["dispatch_file"] = _safe_envelope_reference(root, dispatch_file)
    if manual_board_file is not None:
        source["manual_board_file"] = _safe_envelope_reference(root, manual_board_file)
    if collaboration_run_file is not None:
        source["collaboration_run_file"] = _safe_envelope_reference(root, collaboration_run_file)
    if collaboration_action_file is not None:
        source["collaboration_action_file"] = _safe_envelope_reference(
            root, collaboration_action_file
        )
    if collaboration_inbox_file is not None:
        source["collaboration_inbox_file"] = _safe_envelope_reference(
            root, collaboration_inbox_file
        )
    return ControlPanelSnapshot(
        status=status,
        source=source,
        summary=summary,
        sections=sections,
        findings=findings,
        next_action=next_action,
    )


def build_control_panel_handoff(
    root: Path,
    *,
    envelope_file: str | None = None,
    collaboration_file: str | None = None,
    dispatch_file: str | None = None,
    manual_board_file: str | None = None,
    collaboration_run_file: str | None = None,
    collaboration_action_file: str | None = None,
    collaboration_inbox_file: str | None = None,
) -> ControlPanelHandoff:
    """Describe existing panel representations without rendering or executing them."""
    snapshot_payload = build_control_panel_snapshot(
        root,
        envelope_file=envelope_file,
        collaboration_file=collaboration_file,
        dispatch_file=dispatch_file,
        manual_board_file=manual_board_file,
        collaboration_run_file=collaboration_run_file,
        collaboration_action_file=collaboration_action_file,
        collaboration_inbox_file=collaboration_inbox_file,
    ).to_dict()
    snapshot_argv = [
        "python",
        "-m",
        "agent_runtime.cli",
        "orchestration",
        "control-panel",
        "snapshot",
    ]
    render_argv = [
        "python",
        "-m",
        "agent_runtime.cli",
        "orchestration",
        "control-panel",
        "render",
    ]
    safe_envelope_file = snapshot_payload["source"]["envelope_file"]
    if safe_envelope_file is not None:
        snapshot_argv.extend(("--envelope", safe_envelope_file))
        render_argv.extend(("--envelope", safe_envelope_file))
    safe_collaboration_file = snapshot_payload["source"].get("collaboration_file")
    if safe_collaboration_file is not None:
        snapshot_argv.extend(("--collaboration-file", safe_collaboration_file))
        render_argv.extend(("--collaboration-file", safe_collaboration_file))
    safe_dispatch_file = snapshot_payload["source"].get("dispatch_file")
    if safe_dispatch_file is not None:
        snapshot_argv.extend(("--dispatch-file", safe_dispatch_file))
        render_argv.extend(("--dispatch-file", safe_dispatch_file))
    safe_manual_board_file = snapshot_payload["source"].get("manual_board_file")
    if safe_manual_board_file is not None:
        snapshot_argv.extend(("--manual-board-file", safe_manual_board_file))
        render_argv.extend(("--manual-board-file", safe_manual_board_file))
    safe_collaboration_run_file = snapshot_payload["source"].get("collaboration_run_file")
    if safe_collaboration_run_file is not None:
        snapshot_argv.extend(("--collaboration-run-file", safe_collaboration_run_file))
        render_argv.extend(("--collaboration-run-file", safe_collaboration_run_file))
    safe_collaboration_action_file = snapshot_payload["source"].get(
        "collaboration_action_file"
    )
    if safe_collaboration_action_file is not None:
        snapshot_argv.extend(
            ("--collaboration-action-file", safe_collaboration_action_file)
        )
        render_argv.extend(
            ("--collaboration-action-file", safe_collaboration_action_file)
        )
    safe_collaboration_inbox_file = snapshot_payload["source"].get(
        "collaboration_inbox_file"
    )
    if safe_collaboration_inbox_file is not None:
        snapshot_argv.extend(
            ("--collaboration-inbox-file", safe_collaboration_inbox_file)
        )
        render_argv.extend(
            ("--collaboration-inbox-file", safe_collaboration_inbox_file)
        )
    snapshot_argv.append("--json")

    snapshot_id = str(snapshot_payload["snapshot_id"])
    render_id = _canonical_hash(
        {
            "snapshot_id": snapshot_id,
            "renderer_version": HTML_RENDERER_VERSION,
        }
    )
    status = str(snapshot_payload["status"])
    next_action = (
        {
            "code": "read_control_panel_representation",
            "message": (
                "Read the snapshot or render representation; do not execute "
                "candidate operations without separate authorization."
            ),
        }
        if status == "pass"
        else {
            "code": "fix_control_panel_sources",
            "message": "Fix the failing source read models before host consumption.",
        }
    )
    return ControlPanelHandoff(
        status=status,
        source=dict(snapshot_payload["source"]),
        snapshot={
            "snapshot_id": snapshot_id,
            "schema_version": snapshot_payload["schema_version"],
            "media_type": "application/json; charset=utf-8",
            "encoding": "utf-8",
            "working_directory": "project_root",
            "scoped_unavailable": [
                {
                    "section": name,
                    "scope": snapshot_payload["sections"][name]["scope"],
                    "reason": snapshot_payload["sections"][name]["reason"],
                }
                for name in _SECTION_ORDER
                if snapshot_payload["sections"][name].get("status") == "unavailable"
            ],
            "argv": snapshot_argv,
        },
        render={
            "render_id": render_id,
            "renderer_version": HTML_RENDERER_VERSION,
            "media_type": "text/html; charset=utf-8",
            "encoding": "utf-8",
            "working_directory": "project_root",
            "self_contained": True,
            "argv": render_argv,
        },
        findings=tuple(snapshot_payload.get("findings", [])),
        next_action=next_action,
    )


_UI_TERMS = {
    "pass": "正常",
    "unavailable": "暂不可用",
    "needs_input": "需要输入",
    "blocked": "已阻止",
    "validation_failed": "校验失败",
    "error": "错误",
    "planned": "已计划",
    "ready": "已就绪",
    "simulated_running": "模拟运行中",
    "simulated_blocked": "模拟阻塞",
    "simulated_complete": "模拟完成",
    "not_executed": "未执行",
    "not_required": "无需审阅",
    "pending": "待审阅",
    "approved": "已批准",
    "changes_requested": "要求修改",
    "awaiting_approval": "等待批准",
    "running": "运行中",
    "cancelling": "取消中",
    "cancelled": "已取消",
    "completed": "已完成",
    "failed": "失败",
    "review_pending": "等待审阅",
    "in_review": "审阅中",
    "accepted": "已接受",
    "rejected": "已拒绝",
    "superseded": "已取代",
    "expected": "待产出",
    "reported": "已报告",
    "validated": "已验证",
    "planner": "规划者",
    "implementer": "实现者",
    "reviewer": "审阅者",
    "researcher": "研究者",
    "tester": "测试者",
    "synthesizer": "汇总者",
    "work_ready": "工作项已就绪",
    "work_started": "工作项已开始",
    "artifact_produced": "已产生产物",
    "handoff_completed": "交接已完成",
    "review_requested": "已请求审阅",
    "review_resolved": "审阅已处理",
    "work_completed": "工作项已完成",
    "review_plan": "审阅计划",
    "approve_start": "批准开始",
    "cancel": "取消",
    "retry": "重试",
    "request_changes": "要求修改",
    "approve_handoff": "批准交接",
    "manual": "人工",
    "operator": "操作者",
    "simulated": "模拟",
    "approve": "批准",
    "analysis": "分析",
    "plan": "计划",
    "draft": "草稿",
    "patch": "代码补丁",
    "test_result": "测试结果",
    "review": "审阅",
    "summary": "摘要",
    "external": "外部",
    "local": "本地",
    "stable": "稳定",
    "stable_limited": "稳定但受限",
    "fixture": "演示样例",
    "experimental": "实验性",
    "declared": "已声明",
    "acp_delegate": "ACP 委派",
    "local_cli": "本地命令行（CLI）",
    "agent_api": "Agent 接口（API）",
    "explicit_plan_binding": "人工计划显式绑定",
    "not_collected": "尚未收集",
    "runner_listed": "运行器已列出",
    "read_only": "只读",
    "controlled_write": "受控写入",
}


def _ui_term(value: Any, *, annotate: bool = True) -> str:
    raw = str(value)
    translated = _UI_TERMS.get(raw)
    if translated is None:
        return raw
    return f"{translated}（{raw}）" if annotate else translated


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple)):
        return html.escape(
            ", ".join(_ui_term(item) if str(item) in _UI_TERMS else str(item) for item in value),
            quote=True,
        )
    if isinstance(value, dict):
        return html.escape(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            quote=True,
        )
    text = str(value)
    return html.escape(text if text else "—", quote=True)


def _status_badge(status: str) -> str:
    safe_status = status if status in _STATUS_RANK else "error"
    return (
        f'<span class="status status--{safe_status}">'
        f'<span class="status__dot" aria-hidden="true"></span>'
        f"{_escape(_ui_term(status))}</span>"
    )


def _table(
    *,
    caption: str,
    columns: tuple[tuple[str, str], ...],
    rows: Iterable[dict[str, Any]],
    empty_message: str,
) -> str:
    row_list = list(rows)
    header = "".join(f"<th scope=\"col\">{_escape(label)}</th>" for _, label in columns)
    body_rows: list[str] = []
    for row in row_list:
        search_text = " ".join(str(row.get(key, "")) for key, _ in columns).lower()
        cells = "".join(
            f"<td>{_escape(_ui_term(row.get(key)) if str(row.get(key)) in _UI_TERMS else row.get(key))}</td>"
            for key, _ in columns
        )
        body_rows.append(
            f'<tr data-search-row data-search="{_escape(search_text)}">{cells}</tr>'
        )
    if not body_rows:
        body_rows.append(
            f'<tr class="empty-row"><td colspan="{len(columns)}">{_escape(empty_message)}</td></tr>'
        )
    return (
        '<div class="table-shell"><table>'
        f"<caption>{_escape(caption)}</caption>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def _section_header(number: str, title: str, section: dict[str, Any]) -> str:
    return (
        '<div class="section-heading">'
        f'<span class="section-index">{_escape(number)}</span>'
        '<div>'
        f"<h2>{_escape(title)}</h2>"
        f'<p>范围（scope）={_escape(section.get("scope"))} · '
        f'可用性（availability）={_escape(section.get("availability"))}</p>'
        "</div>"
        f"{_status_badge(str(section.get('status', 'error')))}"
        "</div>"
    )


def _boundary_callout(section: dict[str, Any]) -> str:
    explanations = {
        "envelope_required": "该区段需要提供执行信封（Envelope）文件后才能投影；当前不是系统故障。",
        "request_context_required": "报告只在单次请求上下文中生成，不作为持久集合展示。",
    }
    explanation = explanations.get(
        str(section.get("reason")),
        "当前数据源无法生成该区段，请按下方命令提示补充输入或修复来源。",
    )
    return (
        '<div class="boundary-callout" data-search-row '
        f'data-search="{_escape(section.get("message", ""))}">'
        '<div class="boundary-callout__mark" aria-hidden="true">//</div>'
        '<div><strong>边界提示（BOUNDARY）/ 不是持久集合</strong>'
        f'<p>{_escape(explanation)}</p>'
        '<details><summary>查看原始技术说明</summary>'
        f'<p>{_escape(section.get("message"))}</p></details>'
        f'<code>{_escape(section.get("command_hint"))}</code></div>'
        "</div>"
    )


_GRAPH_NODE_W = 200
_GRAPH_NODE_H = 56
_GRAPH_X_GAP = 90
_GRAPH_Y_GAP = 24
_GRAPH_PAD = 20


def _collaboration_graph(plan: dict[str, Any]) -> str:
    """Render one validated plan as a deterministic accessible SVG graph."""
    work_items = plan["work_items"]
    handoffs = plan["handoffs"]
    review_gates = plan["review_gates"]
    by_id = {item["work_item_id"]: item for item in work_items}
    levels: dict[str, int] = {}

    def level(item_id: str) -> int:
        if item_id not in levels:
            known = [dep for dep in by_id[item_id]["depends_on"] if dep in by_id]
            levels[item_id] = 1 + max((level(dep) for dep in known), default=-1)
        return levels[item_id]

    for item in work_items:
        level(item["work_item_id"])

    column_index: dict[str, int] = {}
    positions: dict[str, tuple[int, int]] = {}
    for item in work_items:
        item_level = levels[item["work_item_id"]]
        index = column_index.get(item_level, 0)
        column_index[item_level] = index + 1
        positions[item["work_item_id"]] = (
            _GRAPH_PAD + item_level * (_GRAPH_NODE_W + _GRAPH_X_GAP),
            _GRAPH_PAD + index * (_GRAPH_NODE_H + _GRAPH_Y_GAP),
        )

    max_work_level = max(levels.values(), default=0)
    gate_level = max_work_level + 1
    gate_positions: dict[str, tuple[int, int]] = {}
    for index, gate in enumerate(review_gates):
        gate_positions[gate["gate_id"]] = (
            _GRAPH_PAD + gate_level * (_GRAPH_NODE_W + _GRAPH_X_GAP),
            _GRAPH_PAD + index * (_GRAPH_NODE_H + _GRAPH_Y_GAP),
        )

    column_count = gate_level + 1 if review_gates else max_work_level + 1
    row_count = max(
        [column_index.get(lvl, 0) for lvl in range(max_work_level + 1)]
        + [len(review_gates), 1]
    )
    width = 2 * _GRAPH_PAD + column_count * _GRAPH_NODE_W + (column_count - 1) * _GRAPH_X_GAP
    height = 2 * _GRAPH_PAD + row_count * (_GRAPH_NODE_H + _GRAPH_Y_GAP) - _GRAPH_Y_GAP

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'aria-hidden="true" focusable="false" role="presentation">',
        "<defs>"
        '<marker id="collab-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="var(--cyan)"/></marker>'
        "</defs>",
    ]

    def right_anchor(item_id: str) -> tuple[int, int]:
        x, y = positions[item_id]
        return x + _GRAPH_NODE_W, y + _GRAPH_NODE_H // 2

    def left_anchor(item_id: str) -> tuple[int, int]:
        x, y = positions[item_id]
        return x, y + _GRAPH_NODE_H // 2

    for handoff in handoffs:
        x1, y1 = right_anchor(handoff["from_work_item_id"])
        x2, y2 = left_anchor(handoff["to_work_item_id"])
        label = ", ".join(handoff["artifact_types"])
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            'stroke="var(--cyan)" stroke-width="1.5" marker-end="url(#collab-arrow)"/>'
            f'<text x="{(x1 + x2) // 2}" y="{(y1 + y2) // 2 - 6}" '
            'text-anchor="middle" font-size="10" fill="var(--muted)">'
            f"{_escape(label)}</text>"
        )

    for gate in review_gates:
        gate_x, gate_y = gate_positions[gate["gate_id"]]
        gate_cy = gate_y + _GRAPH_NODE_H // 2
        for after_id in sorted(gate["after_work_item_ids"]):
            if after_id not in positions:
                continue
            x1, y1 = right_anchor(after_id)
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{gate_x}" y2="{gate_cy}" '
                'stroke="var(--amber-soft)" stroke-width="1.5" stroke-dasharray="5 4" '
                'marker-end="url(#collab-arrow)"/>'
            )

    for item in work_items:
        x, y = positions[item["work_item_id"]]
        subtitle = f"{_ui_term(item['role'])} · Agent 插座（Socket）{item['socket_id']}"
        if item["review_required"]:
            subtitle = f"{subtitle} · 需要审阅"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_GRAPH_NODE_W}" height="{_GRAPH_NODE_H}" '
            'rx="4" fill="var(--panel-raised)" stroke="var(--line-hot)"/>'
            f'<text x="{x + 10}" y="{y + 22}" font-size="12" font-weight="700" '
            f'fill="var(--text)">{_escape(item["work_item_id"])}</text>'
            f'<text x="{x + 10}" y="{y + 40}" font-size="10" fill="var(--muted)">'
            f"{_escape(subtitle)}</text>"
        )

    for gate in review_gates:
        gate_x, gate_y = gate_positions[gate["gate_id"]]
        cx = gate_x + _GRAPH_NODE_W // 2
        cy = gate_y + _GRAPH_NODE_H // 2
        points = (
            f"{gate_x},{cy} {cx},{gate_y} "
            f"{gate_x + _GRAPH_NODE_W},{cy} {cx},{gate_y + _GRAPH_NODE_H}"
        )
        parts.append(
            f'<polygon points="{points}" fill="rgba(245,185,66,.08)" '
            'stroke="var(--amber)"/>'
            f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="11" '
            f'font-weight="700" fill="var(--amber)">{_escape(gate["gate_id"])}</text>'
            f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="10" '
            f'fill="var(--muted)">{_escape(_ui_term(gate["review_role"]))}</text>'
        )

    parts.append("</svg>")
    summary = plan["summary"]
    caption = (
        "协作计划图："
        f"{summary['socket_count']} 个 Agent 插座（Socket），"
        f"{summary['work_item_count']} 个工作项，"
        f"{summary['handoff_count']} 次交接，"
        f"{summary['review_gate_count']} 个审阅门"
    )
    return (
        '<figure class="collaboration-graph" role="img" '
        'aria-labelledby="collaboration-graph-caption">'
        f'<figcaption id="collaboration-graph-caption">{_escape(caption)}</figcaption>'
        f"{''.join(parts)}</figure>"
    )


def _collaboration_section_body(section: dict[str, Any]) -> str:
    plan = section.get("plan")
    if section.get("status") != "pass" or plan is None:
        next_action = section.get("next_action") or {}
        source_file = section.get("source", {}).get("plan_file")
        hint = "orchestration collaboration validate --file <path>"
        if isinstance(source_file, str) and source_file:
            hint = f"orchestration collaboration validate --file {source_file}"
        return _boundary_callout(
            {
                "message": next_action.get(
                    "message",
                    "Collaboration plan projection is unavailable.",
                ),
                "command_hint": hint,
            }
        ) + _table(
            caption="协作计划问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="没有发现问题。",
        )
    return "".join(
        [
            _collaboration_graph(plan),
            _table(
                caption="协作 Agent 插座绑定",
                columns=(("socket_id", "Agent 插座（Socket）ID"), ("role", "角色"), ("required_capabilities", "所需能力")),
                rows=plan["socket_bindings"],
                empty_message="没有 Agent 插座绑定。",
            ),
            _table(
                caption="协作路由说明",
                columns=(
                    ("socket_id", "Agent 插座（Socket）ID"),
                    ("role", "角色"),
                    ("selection_basis", "选择依据"),
                    ("matched_capabilities", "匹配能力"),
                    ("declared_availability", "声明可用性"),
                    ("invocation_mode", "调用模式"),
                    ("readiness_evidence", "就绪证据"),
                    ("reason", "原始技术原因"),
                ),
                rows=plan["routing_explanations"],
                empty_message="没有路由说明。",
            ),
            _table(
                caption="协作工作项",
                columns=(
                    ("work_item_id", "工作项 ID"),
                    ("socket_id", "Agent 插座（Socket）ID"),
                    ("role", "角色"),
                    ("depends_on", "依赖工作项"),
                    ("expected_artifact_types", "预期产物"),
                    ("review_required", "需要审阅"),
                    ("status", "状态"),
                ),
                rows=plan["work_items"],
                empty_message="没有工作项。",
            ),
            _table(
                caption="协作交接",
                columns=(("from_work_item_id", "来源工作项"), ("to_work_item_id", "目标工作项"), ("artifact_types", "交接产物")),
                rows=plan["handoffs"],
                empty_message="没有交接。",
            ),
            _table(
                caption="协作审阅门",
                columns=(("gate_id", "审阅门 ID"), ("after_work_item_ids", "位于工作项之后"), ("review_role", "审阅角色"), ("decision_options", "可选决定"), ("status", "状态")),
                rows=plan["review_gates"],
                empty_message="没有审阅门。",
            ),
        ]
    )


def _dispatch_section_body(section: dict[str, Any]) -> str:
    proposal = section.get("proposal")
    if section.get("status") != "pass" or proposal is None:
        return _table(
            caption="派发提案问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="派发提案暂不可用。",
        )
    return _table(
        caption="受控协作派发资格",
        columns=(
            ("work_item_id", "工作项 ID"),
            ("socket_id", "Agent 插座（Socket）ID"),
            ("plan_eligible", "计划合格"),
            ("dispatch_eligible", "可派发"),
            ("execution", "执行状态"),
            ("readiness_evidence", "就绪证据"),
            ("blocked_reasons", "阻止原因"),
        ),
        rows=[proposal],
        empty_message="没有派发提案。",
    )


def _manual_board_section_body(section: dict[str, Any]) -> str:
    board = section.get("board")
    if section.get("status") != "pass" or board is None:
        return _table(
            caption="人工协作看板问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="人工协作看板暂不可用。",
        )
    socket_roles: dict[str, str] = {}
    for lane in board["lanes"]:
        socket_roles.setdefault(lane["socket_id"], lane["role"])
    socket_options = "".join(
        f'<option value="{_escape(socket_id)}" data-role="{_escape(role)}">{_escape(socket_id)}</option>'
        for socket_id, role in socket_roles.items()
    )
    lane_html = []
    editor_rows = []
    for lane in board["lanes"]:
        lane_html.append(
            '<article class="work-lane" '
            f'data-search="{_escape(json.dumps(lane, sort_keys=True))}">'
            '<div class="work-lane__head">'
            f'<strong>{_escape(lane["work_item_id"])}</strong>'
            f'<span class="pill pill--neutral">{_escape(_ui_term(lane["status"]))}</span>'
            '</div>'
            f'<p class="work-lane__socket">Agent 插座（Socket）ID：{_escape(lane["socket_id"])} · 角色：{_escape(_ui_term(lane["role"]))}</p>'
            f'<p>依赖工作项：<code>{_escape(lane["depends_on"] or ["无"])}</code></p>'
            f'<p>预期产物：<code>{_escape(lane["expected_artifact_types"])}</code></p>'
            f'<p>演示产物（fixture）：<code>{_escape(lane["artifact_types"] or ["无"])}</code></p>'
            f'<p>审阅状态：<strong>{_escape(_ui_term(lane["review_state"]))}</strong></p>'
            '<div class="simulation-mark">仅为模拟展示 · 未启动任何 Agent 对话</div>'
            '</article>'
        )
        selected_options = socket_options.replace(
            f'value="{_escape(lane["socket_id"])}"',
            f'value="{_escape(lane["socket_id"])}" selected',
            1,
        )
        editor_rows.append(
            '<tr class="draft-work-item">'
            f'<td><input class="draft-id" aria-label="工作项 ID" value="{_escape(lane["work_item_id"])}"></td>'
            f'<td><select class="draft-socket" aria-label="Agent 插座（Socket）ID">{selected_options}</select></td>'
            f'<td><input class="draft-depends" aria-label="依赖工作项，多个值用逗号分隔" value="{html.escape(",".join(lane["depends_on"]), quote=True)}"></td>'
            f'<td><input class="draft-artifacts" aria-label="预期产物，多个值用逗号分隔" value="{html.escape(",".join(lane["expected_artifact_types"]), quote=True)}"></td>'
            f'<td><input class="draft-review" aria-label="是否需要审阅" type="checkbox" {"checked" if lane["review_state"] != "not_required" else ""}></td>'
            '<td><button class="draft-remove" type="button" title="从浏览器内存草稿中删除">删除</button></td>'
            '</tr>'
        )
    timeline_html = []
    for event in board["timeline"]:
        timeline_html.append(
            '<li class="board-event" '
            f'data-search="{_escape(json.dumps(event, sort_keys=True))}">'
            f'<span class="board-event__sequence">{event["sequence"]:02d}</span>'
            '<div>'
            f'<strong>{_escape(_ui_term(event["event_type"]))}</strong>'
            f'<p>工作项 {_escape(event["work_item_id"])}：{_escape(_ui_term(event["event_type"], annotate=False))}</p>'
            f'<code>产物：{_escape(event["artifact_types"] or ["无"])}</code>'
            '</div></li>'
        )
    action_html = []
    for action in board["operator_actions"]:
        action_html.append(
            '<button type="button" class="board-action" disabled title="仅展示未来工作流；当前没有执行权限">'
            f'{_escape(_ui_term(action["action"]))}<span>仅模拟</span></button>'
        )
    summary = board["summary"]
    return "".join(
        [
            '<div class="manual-board-banner">'
            '<div><span class="eyebrow">操作者人工编排</span>'
            '<h3>人工计划拆分</h3>'
            f'<p>父任务：{_escape(board["parent_task_ref"])} · 看板状态：{_escape(_ui_term(board["board_state"]))}</p></div>'
            '<div class="manual-board-stats">'
            f'<strong>{summary["lane_count"]}</strong><span>工作项</span>'
            f'<strong>{summary["timeline_event_count"]}</strong><span>时间线事件</span>'
            f'<strong>{summary["simulated_complete_count"]}</strong><span>模拟完成</span>'
            '</div></div>',
            '<div class="work-lanes">', "".join(lane_html), '</div>',
            '<div class="board-lower"><div><h3>交接与产物时间线</h3><ol class="board-timeline">',
            "".join(timeline_html),
            '</ol></div><div><h3>操作者控制项</h3>'
            '<p class="board-note">这些按钮只说明未来工作流。当前是演示样例（fixture），全部禁用且没有执行权限。</p>'
            '<div class="board-actions">', "".join(action_html), '</div></div></div>',
            '<section class="draft-editor" id="manual-plan-editor">'
            '<div class="draft-editor__head"><div><span class="eyebrow">仅浏览器内存</span><h3>人工计划草稿编辑器</h3>'
            '<p>修改内容不会写入项目文件、不会访问网络、不会调用 Agent；刷新页面后草稿消失。</p></div>'
            '<span id="draft-state" class="pill pill--neutral" data-state="editing">编辑中 · 不可派发</span></div>'
            '<div class="draft-task-fields"><div><label class="draft-task-label" for="draft-task-title">任务标题</label>'
            '<input id="draft-task-title" value="未命名人工计划"></div><div><label class="draft-task-label" for="draft-parent-task">父任务引用</label>'
            f'<input id="draft-parent-task" value="{_escape(board["parent_task_ref"])}"></div></div>'
            '<p class="board-note">工作角色由当前 Agent 插座绑定决定；候选必须先校验并人工确认。待人工确认 · 不可派发。</p>'
            '<div class="table-shell"><table><caption>人工计划草稿工作项</caption><thead><tr>'
            '<th>工作项 ID</th><th>Agent 插座（Socket）ID</th><th>依赖工作项</th><th>预期产物</th><th>需要审阅</th><th>操作</th>'
            '</tr></thead><tbody id="draft-work-items">', "".join(editor_rows), '</tbody></table></div>'
            f'<template id="draft-work-item-template"><tr class="draft-work-item"><td><input class="draft-id" aria-label="工作项 ID"></td><td><select class="draft-socket" aria-label="Agent 插座（Socket）ID">{socket_options}</select></td><td><input class="draft-depends" aria-label="依赖工作项，多个值用逗号分隔"></td><td><input class="draft-artifacts" aria-label="预期产物，多个值用逗号分隔" value="analysis"></td><td><input class="draft-review" aria-label="是否需要审阅" type="checkbox"></td><td><button class="draft-remove" type="button" title="从浏览器内存草稿中删除">删除</button></td></tr></template>'
            '<div class="draft-controls"><button id="draft-add" type="button">添加工作项</button><button id="draft-validate" type="button">校验候选计划</button><button id="draft-confirm" type="button" disabled>人工确认候选</button><span>校验和确认都不会授予派发权</span></div>'
            '<dl class="draft-guardrails"><div><dt>派发资格</dt><dd><code>dispatch_eligible=false</code></dd></div><div><dt>执行状态</dt><dd><code>execution=not_executed</code></dd></div><div><dt>确认边界</dt><dd>只有人工确认后才能复制或下载</dd></div></dl>'
            '<div id="draft-preview-panel" class="draft-preview" hidden>'
            '<div class="draft-preview__head"><div><h3>collaboration plan 候选预览</h3><p id="draft-validation-summary">尚未校验。</p></div>'
            '<div class="draft-filename-field"><label for="draft-filename">导出文件名</label><input id="draft-filename" readonly value="collaboration-plan-candidate.json"></div></div>'
            '<ul id="draft-validation-results" class="draft-validation-results" aria-live="polite"></ul>'
            '<pre id="draft-json"></pre>'
            '<div class="draft-export-controls"><button id="draft-copy" type="button" disabled>复制候选 JSON</button><button id="draft-download" type="button" disabled>下载候选 JSON</button><span id="draft-export-feedback" aria-live="polite">需先校验并人工确认。</span></div>'
            '</div></section>',
        ]
    )


def _collaboration_run_section_body(section: dict[str, Any]) -> str:
    run = section.get("run")
    if section.get("status") != "pass" or run is None:
        return _table(
            caption="协作运行状态问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="协作运行状态暂不可用。",
        )

    attempts_by_id = {
        attempt["attempt_id"]: attempt for attempt in run.get("attempts", [])
    }
    current_attempts = []
    for work_item_id, attempt_id in sorted(run.get("current_attempts", {}).items()):
        attempt = dict(attempts_by_id.get(attempt_id, {}))
        attempt["current_work_item_id"] = work_item_id
        current_attempts.append(attempt)

    actions = "".join(
        '<button type="button" class="run-action" disabled '
        'title="仅模拟展示；当前没有执行权限">'
        f'{_escape(_ui_term(action.get("action")))}'
        '<span>仅模拟 · 无执行权限</span></button>'
        for action in run.get("operator_actions", [])
    )
    summary = run.get("summary", {})
    return "".join(
        [
            '<div class="run-state-banner">'
            '<div><span class="eyebrow">只读模拟投影</span>'
            '<h3>模拟协作运行</h3>'
            f'<p>运行 ID：{_escape(run.get("run_id"))} · 父任务：{_escape(run.get("parent_task_ref"))} · 状态：{_escape(_ui_term(run.get("status")))}</p></div>'
            '<div class="run-state-stats">'
            f'<strong>{_escape(summary.get("attempt_count", 0))}</strong><span>尝试</span>'
            f'<strong>{_escape(summary.get("retry_count", 0))}</strong><span>重试</span>'
            f'<strong>{_escape(summary.get("blocked_recovery_count", 0))}</strong><span>阻塞恢复次数</span>'
            '</div></div>',
            '<dl class="run-boundary">'
            '<div><dt>派发资格</dt><dd><code>dispatch_eligible=false</code></dd></div>'
            '<div><dt>执行状态</dt><dd><code>execution=not_executed</code></dd></div>'
            '<div><dt>安全边界</dt><dd>不启动 Agent、不探测就绪状态、不写入账本</dd></div>'
            '</dl>',
            _table(
                caption="当前尝试",
                columns=(("current_work_item_id", "工作项 ID"), ("attempt_id", "当前尝试 ID"), ("attempt_number", "尝试序号"), ("status", "状态"), ("artifact_ids", "产物 ID")),
                rows=current_attempts,
                empty_message="没有当前尝试。",
            ),
            _table(
                caption="工作项尝试历史",
                columns=(("work_item_id", "工作项 ID"), ("attempt_id", "尝试 ID"), ("attempt_number", "尝试序号"), ("status", "状态"), ("review_ids", "审阅 ID"), ("artifact_ids", "产物 ID")),
                rows=run.get("attempts", []),
                empty_message="没有工作项尝试历史。",
            ),
            _table(
                caption="审阅决定",
                columns=(("review_id", "审阅 ID"), ("gate_id", "审阅门 ID"), ("work_item_id", "工作项 ID"), ("attempt_id", "尝试 ID"), ("status", "决定"), ("artifact_ids", "审阅产物")),
                rows=run.get("reviews", []),
                empty_message="没有审阅决定。",
            ),
            _table(
                caption="交接状态",
                columns=(("handoff_id", "交接 ID"), ("from_work_item_id", "来源工作项"), ("to_work_item_id", "目标工作项"), ("from_attempt_id", "来源尝试"), ("to_attempt_id", "目标尝试"), ("status", "状态"), ("artifact_ids", "交接产物")),
                rows=run.get("handoffs", []),
                empty_message="没有交接状态。",
            ),
            _table(
                caption="产物回收",
                columns=(("artifact_id", "产物 ID"), ("work_item_id", "工作项 ID"), ("attempt_id", "尝试 ID"), ("artifact_type", "产物类型"), ("status", "状态"), ("content_hash", "内容哈希")),
                rows=run.get("artifacts", []),
                empty_message="没有产物回收记录。",
            ),
            _table(
                caption="运行事件时间线",
                columns=(("sequence", "序号"), ("event_type", "事件类型"), ("entity_type", "实体类型"), ("entity_id", "实体 ID"), ("from_state", "原状态"), ("to_state", "新状态"), ("label", "事件说明")),
                rows=run.get("events", []),
                empty_message="没有运行事件。",
            ),
            '<div class="run-actions"><div><h3>操作者控制项</h3>'
            '<p>按钮只表达未来运行控制语义；本阶段全部禁用。</p></div>'
            f'<div class="run-actions__buttons">{actions}</div></div>',
        ]
    )


def _collaboration_action_section_body(section: dict[str, Any]) -> str:
    actions = section.get("actions")
    if section.get("status") != "pass" or actions is None:
        return _table(
            caption="操作者操作资格问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="操作者操作资格暂不可用。",
        )

    candidates = []
    for item in actions:
        candidate = item.get("command_candidate")
        if candidate is not None:
            candidates.append(
                {
                    "action": item["action"],
                    "candidate_id": candidate["candidate_id"],
                    "idempotency_key": candidate["idempotency_key"],
                    "approval_id": candidate["approval_id"],
                    "execution": candidate["execution"],
                }
            )
    controls = "".join(
        '<button type="button" class="action-eligibility-control" disabled '
        'title="业务资格不等于执行授权；当前按钮不可执行">'
        f'{_escape(_ui_term(item["action"]))}'
        f'<span>action_eligible={str(bool(item["action_eligible"])).lower()}</span>'
        '<span>资格不等于执行授权</span></button>'
        for item in actions
    )
    summary = section.get("summary", {})
    run = section.get("run", {})
    return "".join(
        [
            '<div class="action-eligibility-banner">'
            '<div><span class="eyebrow">fixture 审批证据 / 只读投影</span>'
            '<h3>操作者操作资格</h3>'
            f'<p>运行 ID：{_escape(run.get("run_id"))} · 事件数：{_escape(run.get("event_count"))}</p></div>'
            '<div class="action-eligibility-stats">'
            f'<strong>{_escape(summary.get("action_count", 0))}</strong><span>操作请求</span>'
            f'<strong>{_escape(summary.get("eligible_count", 0))}</strong><span>业务合格</span>'
            f'<strong>{_escape(summary.get("blocked_count", 0))}</strong><span>已阻止</span>'
            '</div></div>',
            '<dl class="action-eligibility-boundary">'
            '<div><dt>执行授权</dt><dd><code>execution_authorized=false</code></dd></div>'
            '<div><dt>派发资格</dt><dd><code>dispatch_eligible=false</code></dd></div>'
            '<div><dt>执行状态</dt><dd><code>execution=not_executed</code></dd></div>'
            '</dl>',
            _table(
                caption="操作资格检查点",
                columns=(("action", "操作"), ("target_type", "目标类型"), ("target_id", "目标 ID"), ("as_of_sequence", "事件检查点"), ("expected_state", "期望状态"), ("current_state", "检查点状态"), ("action_eligible", "业务资格"), ("blocked_reasons", "阻止原因")),
                rows=actions,
                empty_message="没有操作资格请求。",
            ),
            _table(
                caption="审批绑定",
                columns=(("action", "操作"), ("approval_id", "审批 ID"), ("approval_status", "审批状态"), ("target_id", "绑定目标"), ("as_of_sequence", "绑定检查点"), ("expected_state", "绑定状态")),
                rows=actions,
                empty_message="没有审批绑定。",
            ),
            _table(
                caption="幂等命令候选",
                columns=(("action", "操作"), ("candidate_id", "候选 ID"), ("idempotency_key", "幂等键"), ("approval_id", "审批 ID"), ("execution", "执行状态")),
                rows=candidates,
                empty_message="没有业务合格的命令候选。",
            ),
            '<div class="action-eligibility-actions"><div><h3>只读操作控件</h3>'
            '<p>即使业务资格为 true，也没有执行授权；所有控件固定禁用。</p></div>'
            f'<div class="action-eligibility-actions__buttons">{controls}</div></div>',
        ]
    )


def _collaboration_inbox_section_body(section: dict[str, Any]) -> str:
    actions = section.get("actions")
    if section.get("status") != "pass" or actions is None:
        return _table(
            caption="当前操作者待办问题",
            columns=(("rule_id", "规则 ID"), ("severity", "严重程度"), ("message", "原始技术详情")),
            rows=section.get("findings", []),
            empty_message="当前操作者待办暂不可用。",
        )

    current_run = section.get("current_run", {})
    summary = section.get("summary", {})
    pending = section.get("pending_approvals", [])
    candidates = []
    for item in actions:
        candidate = item.get("command_candidate")
        if candidate is not None:
            candidates.append(
                {
                    "action": item["action"],
                    "candidate_id": candidate["candidate_id"],
                    "idempotency_key": candidate["idempotency_key"],
                    "approval_id": candidate["approval_id"],
                    "execution": candidate["execution"],
                }
            )
    controls = "".join(
        '<button type="button" class="operator-inbox-control" disabled '
        'title="当前待办不是执行授权；当前按钮不可执行">'
        f'{_escape(_ui_term(item["action"]))}'
        f'<span>action_eligible={str(bool(item["action_eligible"])).lower()}</span>'
        '<span>当前待办不是执行授权</span></button>'
        for item in actions
    )
    return "".join(
        [
            '<div class="operator-inbox-banner">'
            '<div><span class="eyebrow">current-state fixture / 只读待办</span>'
            '<h3>当前操作者待办</h3>'
            f'<p>运行 ID：{_escape(current_run.get("run_id"))} · 当前运行状态：{_escape(_ui_term(current_run.get("status")))}</p></div>'
            '<div class="operator-inbox-stats">'
            f'<strong>{_escape(summary.get("pending_approval_count", 0))}</strong><span>待处理审批</span>'
            f'<strong>{_escape(summary.get("eligible_count", 0))}</strong><span>当前合格</span>'
            f'<strong>{_escape(summary.get("blocked_count", 0))}</strong><span>当前阻止</span>'
            '</div></div>',
            '<dl class="operator-inbox-boundary">'
            '<div><dt>执行授权</dt><dd><code>execution_authorized=false</code></dd></div>'
            '<div><dt>派发资格</dt><dd><code>dispatch_eligible=false</code></dd></div>'
            '<div><dt>执行状态</dt><dd><code>execution=not_executed</code></dd></div>'
            '</dl>',
            _table(
                caption="当前运行状态",
                columns=(("run_id", "运行 ID"), ("status", "状态"), ("current_attempts", "当前尝试"), ("current_review_ids", "当前审阅"), ("current_handoff_ids", "当前交接"), ("event_count", "事件数")),
                rows=[current_run],
                empty_message="没有当前运行状态。",
            ),
            _table(
                caption="待处理审批",
                columns=(("approval_id", "审批 ID"), ("status", "状态"), ("action", "操作"), ("target_type", "目标类型"), ("target_id", "目标 ID"), ("expected_state", "期望状态")),
                rows=pending,
                empty_message="当前没有待处理审批。",
            ),
            _table(
                caption="当前操作资格",
                columns=(("action", "操作"), ("target_type", "目标类型"), ("target_id", "目标 ID"), ("expected_state", "期望状态"), ("current_state", "当前状态"), ("approval_status", "审批状态"), ("action_eligible", "业务资格"), ("blocked_reasons", "阻止原因")),
                rows=actions,
                empty_message="没有当前操作请求。",
            ),
            _table(
                caption="当前幂等命令候选",
                columns=(("action", "操作"), ("candidate_id", "候选 ID"), ("idempotency_key", "幂等键"), ("approval_id", "审批 ID"), ("execution", "执行状态")),
                rows=candidates,
                empty_message="没有当前合格的命令候选。",
            ),
            '<div class="operator-inbox-actions"><div><h3>当前待办控件</h3>'
            '<p>当前待办、审批状态和业务资格都不会授予执行授权；所有控件固定禁用。</p></div>'
            f'<div class="operator-inbox-actions__buttons">{controls}</div></div>',
        ]
    )


_CSS = r"""
:root {
  color-scheme: dark;
  --ink: #07100f;
  --panel: #0b1715;
  --panel-raised: #10201d;
  --line: #29433d;
  --line-hot: #4c756b;
  --text: #e7e2cf;
  --muted: #8da49d;
  --amber: #f5b942;
  --amber-soft: #bd8730;
  --cyan: #62d6c7;
  --red: #ff756d;
  --green: #82d173;
  --shadow: rgba(0, 0, 0, .42);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  background:
    linear-gradient(rgba(98, 214, 199, .025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(98, 214, 199, .025) 1px, transparent 1px),
    radial-gradient(circle at 82% 0%, rgba(245, 185, 66, .09), transparent 34rem),
    var(--ink);
  background-size: 28px 28px, 28px 28px, auto, auto;
  color: var(--text);
  font-family: "Cascadia Code", "IBM Plex Mono", Consolas, monospace;
  line-height: 1.55;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(0deg, transparent 0 3px, rgba(255,255,255,.012) 3px 4px);
  mix-blend-mode: soft-light;
}
a { color: inherit; }
.skip-link { position: fixed; left: 1rem; top: -5rem; z-index: 20; padding: .7rem 1rem; background: var(--amber); color: var(--ink); }
.skip-link:focus { top: 1rem; }
.shell { width: min(1540px, calc(100% - 2rem)); margin: 0 auto; padding: 1rem 0 5rem; }
.masthead { position: relative; border: 1px solid var(--line); background: linear-gradient(135deg, rgba(16,32,29,.98), rgba(7,16,15,.94)); box-shadow: 0 28px 70px var(--shadow); overflow: hidden; }

.run-state-banner { display: flex; justify-content: space-between; gap: 2rem; align-items: end; margin: 1rem 0; padding: 1.2rem; border: 1px solid var(--line-hot); background: linear-gradient(120deg, rgba(98,214,199,.08), rgba(245,185,66,.04)); }
.run-state-banner h3, .run-actions h3 { margin: .25rem 0; }
.run-state-banner p, .run-actions p { margin: .35rem 0 0; color: var(--muted); }
.run-state-stats { display: grid; grid-template-columns: repeat(3, minmax(5rem, 1fr)); gap: .65rem; text-align: right; }
.run-state-stats strong { display: block; color: var(--amber); font-size: 1.7rem; }
.run-state-stats span { color: var(--muted); font-size: .75rem; }
.run-boundary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0; }
.run-boundary div { padding: .8rem; border: 1px solid var(--line); background: var(--panel); }
.run-boundary dt { color: var(--muted); font-size: .78rem; }
.run-boundary dd { margin: .35rem 0 0; }
.run-actions { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin: 1rem 0; padding: 1rem; border: 1px solid var(--line); background: var(--panel-raised); }
.run-actions__buttons { display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; }
.run-action { color: var(--muted); border: 1px solid var(--line); background: var(--ink); padding: .55rem .7rem; cursor: not-allowed; }
.run-action span { display: block; margin-top: .2rem; color: var(--amber-soft); font-size: .66rem; }
@media (max-width: 800px) { .run-state-banner, .run-actions { align-items: stretch; flex-direction: column; } .run-state-stats, .run-boundary { grid-template-columns: 1fr; text-align: left; } }

.action-eligibility-banner { display: flex; justify-content: space-between; gap: 2rem; align-items: end; margin: 1rem 0; padding: 1.2rem; border: 1px solid var(--amber-soft); background: linear-gradient(120deg, rgba(245,185,66,.08), rgba(98,214,199,.04)); }
.action-eligibility-banner h3, .action-eligibility-actions h3 { margin: .25rem 0; }
.action-eligibility-banner p, .action-eligibility-actions p { margin: .35rem 0 0; color: var(--muted); }
.action-eligibility-stats { display: grid; grid-template-columns: repeat(3, minmax(5rem, 1fr)); gap: .65rem; text-align: right; }
.action-eligibility-stats strong { display: block; color: var(--cyan); font-size: 1.7rem; }
.action-eligibility-stats span { color: var(--muted); font-size: .75rem; }
.action-eligibility-boundary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0; }
.action-eligibility-boundary div { padding: .8rem; border: 1px solid var(--line); background: var(--panel); }
.action-eligibility-boundary dt { color: var(--muted); font-size: .78rem; }
.action-eligibility-boundary dd { margin: .35rem 0 0; }
.action-eligibility-actions { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin: 1rem 0; padding: 1rem; border: 1px solid var(--line); background: var(--panel-raised); }
.action-eligibility-actions__buttons { display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; }
.action-eligibility-control { color: var(--muted); border: 1px solid var(--line); background: var(--ink); padding: .55rem .7rem; cursor: not-allowed; }
.action-eligibility-control span { display: block; margin-top: .2rem; color: var(--amber-soft); font-size: .66rem; }
@media (max-width: 800px) { .action-eligibility-banner, .action-eligibility-actions { align-items: stretch; flex-direction: column; } .action-eligibility-stats, .action-eligibility-boundary { grid-template-columns: 1fr; text-align: left; } }

.operator-inbox-banner { display: flex; justify-content: space-between; gap: 2rem; align-items: end; margin: 1rem 0; padding: 1.2rem; border: 1px solid var(--cyan); background: linear-gradient(120deg, rgba(98,214,199,.09), rgba(245,185,66,.035)); }
.operator-inbox-banner h3, .operator-inbox-actions h3 { margin: .25rem 0; }
.operator-inbox-banner p, .operator-inbox-actions p { margin: .35rem 0 0; color: var(--muted); }
.operator-inbox-stats { display: grid; grid-template-columns: repeat(3, minmax(5rem, 1fr)); gap: .65rem; text-align: right; }
.operator-inbox-stats strong { display: block; color: var(--cyan); font-size: 1.7rem; }
.operator-inbox-stats span { color: var(--muted); font-size: .75rem; }
.operator-inbox-boundary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0; }
.operator-inbox-boundary div { padding: .8rem; border: 1px solid var(--line); background: var(--panel); }
.operator-inbox-boundary dt { color: var(--muted); font-size: .78rem; }
.operator-inbox-boundary dd { margin: .35rem 0 0; }
.operator-inbox-actions { display: flex; justify-content: space-between; gap: 1rem; align-items: center; margin: 1rem 0; padding: 1rem; border: 1px solid var(--line); background: var(--panel-raised); }
.operator-inbox-actions__buttons { display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; }
.operator-inbox-control { color: var(--muted); border: 1px solid var(--line); background: var(--ink); padding: .55rem .7rem; cursor: not-allowed; }
.operator-inbox-control span { display: block; margin-top: .2rem; color: var(--amber-soft); font-size: .66rem; }
@media (max-width: 800px) { .operator-inbox-banner, .operator-inbox-actions { align-items: stretch; flex-direction: column; } .operator-inbox-stats, .operator-inbox-boundary { grid-template-columns: 1fr; text-align: left; } }
.masthead::after { content: "控制 / 81"; position: absolute; right: -1rem; bottom: -2.7rem; color: rgba(245,185,66,.055); font: 900 clamp(5rem, 14vw, 12rem)/1 "Bahnschrift Condensed", Impact, sans-serif; letter-spacing: -.06em; }
.topline { display: flex; justify-content: space-between; gap: 1rem; padding: .8rem 1rem; border-bottom: 1px solid var(--line); color: var(--muted); font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
.hero { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(18rem, .65fr); gap: 2rem; padding: clamp(1.5rem, 5vw, 4.5rem); }
.eyebrow { color: var(--amber); font-size: .75rem; letter-spacing: .2em; text-transform: uppercase; }
h1 { max-width: none; margin: .5rem 0 1rem; font: 900 clamp(3rem, 6vw, 6rem)/.92 "Bahnschrift Condensed", Impact, sans-serif; letter-spacing: 0; text-transform: uppercase; }
.hero-copy { max-width: 68ch; color: var(--muted); }
.hero-meta { align-self: end; border-left: 3px solid var(--amber); padding-left: 1rem; }
.hero-meta code { display: block; overflow-wrap: anywhere; color: var(--cyan); font-size: .72rem; }
.summary-grid { display: grid; grid-template-columns: repeat(6, minmax(8.5rem, 1fr)); border-top: 1px solid var(--line); }
.metric { min-height: 8rem; padding: 1rem; border-right: 1px solid var(--line); background: rgba(7,16,15,.48); }
.metric:last-child { border-right: 0; }
.metric__value { display: block; font: 800 2.4rem/1 "Bahnschrift", sans-serif; color: var(--amber); }
.metric__label { display: block; margin-top: .7rem; color: var(--muted); font-size: .68rem; letter-spacing: .1em; text-transform: uppercase; }
.toolbar { position: sticky; top: 0; z-index: 10; display: grid; grid-template-columns: 1fr auto; gap: 1rem; margin: 1rem 0; padding: .75rem; border: 1px solid var(--line); background: rgba(7,16,15,.94); backdrop-filter: blur(16px); }
.search { display: flex; align-items: center; gap: .75rem; }
.search label { color: var(--amber); font-size: .72rem; letter-spacing: .12em; }
.search input { width: min(42rem, 100%); padding: .7rem .9rem; border: 1px solid var(--line-hot); background: #07100f; color: var(--text); font: inherit; }
.search input:focus-visible, a:focus-visible { outline: 2px solid var(--amber); outline-offset: 3px; }
.nav { display: flex; align-items: center; gap: .25rem; overflow-x: auto; }
.nav a { padding: .55rem .7rem; color: var(--muted); font-size: .67rem; text-decoration: none; text-transform: uppercase; }
.nav a:hover { color: var(--amber); background: var(--panel-raised); }
.panel-section { scroll-margin-top: 6rem; margin-top: 1rem; border: 1px solid var(--line); background: rgba(11,23,21,.88); box-shadow: 0 18px 45px rgba(0,0,0,.2); }
.section-heading { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 1rem; padding: 1rem; border-bottom: 1px solid var(--line); }
.section-index { color: var(--amber); font-size: .72rem; }
h2 { margin: 0; font: 800 1.15rem/1.1 "Bahnschrift", sans-serif; letter-spacing: .08em; text-transform: uppercase; }
.section-heading p { margin: .3rem 0 0; color: var(--muted); font-size: .68rem; }
.status { display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .55rem; border: 1px solid var(--line); color: var(--muted); font-size: .65rem; text-transform: uppercase; }
.status__dot { width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; box-shadow: 0 0 12px currentColor; }
.status--pass { color: var(--green); }
.status--unavailable { color: var(--muted); }
.status--error, .status--validation_failed, .status--blocked { color: var(--red); }
.status--needs_input { color: var(--amber); }
.table-shell { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .76rem; }
caption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
th, td { padding: .75rem 1rem; border-bottom: 1px solid rgba(41,67,61,.72); text-align: left; vertical-align: top; }
th { color: var(--amber); background: rgba(7,16,15,.72); font-size: .63rem; letter-spacing: .1em; text-transform: uppercase; }
tbody tr { transition: background .15s ease, color .15s ease; }
tbody tr:hover { background: rgba(98,214,199,.05); color: #fff8dc; }
.empty-row td { color: var(--muted); text-align: center; }
.boundary-callout { display: grid; grid-template-columns: auto 1fr; gap: 1rem; margin: 1rem; padding: 1.2rem; border: 1px dashed var(--amber-soft); background: rgba(245,185,66,.045); }
.boundary-callout__mark { color: var(--amber); font-size: 1.8rem; font-weight: 900; }
.boundary-callout strong { color: var(--amber); font-size: .72rem; letter-spacing: .12em; }
.boundary-callout p { color: var(--muted); }
.boundary-callout code { color: var(--cyan); overflow-wrap: anywhere; }
.findings { margin-top: 1rem; padding: 1rem; border: 1px solid rgba(255,117,109,.45); background: rgba(255,117,109,.05); }
.findings h2 { color: var(--red); }
.findings li { margin-top: .6rem; color: var(--muted); }
.collaboration-graph { margin: 1rem; padding: 1rem; border: 1px solid var(--line); background: rgba(7,16,15,.55); overflow-x: auto; }
.collaboration-graph figcaption { margin-bottom: .75rem; color: var(--amber); font-size: .68rem; letter-spacing: .1em; text-transform: uppercase; }
.footer { display: grid; grid-template-columns: 1fr auto; gap: 1rem; margin-top: 1rem; padding: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .68rem; }
.manual-board-banner { display: flex; justify-content: space-between; gap: 1.5rem; align-items: end; padding: 1rem; border: 1px solid var(--line-hot); background: var(--panel-raised); }
.manual-board-banner h3, .board-lower h3 { margin: .25rem 0 .4rem; font-size: 1rem; }
.manual-board-banner p, .work-lane p, .board-event p, .board-note { margin: .25rem 0; color: var(--muted); }
.manual-board-stats { display: grid; grid-template-columns: repeat(3, auto); gap: .25rem 1rem; text-align: right; }
.manual-board-stats strong { font-size: 1.35rem; color: var(--cyan); }
.manual-board-stats span { grid-row: 2; color: var(--muted); font-size: .62rem; text-transform: uppercase; }
.work-lanes { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: .75rem; margin: .85rem 0; }
.work-lane { min-width: 0; padding: .85rem; border: 1px solid var(--line); background: var(--panel-raised); }
.work-lane__head { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.work-lane__socket { color: var(--cyan) !important; }
.work-lane code, .board-event code { overflow-wrap: anywhere; }
.simulation-mark { margin-top: .75rem; padding-top: .55rem; border-top: 1px solid var(--line); color: var(--amber); font-size: .62rem; font-weight: 700; }
.board-lower { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(230px, .8fr); gap: 1rem; }
.board-timeline { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--line); }
.board-event { display: grid; grid-template-columns: 2.4rem 1fr; gap: .6rem; padding: .65rem 0; border-bottom: 1px solid var(--line); }
.board-event__sequence { color: var(--cyan); font-family: var(--mono); }
.board-actions { display: grid; gap: .5rem; }
.board-action { display: flex; justify-content: space-between; gap: .75rem; padding: .65rem; border: 1px solid var(--line); border-radius: 4px; background: var(--panel-raised); color: var(--muted); text-align: left; }
.board-action span { color: var(--amber); font-family: var(--mono); font-size: .62rem; text-transform: uppercase; }
.draft-editor { margin-top: 1rem; padding: 1rem; border-top: 1px solid var(--line-hot); background: rgba(7,16,15,.38); }
.draft-editor__head { display: flex; align-items: start; justify-content: space-between; gap: 1rem; }
.draft-editor__head h3 { margin: .25rem 0; }
.draft-editor__head p { color: var(--muted); }
.draft-task-fields { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.draft-task-label { display: block; margin: .75rem 0 .35rem; color: var(--amber); }
.draft-editor input, .draft-editor select { width: 100%; min-width: 8rem; padding: .55rem; border: 1px solid var(--line-hot); background: var(--ink); color: var(--text); font: inherit; }
.draft-editor input[type="checkbox"] { min-width: auto; width: 1rem; }
.draft-editor button { padding: .55rem .75rem; border: 1px solid var(--line-hot); border-radius: 4px; background: var(--panel-raised); color: var(--text); cursor: pointer; }
.draft-editor button:hover { border-color: var(--amber); color: var(--amber); }
.draft-editor button:disabled { cursor: not-allowed; opacity: .45; border-color: var(--line); color: var(--muted); }
.pill { display: inline-flex; align-items: center; padding: .3rem .55rem; border: 1px solid var(--line-hot); border-radius: 999px; color: var(--muted); font-size: .64rem; white-space: nowrap; }
.pill--pass { border-color: var(--green); color: var(--green); }
.draft-controls { display: flex; align-items: center; flex-wrap: wrap; gap: .6rem; margin-top: .8rem; }
.draft-controls span { color: var(--amber); font-size: .68rem; }
.draft-guardrails { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .6rem; margin: .8rem 0 0; }
.draft-guardrails div { padding: .65rem; border: 1px solid var(--line); background: var(--panel-raised); }
.draft-guardrails dt { color: var(--muted); font-size: .62rem; }
.draft-guardrails dd { margin: .25rem 0 0; color: var(--amber); overflow-wrap: anywhere; }
.draft-preview { margin-top: 1rem; padding: 1rem; border: 1px solid var(--amber-soft); }
.draft-preview__head { display: grid; grid-template-columns: 1fr minmax(16rem, .65fr); gap: 1rem; align-items: end; }
.draft-preview__head h3, .draft-preview__head p { margin: 0 0 .35rem; }
.draft-filename-field label { display: block; margin-bottom: .35rem; color: var(--amber); }
.draft-validation-results { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; margin: 1rem 0; padding: 0; list-style: none; }
.draft-check { padding: .65rem; border: 1px solid var(--line); color: var(--muted); }
.draft-check strong { color: var(--green); }
.draft-check--error { border-color: var(--red); }
.draft-check--error strong { color: var(--red); }
.draft-check ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.draft-preview pre { max-height: 30rem; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--cyan); }
.draft-preview--error { border-color: var(--red); }
.draft-export-controls { display: flex; align-items: center; flex-wrap: wrap; gap: .6rem; }
.draft-export-controls span { color: var(--muted); font-size: .68rem; }
.is-filtered-out { display: none !important; }
@media (max-width: 1050px) { .summary-grid { grid-template-columns: repeat(3, 1fr); } .hero { grid-template-columns: 1fr; } .toolbar { grid-template-columns: 1fr; } .board-lower { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .shell { width: min(100% - 1rem, 1540px); } .summary-grid { grid-template-columns: repeat(2, 1fr); } .hero { padding: 1.5rem; } h1 { font-size: 3.2rem; } .section-heading { grid-template-columns: auto 1fr; } .section-heading .status { grid-column: 2; justify-self: start; } th, td { padding: .65rem; } .manual-board-banner { align-items: stretch; flex-direction: column; } .manual-board-stats { text-align: left; } .draft-task-fields, .draft-preview__head, .draft-guardrails, .draft-validation-results { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; } }
"""


_JS = r"""
(() => {
  const input = document.querySelector('#panel-search');
  const rows = Array.from(document.querySelectorAll('[data-search-row]'));
  const counter = document.querySelector('#filter-count');
  const apply = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const haystack = (row.dataset.search || row.textContent || '').toLocaleLowerCase();
      const matched = !query || haystack.includes(query);
      row.classList.toggle('is-filtered-out', !matched);
      if (matched) visible += 1;
    });
    counter.textContent = `${visible}/${rows.length} 可见`;
  };
  input.addEventListener('input', apply);
  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && document.activeElement !== input) {
      event.preventDefault();
      input.focus();
    }
  });
  apply();

  const editor = document.querySelector('#manual-plan-editor');
  if (!editor) return;
  const body = editor.querySelector('#draft-work-items');
  const template = editor.querySelector('#draft-work-item-template');
  const previewPanel = editor.querySelector('#draft-preview-panel');
  const previewJson = editor.querySelector('#draft-json');
  const stateBadge = editor.querySelector('#draft-state');
  const validationSummary = editor.querySelector('#draft-validation-summary');
  const validationResults = editor.querySelector('#draft-validation-results');
  const filenameInput = editor.querySelector('#draft-filename');
  const confirmButton = editor.querySelector('#draft-confirm');
  const copyButton = editor.querySelector('#draft-copy');
  const downloadButton = editor.querySelector('#draft-download');
  const exportFeedback = editor.querySelector('#draft-export-feedback');
  const allowedArtifactTypes = new Set(['analysis', 'plan', 'draft', 'patch', 'test_result', 'review', 'summary']);
  let validatedCandidateText = '';
  let confirmationState = 'editing';

  const stateLabels = {
    editing: '编辑中 · 不可派发',
    validated: '校验通过 · 等待人工确认',
    operator_confirmed: '已人工确认 · 仅可导出',
  };
  const setState = (state) => {
    confirmationState = state;
    stateBadge.dataset.state = state;
    stateBadge.textContent = stateLabels[state];
    stateBadge.classList.toggle('pill--pass', state === 'validated' || state === 'operator_confirmed');
    confirmButton.disabled = state !== 'validated';
    copyButton.disabled = state !== 'operator_confirmed';
    downloadButton.disabled = state !== 'operator_confirmed';
  };
  const splitList = (value) => Array.from(new Set(value.split(',').map((item) => item.trim()).filter(Boolean)));
  const filenameFor = () => {
    const title = editor.querySelector('#draft-task-title').value.trim();
    const parent = editor.querySelector('#draft-parent-task').value.trim();
    const base = `${title}-${parent}`.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 96) || 'candidate';
    return `collaboration-plan-${base}.json`;
  };
  const resetDraftState = () => {
    validatedCandidateText = '';
    previewPanel.hidden = true;
    validationResults.replaceChildren();
    validationSummary.textContent = '内容已修改，请重新校验。';
    exportFeedback.textContent = '需先校验并人工确认。';
    setState('editing');
  };
  const bindRemove = (row) => {
    row.querySelector('.draft-remove').addEventListener('click', () => {
      row.remove();
      resetDraftState();
    });
  };
  const readWorkItems = () => Array.from(body.querySelectorAll('.draft-work-item')).map((row) => {
    const socket = row.querySelector('.draft-socket');
    const selected = socket.selectedOptions[0];
    return {
      work_item_id: row.querySelector('.draft-id').value.trim(),
      socket_id: socket.value,
      role: selected ? selected.dataset.role : '',
      depends_on: splitList(row.querySelector('.draft-depends').value),
      expected_artifact_types: splitList(row.querySelector('.draft-artifacts').value),
      review_required: row.querySelector('.draft-review').checked,
    };
  });
  const hasDependencyCycle = (workItems) => {
    const byId = new Map(workItems.map((item) => [item.work_item_id, item]));
    const visiting = new Set();
    const visited = new Set();
    const visit = (itemId) => {
      if (visiting.has(itemId)) return true;
      if (visited.has(itemId)) return false;
      visiting.add(itemId);
      const item = byId.get(itemId);
      if (item && item.depends_on.some((dependency) => byId.has(dependency) && visit(dependency))) return true;
      visiting.delete(itemId);
      visited.add(itemId);
      return false;
    };
    return workItems.some((item) => visit(item.work_item_id));
  };
  const buildCandidate = (workItems) => {
    const bindingMap = new Map();
    workItems.forEach((item) => {
      if (!bindingMap.has(item.socket_id)) {
        bindingMap.set(item.socket_id, {
          socket_id: item.socket_id,
          role: item.role,
          required_capabilities: [],
        });
      }
    });
    const byId = new Map(workItems.map((item) => [item.work_item_id, item]));
    const handoffs = [];
    workItems.forEach((target) => target.depends_on.forEach((sourceId) => {
      const source = byId.get(sourceId);
      handoffs.push({
        from_work_item_id: sourceId,
        to_work_item_id: target.work_item_id,
        artifact_types: source ? [...source.expected_artifact_types] : [],
      });
    }));
    const reviewGates = workItems.filter((item) => item.review_required).map((item) => ({
      gate_id: `review-${item.work_item_id}`,
      after_work_item_ids: [item.work_item_id],
      review_role: 'reviewer',
      decision_options: ['approve', 'request_changes'],
    }));
    return {
      parent_task_ref: editor.querySelector('#draft-parent-task').value.trim(),
      revision: 1,
      socket_bindings: Array.from(bindingMap.values()),
      work_items: workItems,
      handoffs: handoffs,
      review_gates: reviewGates,
    };
  };
  const validateCandidate = () => {
    const title = editor.querySelector('#draft-task-title').value.trim();
    const parent = editor.querySelector('#draft-parent-task').value.trim();
    const workItems = readWorkItems();
    const ids = workItems.map((item) => item.work_item_id);
    const categories = {
      '结构校验': [],
      '依赖校验': [],
      'Agent 插座绑定校验': [],
      '审阅要求校验': [],
    };
    const fail = (category, message) => categories[category].push(message);
    if (!title) fail('结构校验', '任务标题不能为空。');
    if (!parent) fail('结构校验', '父任务引用不能为空。');
    if (!workItems.length) fail('结构校验', '至少需要一个工作项。');
    if (ids.some((item) => !item)) fail('结构校验', '每个工作项都必须填写 ID。');
    if (new Set(ids).size !== ids.length) fail('结构校验', '工作项 ID 不能重复。');
    const bindingRoles = new Map();
    workItems.forEach((item) => {
      if (!item.socket_id || !item.role) fail('Agent 插座绑定校验', `工作项 ${item.work_item_id || '未命名'} 必须选择带角色绑定的 Agent 插座。`);
      if (bindingRoles.has(item.socket_id) && bindingRoles.get(item.socket_id) !== item.role) fail('Agent 插座绑定校验', `Agent 插座 ${item.socket_id} 不能绑定多个角色。`);
      bindingRoles.set(item.socket_id, item.role);
      if (!item.expected_artifact_types.length) fail('结构校验', `工作项 ${item.work_item_id || '未命名'} 必须填写至少一种预期产物。`);
      item.expected_artifact_types.forEach((artifact) => {
        if (!allowedArtifactTypes.has(artifact)) fail('结构校验', `工作项 ${item.work_item_id || '未命名'} 使用了不支持的产物类型 ${artifact}。`);
      });
      item.depends_on.forEach((dependency) => {
        if (!ids.includes(dependency)) fail('依赖校验', `工作项 ${item.work_item_id || '未命名'} 引用了不存在的依赖 ${dependency}。`);
        if (dependency === item.work_item_id) fail('依赖校验', `工作项 ${item.work_item_id} 不能依赖自身。`);
      });
    });
    if (hasDependencyCycle(workItems)) fail('依赖校验', '工作项依赖不能形成循环。');
    const candidate = buildCandidate(workItems);
    const reviewedIds = new Set(candidate.review_gates.flatMap((gate) => gate.after_work_item_ids));
    workItems.forEach((item) => {
      if (item.review_required && !reviewedIds.has(item.work_item_id)) fail('审阅要求校验', `工作项 ${item.work_item_id} 缺少审阅门。`);
    });
    return {candidate, categories, errorCount: Object.values(categories).reduce((count, errors) => count + errors.length, 0)};
  };
  const renderValidation = ({categories, errorCount}) => {
    validationResults.replaceChildren();
    Object.entries(categories).forEach(([category, errors]) => {
      const item = document.createElement('li');
      item.className = errors.length ? 'draft-check draft-check--error' : 'draft-check draft-check--pass';
      const label = document.createElement('strong');
      label.textContent = `${errors.length ? '未通过' : '通过'}：${category}`;
      item.appendChild(label);
      if (errors.length) {
        const detail = document.createElement('ul');
        errors.forEach((message) => {
          const row = document.createElement('li');
          row.textContent = message;
          detail.appendChild(row);
        });
        item.appendChild(detail);
      }
      validationResults.appendChild(item);
    });
    validationSummary.textContent = errorCount ? `校验未通过：发现 ${errorCount} 个问题。` : '校验通过：结构、依赖、Agent 插座绑定和审阅要求均符合候选契约。';
  };

  body.querySelectorAll('.draft-work-item').forEach(bindRemove);
  editor.addEventListener('input', (event) => {
    if (event.target.matches('input, select')) resetDraftState();
  });
  editor.addEventListener('change', (event) => {
    if (event.target.matches('input, select')) resetDraftState();
  });
  editor.querySelector('#draft-add').addEventListener('click', () => {
    const row = template.content.firstElementChild.cloneNode(true);
    bindRemove(row);
    body.appendChild(row);
    resetDraftState();
    row.querySelector('.draft-id').focus();
  });
  editor.querySelector('#draft-validate').addEventListener('click', () => {
    const result = validateCandidate();
    const candidateText = `${JSON.stringify(result.candidate, null, 2)}\n`;
    previewPanel.hidden = false;
    previewPanel.classList.toggle('draft-preview--error', result.errorCount > 0);
    previewJson.textContent = candidateText;
    filenameInput.value = filenameFor();
    renderValidation(result);
    exportFeedback.textContent = result.errorCount ? '请修正问题后重新校验。' : '校验通过，但仍需人工确认。';
    if (result.errorCount) {
      validatedCandidateText = '';
      setState('editing');
      return;
    }
    validatedCandidateText = candidateText;
    setState('validated');
  });
  confirmButton.addEventListener('click', () => {
    const result = validateCandidate();
    const currentText = `${JSON.stringify(result.candidate, null, 2)}\n`;
    if (result.errorCount || currentText !== validatedCandidateText) {
      exportFeedback.textContent = '候选内容已变化，请重新校验。';
      setState('editing');
      return;
    }
    setState('operator_confirmed');
    exportFeedback.textContent = '已人工确认。复制或下载不会授予派发权。';
  });
  const fallbackCopy = (text) => {
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand('copy');
    field.remove();
    if (!copied) throw new Error('copy-not-supported');
  };
  copyButton.addEventListener('click', async () => {
    if (confirmationState !== 'operator_confirmed' || !validatedCandidateText) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(validatedCandidateText);
      else fallbackCopy(validatedCandidateText);
      exportFeedback.textContent = '候选 JSON 已复制。仍不可派发、未执行。';
    } catch (error) {
      exportFeedback.textContent = '浏览器未允许复制，请使用下载按钮。';
    }
  });
  downloadButton.addEventListener('click', () => {
    if (confirmationState !== 'operator_confirmed' || !validatedCandidateText) return;
    const blob = new Blob([validatedCandidateText], {type: 'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filenameInput.value;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    exportFeedback.textContent = '候选 JSON 下载已由用户触发。仍不可派发、未执行。';
  });
  setState('editing');
})();
"""


def render_control_panel_html(payload: dict[str, Any]) -> str:
    """Render one safe snapshot payload as self-contained deterministic HTML."""
    summary = payload["summary"]
    sections = payload["sections"]
    snapshot_id = str(payload["snapshot_id"])
    envelope_file = payload.get("source", {}).get("envelope_file") or "未提供"

    metric_specs = (
        ("任务", summary.get("total_tasks", 0)),
        ("已阻止", summary.get("blocked_tasks", 0)),
        ("适配器（Adapter）", summary.get("total_adapters", 0)),
        ("运行记录", summary.get("run_count", 0)),
        ("待处理审批", summary.get("pending_approval_count", 0)),
        ("产物", summary.get("artifact_count", 0)),
    )
    metrics = "".join(
        '<div class="metric">'
        f'<span class="metric__value">{_escape(value)}</span>'
        f'<span class="metric__label">{_escape(label)}</span>'
        "</div>"
        for label, value in metric_specs
    )

    section_names = [name for name in _SECTION_ORDER if name in sections]
    for optional_section in ("external_agents", "collaboration", "dispatch", "manual_board", "collaboration_run", "collaboration_actions", "collaboration_inbox"):
        if optional_section in sections:
            section_names.append(optional_section)
    nav_labels = {
        "overview": "总览", "tasks": "任务", "adapters": "适配器", "automation": "自动化",
        "runs": "运行记录", "approvals": "审批", "artifacts": "产物", "reports": "报告",
        "collaboration": "协作计划", "dispatch": "派发资格", "manual_board": "人工看板",
        "external_agents": "外部智能体", "collaboration_run": "协作运行", "collaboration_actions": "操作资格", "collaboration_inbox": "当前待办",
    }
    nav = "".join(
        f'<a href="#{name.replace("_", "-")}">{_escape(nav_labels.get(name, name))}</a>'
        for name in section_names
    )

    overview = sections["overview"]
    overview_labels = {
        "total_tasks": "任务总数",
        "planned_tasks": "已计划任务",
        "running_tasks": "运行中任务",
        "blocked_tasks": "已阻止任务",
        "finished_tasks": "已完成任务",
        "failed_tasks": "失败任务",
        "total_events": "事件总数",
        "latest_task_updated_at": "最近任务更新时间",
    }
    overview_rows = [
        {"metric": f"{overview_labels.get(key, '技术指标')}（{key}）", "value": value}
        for key, value in overview.get("summary", {}).items()
    ]
    section_html = [
        '<section class="panel-section" id="overview">',
        _section_header("01", "总览 / 项目状态", overview),
        _table(
            caption="总览指标",
            columns=(("metric", "指标"), ("value", "数值")),
            rows=overview_rows,
            empty_message="没有总览指标。",
        ),
        "</section>",
    ]

    tasks = sections["tasks"]
    section_html.extend(
        [
            '<section class="panel-section" id="tasks">',
            _section_header("02", "任务 / 账本快照", tasks),
            _table(
                caption="任务快照",
                columns=(
                    ("task_id", "任务 ID"),
                    ("title", "标题"),
                    ("status", "状态"),
                    ("requested_capability", "请求能力"),
                    ("assignee", "负责人"),
                    ("updated_at", "更新时间"),
                ),
                rows=tasks.get("tasks", []),
                empty_message="没有任务快照。",
            ),
            "</section>",
        ]
    )

    adapters = sections["adapters"]
    section_html.extend(
        [
            '<section class="panel-section" id="adapters">',
            _section_header("03", "适配器（Adapter）/ 能力注册表", adapters),
            _table(
                caption="适配器注册表",
                columns=(
                    ("adapter_id", "适配器 ID"),
                    ("adapter_type", "类型"),
                    ("risk_level", "风险等级"),
                    ("enabled", "已启用"),
                    ("capability_count", "能力数量"),
                    ("supports_approval_roundtrip", "支持审批闭环"),
                    ("supports_artifacts", "支持产物"),
                ),
                rows=adapters.get("adapters", []),
                empty_message="没有适配器投影。",
            ),
            _table(
                caption="Agent 插座（Socket）/ 已声明插件",
                columns=(
                    ("socket_id", "Agent 插座（Socket）ID"),
                    ("invocation_mode", "调用模式"),
                    ("availability", "可用性"),
                    ("risk_level", "风险等级"),
                    ("capabilities", "能力"),
                ),
                rows=adapters.get("agent_sockets", []),
                empty_message="没有 Agent 插座投影。",
            ),
            "</section>",
        ]
    )

    automation = sections["automation"]
    section_html.extend(
        [
            '<section class="panel-section" id="automation">',
            _section_header("04", "自动化 / 使用方契约", automation),
            _table(
                caption="自动化配置档（Profile）",
                columns=(
                    ("profile_id", "配置档 ID"),
                    ("requirement_count", "要求数量"),
                    ("allow_preview", "允许预览"),
                    ("max_access", "最高访问级别"),
                    ("description", "原始技术说明"),
                ),
                rows=automation.get("profiles", []),
                empty_message="没有自动化配置档投影。",
            ),
            "</section>",
        ]
    )

    runs = sections["runs"]
    section_html.extend(
        [
            '<section class="panel-section" id="runs">',
            _section_header("05", "运行记录 / 执行信封（Envelope）投影", runs),
            (
                _boundary_callout(runs)
                if runs.get("status") == "unavailable"
                else _table(
                    caption="执行信封中的运行记录",
                    columns=(("request_id", "请求 ID"), ("task_id", "任务 ID"), ("adapter_id", "适配器 ID"), ("operation", "操作"), ("mode", "模式"), ("status", "状态")),
                    rows=runs.get("runs", []),
                    empty_message="当前执行信封中没有运行记录。",
                )
            ),
            "</section>",
        ]
    )

    approvals = sections["approvals"]
    section_html.extend(
        [
            '<section class="panel-section" id="approvals">',
            _section_header("06", "审批 / 执行信封（Envelope）投影", approvals),
            (
                _boundary_callout(approvals)
                if approvals.get("status") == "unavailable"
                else _table(
                    caption="执行信封中的审批",
                    columns=(("approval_id", "审批 ID"), ("task_id", "任务 ID"), ("adapter_id", "适配器 ID"), ("operation", "操作"), ("status", "状态"), ("requested_at", "请求时间")),
                    rows=approvals.get("approvals", []),
                    empty_message="当前执行信封中没有审批。",
                )
            ),
            "</section>",
        ]
    )

    artifacts = sections["artifacts"]
    section_html.extend(
        [
            '<section class="panel-section" id="artifacts">',
            _section_header("07", "产物 / 安全摘要", artifacts),
            (
                _boundary_callout(artifacts)
                if artifacts.get("status") == "unavailable"
                else _table(
                    caption="执行信封中的产物",
                    columns=(("artifact_id", "产物 ID"), ("artifact_type", "类型"), ("task_id", "任务 ID"), ("producer", "产出者"), ("timestamp", "时间戳"), ("summary", "摘要")),
                    rows=artifacts.get("artifacts", []),
                    empty_message="当前执行信封中没有产物。",
                )
            ),
            "</section>",
        ]
    )

    reports = sections["reports"]
    section_html.extend(
        [
            '<section class="panel-section" id="reports">',
            _section_header("08", "报告 / 请求边界", reports),
            _boundary_callout(reports),
            "</section>",
        ]
    )

    external_agents = sections.get("external_agents")
    if external_agents is not None:
        observations = {
            item.get("profile_id"): item
            for item in external_agents.get("observations", [])
        }
        live_rows = []
        for agent in external_agents.get("agents", []):
            observation = observations.get(agent.get("agent_id"), {})
            readiness = agent.get("readiness", {})
            live_rows.append(
                {
                    "display_name_zh": agent.get("display_name_zh"),
                    "status_label_zh": agent.get("status_label_zh"),
                    "observed_at": observation.get("observed_at") or "尚未观察",
                    "evidence_valid": "是" if observation.get("evidence_valid") else "否",
                    "blocked_reason_code": agent.get("blocked_reason_code") or "无",
                    "dispatch_authorized": "否",
                    "safe_summary_zh": agent.get("safe_summary_zh"),
                }
            )
        section_html.extend(
            [
                '<section class="panel-section" id="external-agents">',
                _section_header("15", "外部智能体 / 实时状态", external_agents),
                _table(
                    caption="Pi/OMP 真实只读状态",
                    columns=(
                        ("display_name_zh", "智能体"),
                        ("status_label_zh", "当前状态"),
                        ("observed_at", "最后观察时间"),
                        ("evidence_valid", "证据有效"),
                        ("blocked_reason_code", "不可派发原因"),
                        ("dispatch_authorized", "允许派发"),
                        ("safe_summary_zh", "安全说明"),
                    ),
                    rows=live_rows,
                    empty_message="尚未获得 Pi/OMP 状态。",
                ),
                "</section>",
            ]
        )

    collaboration = sections.get("collaboration")
    if collaboration is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="collaboration">',
                _section_header(
                    "09", "协作 / 计划投影", collaboration
                ),
                _collaboration_section_body(collaboration),
                "</section>",
            ]
        )

    dispatch = sections.get("dispatch")
    if dispatch is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="dispatch">',
                _section_header("10", "协作 / 派发资格", dispatch),
                _dispatch_section_body(dispatch),
                "</section>",
            ]
        )

    manual_board = sections.get("manual_board")
    if manual_board is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="manual-board">',
                _section_header("11", "协作 / 人工看板", manual_board),
                _manual_board_section_body(manual_board),
                "</section>",
            ]
        )

    collaboration_run = sections.get("collaboration_run")
    if collaboration_run is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="collaboration-run">',
                _section_header("12", "协作 / 运行状态", collaboration_run),
                _collaboration_run_section_body(collaboration_run),
                "</section>",
            ]
        )

    collaboration_actions = sections.get("collaboration_actions")
    if collaboration_actions is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="collaboration-actions">',
                _section_header("13", "协作 / 操作资格", collaboration_actions),
                _collaboration_action_section_body(collaboration_actions),
                "</section>",
            ]
        )

    collaboration_inbox = sections.get("collaboration_inbox")
    if collaboration_inbox is not None:
        section_html.extend(
            [
                '<section class="panel-section" id="collaboration-inbox">',
                _section_header("14", "协作 / 当前待办", collaboration_inbox),
                _collaboration_inbox_section_body(collaboration_inbox),
                "</section>",
            ]
        )

    findings_html = ""
    findings = payload.get("findings", [])
    if findings:
        items = "".join(
            '<li data-search-row '
            f'data-search="{_escape(finding.get("rule_id", ""))}">'
            f'<strong>{_escape(finding.get("rule_id"))}</strong> — '
            f'{_escape(finding.get("message"))}</li>'
            for finding in findings
        )
        findings_html = (
            '<aside class="findings" aria-labelledby="findings-title">'
            '<h2 id="findings-title">数据源问题</h2>'
            f"<ul>{items}</ul></aside>"
        )

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>S-BLACK / 多 Agent 协作控制台</title>
<style>{_CSS}</style>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<div class="shell">
<header class="masthead">
  <div class="topline"><span>S-BLACK 控制框架工程（Harness Engineering）</span><span>本地 / 只读 / 确定性</span></div>
  <div class="hero">
    <div>
      <span class="eyebrow">多 Agent 协作审计界面</span>
      <h1>S-BLACK / 控制台</h1>
      <p class="hero-copy">本地静态控制面。所有内容来自既有安全只读模型（read model）；不执行命令、不写账本（ledger）、不启动服务（service）。</p>
    </div>
    <div class="hero-meta">
      <span class="eyebrow">投影数据源</span>
      <p>执行信封（Envelope）：{_escape(envelope_file)}</p>
      <code>{_escape(snapshot_id)}</code>
    </div>
  </div>
  <div class="summary-grid">{metrics}</div>
</header>
<div class="toolbar">
  <div class="search"><label for="panel-search">筛选 /</label><input id="panel-search" aria-label="全局过滤" type="search" placeholder="按任务、适配器、状态、产物过滤（按 / 聚焦）"><span id="filter-count" aria-live="polite"></span></div>
  <nav class="nav" aria-label="控制台区段">{nav}</nav>
</div>
<main id="main">{''.join(section_html)}{findings_html}</main>
<footer class="footer"><span>不访问网络 · 不启动服务 · 不执行 Agent · 不写入数据</span><span>数据结构版本（schema）：{_escape(payload.get('schema_version'))}</span></footer>
</div>
<script>{_JS}</script>
</body>
</html>
'''

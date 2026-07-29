"""Safe, bounded read model for the Agent Deck workbench."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .control_panel_live_gui import build_live_control_panel_snapshot
from .orchestration_control_panel_registered_work import load_registered_work_inbox
from .result import EXIT_ERROR, EXIT_PASS, Finding

AGENT_DECK_SCHEMA_VERSION = "agent-deck/read-model/v1"
MAX_CHAIN_LIMIT = 20
_PENDING_AGENTS = (
    ("codex-cli", "Codex CLI"),
    ("claude-code", "Claude Code"),
    ("kimi-code", "Kimi Code"),
)
_LIVE_ORDER = ("pi-local", "omp-local")


@dataclass(frozen=True)
class AgentDeckSnapshot:
    status: str
    payload: dict[str, Any]

    def exit_code(self) -> int:
        return EXIT_PASS if self.status == "pass" else EXIT_ERROR

    def to_dict(self) -> dict[str, Any]:
        return self.payload


def _snapshot_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _pending_agent(agent_id: str, display_name: str) -> dict[str, str]:
    return {
        "id": agent_id,
        "name_zh": display_name,
        "role_zh": "待接入成员",
        "integration_status": "not_integrated",
        "status": "unknown",
        "status_label_zh": "待接入",
        "safe_summary_zh": "尚未接入真实状态或执行能力。",
    }


def _unavailable_live_agent(agent_id: str, display_name: str) -> dict[str, str]:
    return {
        "id": agent_id,
        "name_zh": display_name,
        "role_zh": "试运行成员",
        "integration_status": "live",
        "status": "unavailable",
        "status_label_zh": "不可用",
        "safe_summary_zh": "尚未获得可安全展示的实时状态。",
    }


def _safe_live_agent(value: object, *, expected_id: str, display_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("agent_id") != expected_id:
        return _unavailable_live_agent(expected_id, display_name)
    status = value.get("status")
    label = value.get("status_label_zh")
    summary = value.get("safe_summary_zh")
    readiness = value.get("readiness")
    if not isinstance(status, str) or not isinstance(label, str) or not isinstance(summary, str):
        return _unavailable_live_agent(expected_id, display_name)
    readiness_status = readiness.get("status") if isinstance(readiness, dict) else "unknown"
    return {
        "id": expected_id,
        "name_zh": display_name,
        "role_zh": "规划与审阅成员" if expected_id == "pi-local" else "执行成员",
        "integration_status": "live",
        "status": status,
        "status_label_zh": label,
        "readiness_status": readiness_status if isinstance(readiness_status, str) else "unknown",
        "safe_summary_zh": summary,
    }


def _safe_timeline(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    records: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        chain_id = item.get("chain_id")
        status = item.get("status")
        if not isinstance(chain_id, str) or not isinstance(status, str):
            continue
        record: dict[str, object] = {"chain_id": chain_id, "status": status}
        for key in ("status_label_zh", "safe_summary_zh", "updated_at"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate:
                record[key] = candidate
        records.append(record)
    return sorted(records, key=lambda item: str(item["chain_id"]))[:MAX_CHAIN_LIMIT]


def _invalid(evaluated_at: str, code: str, message: str) -> AgentDeckSnapshot:
    payload: dict[str, Any] = {
        "status": "validation_failed",
        "schema_version": AGENT_DECK_SCHEMA_VERSION,
        "source_mode": "runtime",
        "source": {"evaluated_at": evaluated_at},
        "findings": [Finding(code, "error", "error", message).to_dict()],
        "guarantees": {"read_only": True, "accesses_network": False, "executes_commands": False},
    }
    payload["snapshot_id"] = _snapshot_id(payload)
    return AgentDeckSnapshot("validation_failed", payload)


def build_agent_deck_snapshot(root: Path, *, evaluated_at: str, chain_limit: int = MAX_CHAIN_LIMIT) -> AgentDeckSnapshot:
    """Build a safe Agent Deck projection from existing read-only sources."""
    if not isinstance(chain_limit, int) or isinstance(chain_limit, bool) or not 1 <= chain_limit <= MAX_CHAIN_LIMIT:
        return _invalid(evaluated_at, "agent-deck-chain-limit-invalid", "链路展示上限必须在 1 到 20 条之间。")
    panel = build_live_control_panel_snapshot(root.resolve(), evaluated_at=evaluated_at, chain_limit=chain_limit).to_dict()
    sections = panel.get("sections") if isinstance(panel, dict) else {}
    sections = sections if isinstance(sections, dict) else {}
    live = sections.get("external_agents")
    source_agents = live.get("agents") if isinstance(live, dict) else []
    source_agents = source_agents if isinstance(source_agents, list) else []
    by_id = {item.get("agent_id"): item for item in source_agents if isinstance(item, dict) and isinstance(item.get("agent_id"), str)}
    agents: list[dict[str, object]] = [
        _safe_live_agent(by_id.get("pi-local"), expected_id="pi-local", display_name="Pi"),
        _safe_live_agent(by_id.get("omp-local"), expected_id="omp-local", display_name="OMP"),
        *[_pending_agent(agent_id, name) for agent_id, name in _PENDING_AGENTS],
    ]
    chains_section = sections.get("external_agent_chains")
    chains = chains_section.get("chains") if isinstance(chains_section, dict) else []
    inbox = load_registered_work_inbox(root.resolve()).to_safe_dict()
    cards = inbox.get("cards") if isinstance(inbox, dict) else []
    cards = cards if isinstance(cards, list) else []
    payload: dict[str, Any] = {
        "status": "pass" if panel.get("status") == "pass" else "blocked",
        "schema_version": AGENT_DECK_SCHEMA_VERSION,
        "source_mode": "runtime",
        "source": {"control_panel_snapshot_id": panel.get("snapshot_id"), "evaluated_at": evaluated_at},
        "project": {"id": "agent-runtime", "name_zh": "Agent Runtime"},
        "agents": agents,
        "registered_work": sorted(cards, key=lambda item: str(item.get("card_id", "")) if isinstance(item, dict) else ""),
        "tasks": [],
        "timeline": _safe_timeline(chains),
        "delivery": {"summary_zh": "P0 仅展示安全摘要；最终业务决定仍由既有受控 GUI 完成。"},
        "findings": list(live.get("findings", [])) if isinstance(live, dict) and isinstance(live.get("findings"), list) else [],
        "guarantees": {"read_only": True, "accesses_network": False, "executes_commands": False, "ui_dispatch": False},
    }
    payload["snapshot_id"] = _snapshot_id(payload)
    return AgentDeckSnapshot(str(payload["status"]), payload)
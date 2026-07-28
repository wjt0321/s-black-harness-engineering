"""Fixed, read-only registered-work inbox for the foreground control panel."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .result import Finding

_INBOX_FILE = Path("adapters/control-panel-registered-work-inbox.json")
_CONTRACT = "control-panel-registered-work-inbox/v1"
_CARD_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_ALLOWED_TOPOLOGIES = {
    ("pi-local", "omp-local", "pi-local"),
    ("omp-local", "pi-local", "omp-local"),
}


@dataclass(frozen=True)
class RegisteredWorkCard:
    card_id: str
    title_zh: str
    summary_zh: str
    task_id: str
    collaboration_file: str
    goal: str
    topology: tuple[str, str, str]

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "title_zh": self.title_zh,
            "summary_zh": self.summary_zh,
            "task_id": self.task_id,
            "topology": list(self.topology),
            "goal_digest": "sha256:" + hashlib.sha256(self.goal.encode("utf-8")).hexdigest(),
        }


@dataclass(frozen=True)
class RegisteredWorkInboxResult:
    status: str
    cards: tuple[RegisteredWorkCard, ...] = ()
    findings: tuple[Finding, ...] = ()

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "schema_version": _CONTRACT,
            "cards": [card.to_safe_dict() for card in self.cards],
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
                "read_only": True,
                "fixed_path_only": True,
                "writes_files": False,
                "executes_commands": False,
                "starts_service": False,
                "accesses_network": False,
            },
        }


def _failure() -> RegisteredWorkInboxResult:
    return RegisteredWorkInboxResult(
        "validation_failed",
        findings=(
            Finding(
                "control-panel-registered-work-invalid",
                "error",
                "error",
                "已登记工作配置不符合固定安全结构；不会显示或启动任何工作。",
            ),
        ),
    )


def _safe_text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        return None
    return value


def _parse_card(value: object) -> RegisteredWorkCard | None:
    if not isinstance(value, dict) or set(value) != {
        "card_id",
        "title_zh",
        "summary_zh",
        "task_id",
        "collaboration_file",
        "goal",
        "topology",
    }:
        return None
    card_id = _safe_text(value.get("card_id"), maximum=64)
    title_zh = _safe_text(value.get("title_zh"), maximum=100)
    summary_zh = _safe_text(value.get("summary_zh"), maximum=280)
    task_id = _safe_text(value.get("task_id"), maximum=120)
    collaboration_file = _safe_text(value.get("collaboration_file"), maximum=240)
    goal = _safe_text(value.get("goal"), maximum=2000)
    topology_raw = value.get("topology")
    if (
        card_id is None
        or not _CARD_ID_RE.fullmatch(card_id)
        or title_zh is None
        or summary_zh is None
        or task_id is None
        or collaboration_file is None
        or goal is None
        or not isinstance(topology_raw, list)
        or len(topology_raw) != 3
        or not all(isinstance(item, str) for item in topology_raw)
    ):
        return None
    topology = tuple(topology_raw)
    if topology not in _ALLOWED_TOPOLOGIES:
        return None
    path = Path(collaboration_file)
    if (
        "\\" in collaboration_file
        or path.is_absolute()
        or path.suffix != ".json"
        or len(path.parts) < 2
        or path.parts[0] != "adapters"
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return None
    return RegisteredWorkCard(
        card_id=card_id,
        title_zh=title_zh,
        summary_zh=summary_zh,
        task_id=task_id,
        collaboration_file=collaboration_file,
        goal=goal,
        topology=topology,  # type: ignore[arg-type]
    )


def load_registered_work_inbox(root: Path) -> RegisteredWorkInboxResult:
    """Read only the fixed reviewed inbox; it accepts no caller-selected path."""
    root = root.resolve()
    path = (root / _INBOX_FILE).resolve()
    try:
        path.relative_to(root)
        raw = path.read_bytes()
        if not raw or len(raw) > 32768:
            return _failure()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return _failure()
    if not isinstance(document, dict) or set(document) != {"version", "contract", "cards"}:
        return _failure()
    cards_raw = document.get("cards")
    if document.get("version") != 1 or document.get("contract") != _CONTRACT or not isinstance(cards_raw, list):
        return _failure()
    if not 1 <= len(cards_raw) <= 20:
        return _failure()
    cards = tuple(_parse_card(value) for value in cards_raw)
    if any(card is None for card in cards):
        return _failure()
    typed_cards = tuple(card for card in cards if card is not None)
    if len({card.card_id for card in typed_cards}) != len(typed_cards):
        return _failure()
    return RegisteredWorkInboxResult("pass", cards=typed_cards)

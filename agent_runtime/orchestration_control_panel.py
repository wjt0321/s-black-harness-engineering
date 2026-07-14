"""Stage 16 deterministic read-only Control Panel snapshot and static HTML."""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .orchestration_adapter import list_adapters
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
                f"{name}={self.sections[name]['status']}"
                for name in _SECTION_ORDER
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


def build_control_panel_snapshot(
    root: Path,
    *,
    envelope_file: str | None = None,
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
        "automation_profile_count": len(automation.get("profiles", [])),
        "run_count": len(runs.get("runs", [])),
        "pending_approval_count": sum(
            item.get("status") == "pending" for item in approval_rows
        ),
        "artifact_count": len(artifacts.get("artifacts", [])),
        "unavailable_sections": [
            name
            for name in _SECTION_ORDER
            if sections[name].get("status") == "unavailable"
        ],
        "section_statuses": {
            name: sections[name].get("status", "error")
            for name in _SECTION_ORDER
        },
    }
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
    return ControlPanelSnapshot(
        status=status,
        source={"envelope_file": envelope_file},
        summary=summary,
        sections=sections,
        findings=findings,
        next_action=next_action,
    )


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return html.escape(", ".join(str(item) for item in value), quote=True)
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
        f"{_escape(status)}</span>"
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
        cells = "".join(f"<td>{_escape(row.get(key))}</td>" for key, _ in columns)
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
        f'<p>scope={_escape(section.get("scope"))} · '
        f'availability={_escape(section.get("availability"))}</p>'
        "</div>"
        f"{_status_badge(str(section.get('status', 'error')))}"
        "</div>"
    )


def _boundary_callout(section: dict[str, Any]) -> str:
    return (
        '<div class="boundary-callout" data-search-row '
        f'data-search="{_escape(section.get("message", ""))}">'
        '<div class="boundary-callout__mark" aria-hidden="true">//</div>'
        '<div><strong>BOUNDARY / NOT A COLLECTION</strong>'
        f'<p>{_escape(section.get("message"))}</p>'
        f'<code>{_escape(section.get("command_hint"))}</code></div>'
        "</div>"
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
.masthead::after { content: "CONTROL / 16"; position: absolute; right: -1rem; bottom: -2.7rem; color: rgba(245,185,66,.055); font: 900 clamp(5rem, 14vw, 12rem)/1 "Bahnschrift Condensed", Impact, sans-serif; letter-spacing: -.06em; }
.topline { display: flex; justify-content: space-between; gap: 1rem; padding: .8rem 1rem; border-bottom: 1px solid var(--line); color: var(--muted); font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
.hero { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(18rem, .65fr); gap: 2rem; padding: clamp(1.5rem, 5vw, 4.5rem); }
.eyebrow { color: var(--amber); font-size: .75rem; letter-spacing: .2em; text-transform: uppercase; }
h1 { max-width: 12ch; margin: .5rem 0 1rem; font: 900 clamp(3rem, 7vw, 7.4rem)/.86 "Bahnschrift Condensed", Impact, sans-serif; letter-spacing: -.045em; text-transform: uppercase; }
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
.footer { display: grid; grid-template-columns: 1fr auto; gap: 1rem; margin-top: 1rem; padding: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .68rem; }
.is-filtered-out { display: none !important; }
@media (max-width: 1050px) { .summary-grid { grid-template-columns: repeat(3, 1fr); } .hero { grid-template-columns: 1fr; } .toolbar { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .shell { width: min(100% - 1rem, 1540px); } .summary-grid { grid-template-columns: repeat(2, 1fr); } .hero { padding: 1.5rem; } h1 { font-size: 3.2rem; } .section-heading { grid-template-columns: auto 1fr; } .section-heading .status { grid-column: 2; justify-self: start; } th, td { padding: .65rem; } }
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
    counter.textContent = `${visible}/${rows.length} visible`;
  };
  input.addEventListener('input', apply);
  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && document.activeElement !== input) {
      event.preventDefault();
      input.focus();
    }
  });
  apply();
})();
"""


def render_control_panel_html(payload: dict[str, Any]) -> str:
    """Render one safe snapshot payload as self-contained deterministic HTML."""
    summary = payload["summary"]
    sections = payload["sections"]
    snapshot_id = str(payload["snapshot_id"])
    envelope_file = payload.get("source", {}).get("envelope_file") or "not supplied"

    metric_specs = (
        ("Tasks", summary.get("total_tasks", 0)),
        ("Blocked", summary.get("blocked_tasks", 0)),
        ("Adapters", summary.get("total_adapters", 0)),
        ("Runs", summary.get("run_count", 0)),
        ("Pending approvals", summary.get("pending_approval_count", 0)),
        ("Artifacts", summary.get("artifact_count", 0)),
    )
    metrics = "".join(
        '<div class="metric">'
        f'<span class="metric__value">{_escape(value)}</span>'
        f'<span class="metric__label">{_escape(label)}</span>'
        "</div>"
        for label, value in metric_specs
    )

    nav = "".join(
        f'<a href="#{name}">{_escape(name)}</a>' for name in _SECTION_ORDER
    )

    overview = sections["overview"]
    overview_rows = [
        {"metric": key, "value": value}
        for key, value in overview.get("summary", {}).items()
    ]
    section_html = [
        '<section class="panel-section" id="overview">',
        _section_header("01", "Overview / Project pulse", overview),
        _table(
            caption="Overview metrics",
            columns=(("metric", "Metric"), ("value", "Value")),
            rows=overview_rows,
            empty_message="No overview metrics.",
        ),
        "</section>",
    ]

    tasks = sections["tasks"]
    section_html.extend(
        [
            '<section class="panel-section" id="tasks">',
            _section_header("02", "Tasks / Ledger snapshots", tasks),
            _table(
                caption="Task snapshots",
                columns=(
                    ("task_id", "Task"),
                    ("title", "Title"),
                    ("status", "Status"),
                    ("requested_capability", "Capability"),
                    ("assignee", "Assignee"),
                    ("updated_at", "Updated"),
                ),
                rows=tasks.get("tasks", []),
                empty_message="No task snapshots.",
            ),
            "</section>",
        ]
    )

    adapters = sections["adapters"]
    section_html.extend(
        [
            '<section class="panel-section" id="adapters">',
            _section_header("03", "Adapters / Capability registry", adapters),
            _table(
                caption="Adapter registry",
                columns=(
                    ("adapter_id", "Adapter"),
                    ("adapter_type", "Type"),
                    ("risk_level", "Risk"),
                    ("enabled", "Enabled"),
                    ("capability_count", "Capabilities"),
                    ("supports_approval_roundtrip", "Approval"),
                    ("supports_artifacts", "Artifacts"),
                ),
                rows=adapters.get("adapters", []),
                empty_message="No adapters projected.",
            ),
            "</section>",
        ]
    )

    automation = sections["automation"]
    section_html.extend(
        [
            '<section class="panel-section" id="automation">',
            _section_header("04", "Automation / Consumer contracts", automation),
            _table(
                caption="Automation profiles",
                columns=(
                    ("profile_id", "Profile"),
                    ("requirement_count", "Requirements"),
                    ("allow_preview", "Preview"),
                    ("max_access", "Max access"),
                    ("description", "Description"),
                ),
                rows=automation.get("profiles", []),
                empty_message="No Automation Profiles projected.",
            ),
            "</section>",
        ]
    )

    runs = sections["runs"]
    section_html.extend(
        [
            '<section class="panel-section" id="runs">',
            _section_header("05", "Runs / Envelope projection", runs),
            (
                _boundary_callout(runs)
                if runs.get("status") == "unavailable"
                else _table(
                    caption="Envelope runs",
                    columns=(
                        ("request_id", "Request"),
                        ("task_id", "Task"),
                        ("adapter_id", "Adapter"),
                        ("operation", "Operation"),
                        ("mode", "Mode"),
                        ("status", "Status"),
                    ),
                    rows=runs.get("runs", []),
                    empty_message="No runs in this envelope.",
                )
            ),
            "</section>",
        ]
    )

    approvals = sections["approvals"]
    section_html.extend(
        [
            '<section class="panel-section" id="approvals">',
            _section_header("06", "Approvals / Envelope projection", approvals),
            (
                _boundary_callout(approvals)
                if approvals.get("status") == "unavailable"
                else _table(
                    caption="Envelope approvals",
                    columns=(
                        ("approval_id", "Approval"),
                        ("task_id", "Task"),
                        ("adapter_id", "Adapter"),
                        ("operation", "Operation"),
                        ("status", "Status"),
                        ("requested_at", "Requested"),
                    ),
                    rows=approvals.get("approvals", []),
                    empty_message="No approvals in this envelope.",
                )
            ),
            "</section>",
        ]
    )

    artifacts = sections["artifacts"]
    section_html.extend(
        [
            '<section class="panel-section" id="artifacts">',
            _section_header("07", "Artifacts / Safe summaries", artifacts),
            (
                _boundary_callout(artifacts)
                if artifacts.get("status") == "unavailable"
                else _table(
                    caption="Envelope artifacts",
                    columns=(
                        ("artifact_id", "Artifact"),
                        ("artifact_type", "Type"),
                        ("task_id", "Task"),
                        ("producer", "Producer"),
                        ("timestamp", "Timestamp"),
                        ("summary", "Summary"),
                    ),
                    rows=artifacts.get("artifacts", []),
                    empty_message="No artifacts in this envelope.",
                )
            ),
            "</section>",
        ]
    )

    reports = sections["reports"]
    section_html.extend(
        [
            '<section class="panel-section" id="reports">',
            _section_header("08", "Reports / Request boundary", reports),
            _boundary_callout(reports),
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
            '<h2 id="findings-title">Source findings</h2>'
            f"<ul>{items}</ul></aside>"
        )

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>S-BLACK / Control Plane</title>
<style>{_CSS}</style>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<div class="shell">
<header class="masthead">
  <div class="topline"><span>S-BLACK HARNESS ENGINEERING</span><span>LOCAL / READ-ONLY / DETERMINISTIC</span></div>
  <div class="hero">
    <div>
      <span class="eyebrow">Stage 16 · Audit surface</span>
      <h1>S-BLACK / CONTROL PLANE</h1>
      <p class="hero-copy">本地静态控制面。所有内容来自既有安全 read model；不执行命令、不写 ledger、不启动 service。</p>
    </div>
    <div class="hero-meta">
      <span class="eyebrow">Projection source</span>
      <p>envelope: {_escape(envelope_file)}</p>
      <code>{_escape(snapshot_id)}</code>
    </div>
  </div>
  <div class="summary-grid">{metrics}</div>
</header>
<div class="toolbar">
  <div class="search"><label for="panel-search">FILTER /</label><input id="panel-search" aria-label="全局过滤" type="search" placeholder="按 task、adapter、status、artifact 过滤（按 / 聚焦）"><span id="filter-count" aria-live="polite"></span></div>
  <nav class="nav" aria-label="控制台区段">{nav}</nav>
</div>
<main id="main">{''.join(section_html)}{findings_html}</main>
<footer class="footer"><span>NO NETWORK · NO SERVICE · NO EXECUTION · NO WRITE</span><span>{_escape(payload.get('schema_version'))}</span></footer>
</div>
<script>{_JS}</script>
</body>
</html>
'''

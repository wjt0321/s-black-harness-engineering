# Release Notes — Stage 70 Control Panel Collaboration Projection

> Date: 2026-07-26
> Status: included in v0.19.0 multi-Agent collaboration board milestone

## Shipped

- `orchestration control-panel snapshot|render|handoff` accept optional `--collaboration-file <project-local-json>`.
- Snapshot gains a file-scoped `collaboration` section that reuses the Stage 69 validated safe plan projection; invalid, missing, or escaping plans fail closed with findings and no plan payload.
- Handoff binds the normalized plan path into both snapshot and render `argv` arrays.
- Self-contained HTML render adds an accessible inline-SVG collaboration graph (work items layered by dependency, handoff arrows, review-gate diamonds) plus escaped tables for socket bindings, work items, handoffs, and review gates; validation failures render a boundary callout and findings table instead.
- `control_panel_read` contract `key_flags` now lists `--collaboration-file` alongside `--envelope`.

## Boundaries Kept

- No persistence, no ledger writes, no network, no process spawn, no readiness probe, no Agent invocation.
- Omitting `--collaboration-file` leaves snapshot/render/handoff payloads byte-identical to previous behavior.

## Evidence

- Fact source: `docs/118-control-panel-collaboration-projection.md`
- Tests: `tests/test_orchestration_control_panel_collaboration.py`

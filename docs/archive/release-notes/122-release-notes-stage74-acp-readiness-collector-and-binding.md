# Release Notes - Stage 74 ACP Readiness Collector and Dispatch Binding

> Date: 2026-07-26
> Status: included in v0.21.0 ACP readiness evidence foundation milestone

## Added

- `orchestration socket readiness collect` for deterministic project-local runner snapshots.
- Content hash, socket binding, TTL, and expiry validation.
- Optional readiness evidence binding in collaboration dispatch proposals.
- Control Panel evidence status, level, id, expiry, and blocker projection.

## Safety Boundary

- The collector does not contact QwenPaw or an ACP runner at runtime.
- `runner_listed` evidence remains `sufficient_for_dispatch=false`.
- Dispatch remains blocked by `readiness_insufficient` and `execution_authority_unavailable`.
- No Agent, model, process, session, credential, network, quota, ledger, or project write occurs.

## Verification

- Focused tests cover deterministic collection, missing runners, expiry, path escape, non-ACP sockets, TTL bounds, evidence tampering, socket mismatch, dispatch binding, Control Panel rendering, CLI surface, and doctor contracts.
- Full regression, doctor, docs context, CLI/HTML smoke, public scan, compileall, and diff review are required before the milestone commit.

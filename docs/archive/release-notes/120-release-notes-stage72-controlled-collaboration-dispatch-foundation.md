# Release Notes - Stage 72 Controlled Collaboration Dispatch Foundation

> Date: 2026-07-26
> Status: included in v0.20.0 controlled collaboration dispatch foundation milestone

## Added

- A schema-validated, content-addressed dispatch proposal for one collaboration-plan work item.
- Read-only `collaboration dispatch validate` and `inspect` CLI commands.
- An optional Control Panel dispatch projection with eligibility and blocked reasons.
- A static ACP readiness evidence schema and uncollected sample.

## Safety Boundary

- Every Stage 72 proposal remains `dispatch_eligible=false` and `execution=not_executed`.
- Readiness is not collected and execution authority is unavailable.
- No prompt, Agent, model, process, session, network, credential, quota, ledger, or project write occurs.

## Verification

- Focused tests cover determinism, plan drift, socket mismatch, handoff artifacts, path escape, Control Panel projection, and handoff replay arguments.
- Full regression, doctor, CLI/HTML smoke, public scan, pre-commit, and diff review are required before the milestone commit.

# Release Notes - Stage 75 Direction Reset and Documentation Convergence

> Date: 2026-07-26
> Status: included in v0.22.0 direction reset and docs convergence milestone

## Completed

- Froze the design for stronger `session_openable_no_turn` ACP evidence without implementing a probe.
- Consolidated the current multi-Agent goal, capabilities, gaps, Stage 75 boundary, and direction decision into `docs/123-multi-agent-control-hub-current-state-and-stage75-gate.md`.
- Archived completed Stage 67-74 detail documents `115` through `122` without deleting history.
- Reduced the current reading path to one multi-Agent fact source plus core architecture and execution-boundary documents.
- Changed the next milestone from deeper ACP probe work to a usable collaboration board and fixture-backed end-to-end walkthrough.

## Direction Decision

The socket-based multi-Agent control hub remains the correct goal. Stages 72-75 added relevant safety infrastructure, but continuing deeper would make the project infrastructure-led again. Product-visible collaboration workflows now take priority.

## Safety Boundary

Stage 75 starts no runner or process, opens no session, sends no prompt, invokes no model, reads no credentials, consumes no quota, and grants no dispatch authority.

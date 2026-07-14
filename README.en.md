# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

> A lightweight Agent Runtime / Harness Orchestrator for policy guardrails, task ledgers, agent registries, adapter boundaries, and completion verification, gradually evolving into a multi-agent, multi-tool, multi-channel orchestration hub.

## What This Project Is

`s-black harness engineering` is an agent engineering infrastructure project.

Its goal is not to replace the chat host or start with a UI. The first priority is to extract the parts of agent work that most need unified control:

- policy checks
- task ledgers
- agent registries
- adapter boundaries
- completion verification
- controlled write flows
- capability routing and orchestration foundations

The long-term goal is a **small, auditable, portable, pluggable runtime / control plane**, where QwenPaw is only one future host/adapter target rather than the only boundary.

## Big Picture

```text
User / CLI / Lark / Future UI
  -> Orchestration Hub / Control Plane
  -> Capability Routing
  -> Policy Guardrails / Approval / Completion Checks
  -> Agent & Tool Adapters
       -> QwenPaw
       -> Kimi Code / WebBridge
       -> Claude Code
       -> OMP / pi
       -> Shell
       -> GitHub
       -> Lark
       -> Obsidian
       -> Other external systems
  -> Task / Event / Run / Approval / Artifact State
  -> Report / Audit / Observability
```

In one sentence:

- **guardrails / ledgers / controlled writes** are the security core
- **unified integration / capability routing / control-plane state / future UI** are the larger orchestration-hub body this project is meant to grow into

## Where The Project Is Now

The repository now provides an **offline, auditable CLI/runtime security core suitable for internal trials**, with the Stage 12 control-plane read model accepted:

- it can already support policy validation, task/event ledgers, capability routing, dry-runs, controlled writes, and recovery-lineage auditing;
- Stage 13 resource/operation reconciliation and the Stage 14 replayable minimal orchestration loop are both complete;
- a local, deterministic, self-contained read-only Control Panel is now available; real adapter execution, persistent services/databases, authentication, and UI write operations remain unavailable, so this is not yet an auto-executing production orchestration hub.
- Stage 16 closure commit: `b46c013`; this closure has been pushed to `origin/main` with user authorization.

## Progress Bar

> This is a long-term project. The percentages below are **stage-completion estimates**, not code-volume metrics. They exist to answer one practical question: where are we now, and what comes next?

### Overall Progress (subjective engineering estimate)

```text
[███████████████░░░░░░░░░] about 60%
```

Current estimate:

- **Security and audit core**: about **80%**
- **Orchestration-hub backend abstractions**: about **55%**
- **UI / Control Panel readiness**: about **45%**

### Versioning Note

The latest milestone baseline is `v0.13.0-read-only-control-plane` (annotated tag, pushed), covering the Stage 13–16 backend boundary, replay, CLI automation, and static read-only Control Panel. The previous baseline is `v0.12.1-orchestration-read-loop-snapshot` (commit `0419a04`).

After `v0.11.0-runtime-event-import`, the project entered the orchestration line and effectively switched to **stage numbers + release-notes documents** for stage closure, such as `55`, `57`, `59`, `61`, `65`, `67`, and `72`. That means:

- stage closure did continue;
- semver / tags no longer advanced stage-by-stage;
- versioning moved to a "stage progression + release-notes closure + milestone tags" model.

The repository formalizes this through `docs/64-versioning-governance.md`. The policy has now been applied to `v0.12.0-orchestration-foundation`, `v0.12.1-orchestration-read-loop-snapshot`, and `v0.13.0-read-only-control-plane`:

- stage numbers continue to represent internal progression order;
- release-notes documents close individual stages;
- semver / Git tags are reserved for milestone-level freeze points rather than every stage;
- the current freeze baseline is `v0.13.0-read-only-control-plane`, adding the Stage 13–16 backend boundary, replay/recovery, CLI automation, and static read-only Control Panel on top of `v0.12.1`.

### Stage Closure Progress

- ✅ Stage 0 — Project skeleton
- ✅ Stage 1 — General policy model
- ✅ Stage 2 — Task ledger
- ✅ Stage 3 — Agent registry
- ✅ Stage 4 — Tool adapter layer (first-round design)
- ✅ Stage 5 — Minimal Runtime CLI
- ✅ Stage 6 — Runtime read-only checking chain
- ✅ Stage 7 — Controlled-write foundation
- ✅ Stage 8 — Runtime Event Import capability pack (v0.11)
- ✅ Stage 9 — Orchestration-hub positioning reset and blueprint
- 🟡 Stage 10 — Adapter Runtime Interface (source-backed registry projection v1 landed; continuing refinement)
- 🟡 Stage 11 — Capability Routing Model (constraint routing + decision trace v1 landed; continuing refinement)
- ✅ Stage 12 — Control Plane State Model (read-only loop, recovery lineage aggregation, and inspect/report consolidation completed final acceptance)
- ✅ Stage 13 — Backend-first API Boundary (resource/operation reconciliation and CLI contract tests completed)
- ✅ Stage 14 — Minimal orchestration-hub execution loop (seven-step loop, replay, and structured next action completed)
- 🟡 Stage 15 — Backend preparation before UI / dashboard (read-model CLI first version landed; interactive frontend still deferred)
- 🟡 Stage 15.5 — Orchestration controlled-write boundary (first controlled handoff / approval resolve landed)
- ✅ Stage 15.7 — Orchestration Run Dry-run landed
- ✅ Stage 15.8 — Orchestration Run Commit (A-only) landed
- ✅ Stage 15.9 — Orchestration Run Lifecycle Events landed
- ✅ Stage 15.95 — Orchestration Task Submit Created Event landed
- ✅ Stage 15.96 — Orchestration Run Retry / Fallback Dry-run landed
- ✅ Stage 15.97 — Orchestration Foundation Freeze completed (baseline: `38b4b69` / `v0.12.0-orchestration-foundation`)
- ✅ Stage 15.98 — Orchestration Run Retry / Fallback Commit landed
- ✅ Stage 15.99 — Run Lineage / Recovery single-run read models landed
- ✅ Stage 16 — Read-only Control Panel MVP (static snapshot/render closed; live UI deferred)

### The Most Accurate Current Read

The current state is best understood as:

- **guardrails / ledgers / controlled writes are no longer a sketch; they are already a formed security core**
- **the orchestration backend now has source-backed registry, constraint routing, read-loop snapshots, and recovery lineage aggregation v1**
- **real adapter execution, long-running services/APIs, interactive write-capable UI, and DB remain out of implementation scope**

### What Comes Next

No new product stage starts automatically:

1. treat **Stage 16 Read-only Control Panel MVP as complete**, with final acceptance recorded in `docs/archive/release-notes/79-release-notes-stage16-read-only-control-panel.md`
2. retain the local Task intent → routing → preflight → controlled commit → replay loop and structured next action
3. keep live service, authentication, database, real-time refresh, and UI write operations deferred until a concrete product or integration need exists
4. preserve the read-only, controlled-write, and no-real-adapter-execution boundaries

Implemented capability highlights:

- structure validation, secret scan, path checks, action preflight
- registry / policy / ledger queries and validation
- adapter execution envelope plan / validate / inspect / gate check
- `runtime draft export --dry-run / --commit`
- `runtime event append --dry-run / --commit`
- `runtime task create --dry-run / --commit`
- `runtime event import --dry-run / --commit`
- `runtime event import --expected-plan-hash` consistency freeze
- `runtime event import --require-dry-run` strict freeze mode
- controlled write regression coverage
- documentation backbone for orchestration-hub vision, adapter interface, capability routing, and control-plane state
- Stage 15 read-model CLI: `orchestration overview`, `orchestration task list/get`, `orchestration run list/inspect`, `orchestration approval list/get`, `orchestration artifact list/get`, `orchestration report generate`
- Stage 15.5 controlled handoff: `orchestration route preview`, `orchestration preflight`, controlled-write `orchestration approval resolve` (records decision only, does not execute original request)
- Stage 15.7/15.8/15.9 run controlled execution: `orchestration run --dry-run` (read-only plan preview + plan_hash), controlled-write `orchestration run --commit` (A+B envelope draft export + `run_planned` / `run_draft_exported` lifecycle events, no real adapter execution)
- Stage 12 post-freeze recovery read model: `orchestration run inspect --aggregate-lineage` / `orchestration report generate --aggregate-lineage` (aggregates root/latest/leaves, attempt count, and effective plan hash from existing lifecycle events; read-only and does not scan drafts)
- Stage 16 Read-only Control Panel: `orchestration control-panel snapshot/render` (deterministic snapshot, self-contained HTML, optional envelope-scoped run/approval/artifact projection, no service/network/write/execute)

## Current Boundaries

The runtime still keeps conservative boundaries:

- no real adapter execution
- no network access
- no message sending
- no reading `.env` / credential / token / keyring files
- no UI or background service
- no silent write-scope expansion

The implemented writes are all **controlled writes**: project-local safe paths only, explicit command trigger, pre-write validation, post-write validation, and rollback on failure.

## Quick Start

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
python -m agent_runtime.cli orchestration run inspect --task-id <task-id> --request-id <request-id> --envelope <envelope.json> --events-file tasks/events.jsonl --aggregate-lineage --json
```

For more CLI usage, see `docs/10-cli-poc-usage.md`.

## Recommended Reading

If this is your first time in the repository, read in this order:

1. `docs/00-index.md`
2. `docs/01-vision-and-boundaries.md`
3. `docs/02-roadmap.md`
4. `docs/47-orchestration-hub-vision.md`
5. `docs/48-adapter-runtime-interface.md`
6. `docs/49-capability-routing-model.md`
7. `docs/50-control-plane-state-model.md`
8. `docs/51-backend-first-api-boundary.md`
9. `docs/52-minimal-orchestration-loop.md`
10. `docs/53-minimal-orchestration-loop-cli-draft.md`
11. `docs/54-backend-preparation-before-ui.md`
12. `docs/55-release-notes-orchestration-read-models.md`
13. `docs/56-orchestration-controlled-write-boundary.md`
14. `docs/57-release-notes-orchestration-controlled-handoff.md`
15. `docs/58-orchestration-run-controlled-execution-design.md`
16. `docs/59-release-notes-orchestration-run-controlled-execution.md`
17. `docs/60-orchestration-run-lifecycle-events-design.md`
18. `docs/61-release-notes-orchestration-run-lifecycle-events.md`
19. `docs/62-orchestration-task-submit-controlled-write-design.md`
20. `docs/63-orchestration-task-submit-created-event-design.md`
21. `docs/64-versioning-governance.md`
22. `docs/65-release-notes-orchestration-task-submit-created-event.md`
23. `docs/66-orchestration-run-retry-fallback-design.md`
24. `docs/67-release-notes-orchestration-run-retry-fallback.md`
25. `docs/68-orchestration-foundation-milestone-freeze-checklist.md`
26. `docs/69-orchestration-foundation-freeze-execution-plan.md`
27. `docs/70-orchestration-run-retry-fallback-commit-design.md`
28. `docs/71-release-notes-run-lineage-read-models.md`
29. `docs/10-cli-poc-usage.md`
30. `docs/21-controlled-write-boundaries.md`

The documents `docs/47-orchestration-hub-vision.md` through `docs/54-backend-preparation-before-ui.md` form the orchestration-hub backend backbone; read them in numbered order.

If you only want the full progress ledger:

- `tasks/progress.md`

## Repository Layout

| Path | Purpose |
|:---|:---|
| `docs/` | architecture, roadmap, protocol notes, stage docs |
| `policies/` | policy schema and sample policies |
| `agents/` | agent registry schema and sample registry |
| `adapters/` | adapter design and related schemas |
| `tasks/` | task ledger schemas, samples, progress, handoff notes |
| `logs/` | future runtime logs |
| `decisions/` | architecture decision records |
| `notes/` | daily project notes |
| `assets/` | project visual assets |

## Continuous Integration

On push and pull request to `main`, GitHub Actions runs:

- `pytest`
- `doctor`
- ledger CLI smoke checks
- `public_scan`

See `.github/workflows/ci.yml` for details.

## Development Principle

Move in small, reviewable, reversible steps.

First stabilize the rules, state model, agent registry, adapter boundaries, and controlled-write core, then gradually expand unified integration, capability routing, control-plane state, and future UI-ready backend boundaries.

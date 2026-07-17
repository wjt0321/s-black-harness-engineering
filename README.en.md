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
- Stage 13–49 backend/read-model/controlled-write/host/display/readiness/audit/fixed-execution work is closed. The [Stage 50 operational recovery design](docs/99-fixed-execution-operational-recovery-design-gate.md) freezes a machine-local execution lease, identity-bound trust rotation, bounded open-attempt recovery, Windows Job accounting, and audit-v2 contract without expanding production execution permission. Generic adapter execution remains unavailable.
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

The latest milestone baseline is `v0.17.0-filtered-snapshot-display-host-integration` (pushed to `origin`), covering the Stage 39–40 validation-before-release one-shot Markdown display host. The previous baseline, `v0.16.0-filtered-snapshot-display-consumer`, has also been pushed to `origin`.

After `v0.11.0-runtime-event-import`, the project entered the orchestration line and effectively switched to **stage numbers + release-notes documents** for stage closure, such as `55`, `57`, `59`, `61`, `65`, `67`, and `72`. That means:

- stage closure did continue;
- semver / tags no longer advanced stage-by-stage;
- versioning moved to a "stage progression + release-notes closure + milestone tags" model.

The repository formalizes this through `docs/64-versioning-governance.md`. The policy has now been applied to `v0.12.0-orchestration-foundation`, `v0.12.1-orchestration-read-loop-snapshot`, `v0.13.0-read-only-control-plane`, `v0.14.0-filtered-snapshot-host-integration`, `v0.15.0-filtered-snapshot-display-integration`, `v0.16.0-filtered-snapshot-display-consumer`, and `v0.17.0-filtered-snapshot-display-host-integration`:

- stage numbers continue to represent internal progression order;
- release-notes documents close individual stages;
- semver / Git tags are reserved for milestone-level freeze points rather than every stage;
- the current freeze baseline is the local `v0.17.0-filtered-snapshot-display-host-integration`, adding validation-before-release and five-id cross-checking on top of the `v0.16.0` consumer.

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
- ✅ Stage 17 — Control Panel Host Integration Boundary
- ✅ Stage 18 — Independent Read-only Host Consumer Validation
- ✅ Stage 19 — Codex Desktop Read-only Adapter Design Gate
- ✅ Stage 20 — Codex Desktop One-shot Read-only Adapter
- ✅ Stage 21 — Representation Read Design Gate
- ✅ Stage 22 — Project-scoped Snapshot JSON Reader
- ✅ Stage 23/24 — Envelope-scoped Reader Design and Implementation
- ✅ Stage 25/26 — Consumer and Filter Design Gates
- ✅ Stage 27 — Filtered Envelope Snapshot JSON Reader v3
- ✅ Stage 28/29 — Filtered Snapshot Consumer Gate and Implementation
- ✅ Stage 30 — Filtered Snapshot Host Integration Gate
- ✅ Stage 31 — Validation-before-display One-shot Host Implementation
- ✅ Stage 32 — `v0.14.0-filtered-snapshot-host-integration` Milestone Freeze
- ✅ Stage 33 — Filtered Snapshot Display Integration Gate
- ✅ Stage 34 — Filtered Snapshot Markdown Display Implementation
- ✅ Stage 35 — `v0.15.0-filtered-snapshot-display-integration` Milestone Freeze (pushed)
- ✅ Stage 36 — Filtered Snapshot Markdown Display Consumer Validation Gate
- ✅ Stage 37 — Filtered Snapshot Markdown Display Consumer Implementation
- ✅ Stage 38 — `v0.16.0-filtered-snapshot-display-consumer` Milestone Freeze (pushed)
- ✅ Stage 39 — Filtered Snapshot Markdown Display Consumer Host Integration Gate
- ✅ Stage 40 — Filtered Snapshot Markdown Display Consumer Host Integration Implementation
- ✅ Stage 41 — `v0.17.0-filtered-snapshot-display-host-integration` Milestone Freeze (pushed)
- ✅ Stage 42 — Filtered Snapshot Validated Markdown Presentation Handoff Gate (design-only gate complete)
- ✅ Stage 43–45 — Single-user Real Execution Readiness (commit-level milestone complete; execution still blocked)
- ✅ Stage 46 — Fixed Git Status Executor Design Gate (design-only complete; Git was not executed)
- ✅ Stage 47 — Execution Lifecycle Audit Writer Design Gate
- ✅ Stage 48 — Execution Lifecycle Audit Writer Implementation (no CLI and no subprocess)
- ✅ Stage 49 — Fixed Git Status Executor Implementation and Limited Enablement (Windows only)
- ✅ Stage 50 — Fixed Execution Operational Recovery Design Gate (design only)
- ⏳ Stage 51 — Fixed Execution Operational Recovery Implementation (conditional)

### The Most Accurate Current Read

The current state is best understood as:

- **guardrails / ledgers / controlled writes are no longer a sketch; they are already a formed security core**
- **the orchestration backend now has source-backed registry, constraint routing, read-loop snapshots, and recovery lineage aggregation v1**
- **one Windows fixed `git_status` operation is enabled; generic adapters, POSIX execution, a second operation, and OS-enforced filesystem write protection remain blocked**
- **Stage 51 is not implemented; there is currently no recovery CLI, automatic retry, invalid-binding force repair, or additional real operation**

### What Comes Next

Stage 49 is complete on Windows for one fixed operation only. The operator first provisions a machine-local reviewed Git binding; execution then requires explicit `--commit`, exact `git status --short --branch`, pre/post repository guards, a suspended actual-image check, Job Object containment, bounded output, finite porcelain validation, and closed execution audit before a path-free summary is released. Stage 50 adds only a recovery design contract for a replacement-resistant single-flight lease, old-binding/full-candidate-bound rotation, input-bounded open-attempt handling, active-zero Job accounting, and future audit v2. POSIX, arbitrary commands, network adapters, and additional operations remain unavailable.


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
- Stage 17–31 read-only host chain: stdio handoff, independent consumers, project/envelope/filtered snapshot JSON reads, and `tools/codex_desktop_filtered_snapshot_host.py` validation-before-display one-shot integration

## Current Boundaries

The runtime still keeps conservative boundaries:

- no real adapter or external-command execution except the Windows fixed `git status --short --branch`
- no network access
- no message sending
- no reading `.env` / credential / token / keyring files
- no UI or background service
- no silent write-scope expansion

The implemented writes are all **controlled writes**: project-local safe paths only, explicit command trigger, pre-write validation, post-write validation, and rollback on failure.

## Quick Start

```bash
python -m agent_runtime.cli docs context --json
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

For a new session, recover the current stage first; there is no need to read the full history in sequence:

1. [`docs/000-stage-digest.md`](docs/000-stage-digest.md): current stage, stable baseline, and next step.
2. [`docs/99-fixed-execution-operational-recovery-design-gate.md`](docs/99-fixed-execution-operational-recovery-design-gate.md): authoritative Stage 50 design contract.
3. [`docs/98-fixed-git-status-executor-implementation-and-limited-enablement.md`](docs/98-fixed-git-status-executor-implementation-and-limited-enablement.md): the only real execution capability and its stop lines.
4. [`docs/97-execution-lifecycle-audit-writer-design-and-implementation.md`](docs/97-execution-lifecycle-audit-writer-design-and-implementation.md): execution audit writer source of truth.
5. [`tasks/handoff-2026-07-17.md`](tasks/handoff-2026-07-17.md): latest handoff and Stage 51 conditional boundary.
6. [`docs/02-roadmap.md`](docs/02-roadmap.md): complete stage roadmap.
7. [`docs/10-cli-poc-usage.md`](docs/10-cli-poc-usage.md): CLI flags and examples.

See [`docs/00-index.md`](docs/00-index.md) for the complete topic/archive map and [`tasks/progress.md`](tasks/progress.md) for the full progress ledger.

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
- controlled-write regression
- `public_scan`

See `.github/workflows/ci.yml` for details.

## Development Principle

Move in small, reviewable, reversible steps.

First stabilize the rules, state model, agent registry, adapter boundaries, and controlled-write core, then gradually expand unified integration, capability routing, control-plane state, and future UI-ready backend boundaries.

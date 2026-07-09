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

The repository has already moved from a read-only checking CLI to a minimal controlled-write runtime, and has now started to formalize the orchestration-hub backend blueprint.

## Progress Bar

> This is a long-term project. The percentages below are **stage-completion estimates**, not code-volume metrics. They exist to answer one practical question: where are we now, and what comes next?

### Overall Progress (subjective engineering estimate)

```text
[███████████████░░░░░░░░░] about 60%
```

Current estimate:

- **Security and audit core**: about **80%**
- **Orchestration-hub backend abstractions**: about **45%**
- **Future UI / Control Panel readiness**: about **20%**

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
- 🟡 Stage 10 — Adapter Runtime Interface (documented, needs further refinement)
- 🟡 Stage 11 — Capability Routing Model (documented, needs further refinement)
- 🟡 Stage 12 — Control Plane State Model (documented, needs further refinement)
- ⚪ Stage 13 — Backend-first API Boundary (context kept, not urgent yet)
- ⚪ Stage 14 — Minimal orchestration-hub execution loop
- ⚪ Stage 15 — Backend preparation before UI / dashboard
- ⚪ Stage 16 — UI / Control Panel

### The Most Accurate Current Read

The current state is best understood as:

- **guardrails / ledgers / controlled writes are no longer a sketch; they are already a formed security core**
- **the orchestration-hub backend line has completed its positioning reset and first batch of core documents**
- **true unified integration, routing, and control-plane operating boundaries have not yet entered an execution loop**

### What Comes Next

The most natural next direction is not to keep adding scattered features, but to:

1. keep refining the backend abstractions in **Stage 10-12**
2. keep **Stage 13** as prepared context, but not expand it yet
3. enter **Stage 14: the minimal orchestration-hub execution loop** at the right time
4. backfill guardrail gaps when new stages expose them

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
12. `docs/10-cli-poc-usage.md`
13. `docs/21-controlled-write-boundaries.md`

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

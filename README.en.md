# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

> A lightweight Agent Runtime / Harness Orchestrator for policy guardrails, task ledgers, agent registries, adapter boundaries, and completion verification.

## What This Project Is

`s-black harness engineering` is a long-term engineering project for extracting agent orchestration, policy checks, task tracking, tool adapters, and delivery verification out of a single host framework and into a small, auditable runtime layer.

It is not intended to replace QwenPaw immediately. The first phase focuses on documents, schemas, examples, and boundaries before any real runtime execution code is introduced.

## Relationship With QwenPaw

[QwenPaw](https://github.com/agentscope-ai/QwenPaw) is a public multi-agent desktop/runtime framework and an important host environment used during the early practice that shaped this project.

`s-black harness engineering` treats QwenPaw as one future host/adapter target, not as something to replace. This repository currently focuses on independent policies, ledgers, registries, and adapter-boundary design.

## Current Status

- Stage: read-only CLI POC plus Adapter execution envelope checks are runnable
- Created: 2026-07-02
- Current implementation: minimal read-only CLI for structure validation, secret scanning, path checks, action preflight, registry queries, ledger validation, adapter envelope plan / validate / inspect / approval check / response check / gate check, task + adapter envelope runtime plan (including `--draft-json` envelope draft output), runtime draft validate / inspect / export `--dry-run` / `--commit`, runtime event append `--dry-run` / `--commit`, runtime event import `--dry-run` / `--commit` (with `--expected-plan-hash` consistency freeze), runtime task create `--dry-run` / `--commit`, runtime gate check, runtime ledger audit, and runtime report
- Current boundary: adapter flows, runtime plan, runtime draft validate / inspect / gate / runtime ledger audit, runtime report, and runtime task create `--dry-run` remain read-only by default and do not execute real external actions; `runtime draft export --commit` only writes new files under `drafts/runtime/.../*.json`, does not overwrite, and rolls back on failure; `runtime event append --commit` appends exactly one line to an event ledger JSONL and rolls back to the original byte size on failure; `runtime event import --commit` appends a continuous block of candidate events to an existing event ledger JSONL and rolls back to the original byte size on post-check failure; `runtime task create --commit` appends exactly one line to a task ledger JSONL, rolls back to the original byte size on post-check failure, and does not write the event ledger

## Continuous Integration

On push and pull_request to `main`, GitHub Actions runs `pytest`, `doctor`, ledger CLI smoke checks, and `public_scan` against Python 3.11 and 3.12. See `.github/workflows/ci.yml`.

## Quick Start

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
```

See `docs/10-cli-poc-usage.md` for more usage details.

## Initial Scope

The runtime is expected to cover these areas over time:

1. **Agent registry**: track agents, capabilities, boundaries, workspaces, and handoff rules.
2. **Task routing**: decide which agent or tool should handle a task.
3. **Policy guardrails**: check risky actions before external publishing, deletion, configuration changes, or pushes.
4. **Tool adapters**: wrap QwenPaw, Kimi, Claude, OMP, Shell, Lark, GitHub, and WebBridge behind consistent interfaces.
5. **Task ledger**: record task state from planning through execution, blocking, failure, or completion.
6. **Completion verification**: require evidence before a task is marked finished.
7. **Memory and documentation handoff**: preserve important context in the right place instead of only in chat.

## Non-Goals For The First Phase

The first phase does not:

- Replace QwenPaw
- Provide a UI or desktop shell
- Start a long-running background service
- Take over existing scheduled jobs
- Implement a model proxy or billing system
- Silently execute real external operations before the design is stable

## Repository Layout

| Path | Purpose |
|:---|:---|
| `docs/` | Architecture, roadmap, protocol notes |
| `policies/` | Policy schema and sample policies |
| `agents/` | Agent registry schema and sample registry |
| `adapters/` | Future adapter designs or code |
| `tasks/` | Task ledger schemas, examples, progress, handoff notes |
| `logs/` | Future runtime logs |
| `decisions/` | Architecture decision records |
| `notes/` | Daily project notes |
| `assets/` | Project visual assets |

## Current Documents

- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `docs/03-policy-schema.md`
- `docs/04-task-state-model.md`
- `docs/05-agent-registry.md`
- `docs/06-adapter-layer.md`
- `docs/07-policy-task-bridge.md`
- `docs/08-minimal-cli-design.md`
- `docs/09-policy-checker-poc-plan.md`
- `docs/10-cli-poc-usage.md`
- `docs/11-release-notes-v0.1.md`
- `docs/12-adapter-execution-envelope.md`
- `docs/13-release-notes-adapter-envelope.md`
- `docs/14-task-runtime-bridge.md`
- `docs/15-runtime-ledger-audit.md`
- `docs/16-runtime-plan.md`
- `docs/17-runtime-planning-bridge.md`
- `docs/18-release-notes-runtime-planning-bridge.md`
- `docs/19-runtime-report.md`
- `docs/20-release-notes-runtime-report.md`
- `docs/21-controlled-write-boundaries.md`
- `docs/22-runtime-draft-export-dry-run.md`
- `docs/23-release-notes-runtime-draft-export-dry-run.md`
- `docs/24-runtime-draft-export-commit.md`
- `docs/25-release-notes-runtime-draft-export-commit.md`
- `docs/26-runtime-event-append-dry-run.md`
- `docs/27-release-notes-runtime-event-append-dry-run.md`
- `docs/28-runtime-event-append-commit.md`
- `docs/29-release-notes-runtime-event-append-commit.md`
- `docs/30-runtime-event-append-smoke.md`
- `docs/31-runtime-task-create-dry-run.md`
- `docs/32-release-notes-runtime-task-create-dry-run.md`
- `docs/33-runtime-task-create-commit.md`
- `docs/34-release-notes-runtime-task-create-commit.md`
- `docs/35-runtime-task-create-smoke.md`
- `docs/36-controlled-write-regression.md`
- `docs/37-runtime-event-import-dry-run.md`
- `docs/38-release-notes-runtime-event-import-dry-run.md`
- `docs/39-runtime-event-import-commit-design.md`
- `docs/40-release-notes-runtime-event-import-commit.md`
- `docs/41-runtime-event-import-consistency-freeze.md`
- `docs/42-release-notes-runtime-event-import-consistency-freeze.md`
- `docs/43-controlled-write-regression-event-import.md`
- `docs/44-release-notes-v0.11-runtime-event-import.md`

## Development Principle

Move in small, reviewable steps. Define the rules, task model, agent registry, adapter boundaries, and completion checks before implementing executable runtime code.

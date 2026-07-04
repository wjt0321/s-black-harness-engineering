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
- Current implementation: minimal read-only CLI for structure validation, secret scanning, path checks, action preflight, registry queries, ledger validation, and adapter envelope plan / validate / inspect / approval check / response check / gate check
- Current boundary: adapter flows remain read-only and do not execute real external actions

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

## Development Principle

Move in small, reviewable steps. Define the rules, task model, agent registry, adapter boundaries, and completion checks before implementing executable runtime code.

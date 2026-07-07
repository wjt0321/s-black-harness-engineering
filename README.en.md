# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

> A lightweight Agent Runtime / Harness Orchestrator for policy guardrails, task ledgers, agent registries, adapter boundaries, and completion verification.

## What This Project Is

`s-black harness engineering` is an agent engineering infrastructure project.

Its goal is not to replace the chat host or start with a UI. Instead, it extracts the parts of agent work that most need hard boundaries:

- policy checks
- task ledgers
- agent registries
- adapter boundaries
- completion verification
- controlled write flows

The long-term goal is a **small, auditable, portable runtime layer**, where QwenPaw is only one future host/adapter target rather than the only boundary.

## Where The Project Is Now

The repository has already moved from a read-only checking CLI to a minimal controlled-write runtime.

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
3. `docs/10-cli-poc-usage.md`
4. `docs/21-controlled-write-boundaries.md`
5. `docs/45-runtime-event-import-strict-freeze-mode.md`
6. `docs/46-release-notes-runtime-event-import-strict-freeze.md`

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

Define the rules, task model, agent registry, adapter boundaries, and completion checks first, then gradually expand executable runtime capability.

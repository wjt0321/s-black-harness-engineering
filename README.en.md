# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

A lightweight, auditable Agent Runtime / Harness Orchestrator. It separates policy gates, ledgers, capability routing, controlled writes, execution audit, and host integration from the chat host into a testable local control plane.

## Current Status

Stage 62 is complete. The repository exposes exactly two limited real-execution operations on Windows:

- fixed Git status: only `git status --short --branch`;
- fixed Pi print: only `pi --print --no-session --no-tools <prompt>`, validated by a real DeepSeek smoke test.

Both require explicit `--commit` and are guarded by a machine-local lease, fixed arguments, bounded validation, started/terminal audit events, and Windows Job Object process-tree cleanup. Pi results expose only digests, byte counts, and audit evidence; prompts, model text, and credentials remain withheld.

The repository also provides policy and registry checks, task/event/run read models, controlled ledger writes with rollback, capability routing, workflow/profile/contract validation, a static read-only Control Panel pipeline, and Pi preflight/approval/postflight host primitives.

## Security Boundary

The project does not currently provide:

- a general shell or arbitrary adapter execution;
- POSIX real execution;
- network adapters, long-running services, databases, or automatic background jobs;
- Pi read/write/edit/bash tool authority;
- silent access to `.env`, tokens, keyrings, or credential files;
- a third real operation without a separate design gate and authorization.

## Quick Start

```bash
pip install -e .[dev]
python -m agent_runtime.cli doctor
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli --help
```

Validation:

```bash
python -m pytest tests -q
python tools/public_scan.py
python -m agent_runtime.cli doctor
git diff --check
```

See [`docs/10-cli-poc-usage.md`](docs/10-cli-poc-usage.md) for the full CLI reference.

## Documentation

- [`docs/000-stage-digest.md`](docs/000-stage-digest.md): current state and recovery order.
- [`docs/00-index.md`](docs/00-index.md): topic-based navigation.
- [`docs/02-roadmap.md`](docs/02-roadmap.md): completed capability packages and next candidates.
- [`docs/111-pi-controlled-dry-run-print-implementation.md`](docs/111-pi-controlled-dry-run-print-implementation.md): latest real-execution fact source.
- [`docs/archive/`](docs/archive/): historical designs, plans, smoke reports, and release notes.

## Repository Layout

| Path | Purpose |
|:---|:---|
| `agent_runtime/` | Python package, CLI, and control-plane logic |
| `tests/` | pytest suite |
| `docs/` | current architecture, policies, and usage entry points |
| `docs/archive/` | completed stages and historical snapshots |
| `adapters/`, `agents/`, `policies/` | sample registries and policies |
| `tasks/` | sample ledgers, handoffs, and progress records |
| `integrations/` | host integration examples |

Version governance is documented in [`docs/64-versioning-governance.md`](docs/64-versioning-governance.md).

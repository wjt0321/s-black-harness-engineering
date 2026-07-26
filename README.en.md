# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

An auditable multi-Agent collaboration control hub. Kimi Code, Claude Code, OMP/Pi, and QwenPaw agents are replaceable plugs; the project provides shared sockets, task decomposition, capability routing, handoffs, reviews, evidence, and operator boundaries so their work can ultimately be observed and controlled from one board.

## Current Status

Stage 78 is complete. The repository now provides:

- a shared Agent socket registry, capability routing, and explicit role bindings;
- validated multi-Agent collaboration plans with work items, dependencies, handoffs, artifacts, and review gates;
- a Chinese-first Control Panel with a manual collaboration fixture, work lanes, and a handoff/artifact timeline;
- an in-memory manual plan editor with structure, dependency, Agent socket binding, and review validation;
- an `editing -> validated -> operator_confirmed` confirmation state machine;
- user-triggered copy and download of collaboration plan v1 candidate JSON;
- single-work-item dispatch proposals, ACP readiness evidence foundations, and audit boundaries.

The board still cannot start a real Kimi, Claude, or OMP collaboration. Validation, operator confirmation, copy, and download never grant dispatch authority; the boundary remains `dispatch_eligible=false` and `execution=not_executed`. The next product milestone is **Stage 79 collaboration run state model design**: define start, cancel, retry, review, handoff, blocked recovery, and artifact collection without invoking an Agent.

Two limited Windows real-execution operations remain available underneath: fixed Git status and fixed Pi print. Both use explicit authorization, fixed arguments, a machine-local lease, execution audit, and Windows Job Object process-tree containment. They are security infrastructure, not the product mainline.

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
- [`docs/126-stage78-manual-confirmation-and-controlled-export.md`](docs/126-stage78-manual-confirmation-and-controlled-export.md): current fact source for manual validation, operator confirmation, and controlled export.
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

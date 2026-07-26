# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

An auditable multi-Agent collaboration control hub. Kimi Code, Claude Code, OMP/Pi, and QwenPaw agents are replaceable plugs; the project provides shared sockets, task decomposition, capability routing, handoffs, reviews, evidence, and operator boundaries so their work can ultimately be observed and controlled from one board.

## Current Status

Stage 81 is complete. The repository now provides:

- a shared Agent socket registry, capability routing, and explicit role bindings;
- validated multi-Agent collaboration plans with work items, dependencies, handoffs, artifacts, and review gates;
- a Chinese-first Control Panel with a manual collaboration fixture, work lanes, and a handoff/artifact timeline;
- an in-memory manual plan editor with structure, dependency, Agent socket binding, and review validation;
- an `editing -> validated -> operator_confirmed` confirmation state machine;
- user-triggered copy and download of collaboration plan v1 candidate JSON;
- a fixture-backed collaboration run state, continuous event replay, retries, reviews, handoffs, blocked recovery, and artifact collection;
- checkpoint action eligibility, exact fixture approval bindings, and non-executable idempotent command candidates;
- a current operator inbox that only aggregates latest attempts/reviews/handoffs, pending approvals, and stable stale-target reasons;
- Chinese Control Panel run/action/inbox projections with operator controls permanently disabled;
- single-work-item dispatch proposals, ACP readiness evidence foundations, and audit boundaries.

The board still cannot start a real Kimi, Claude, or OMP collaboration. Even when the current inbox reports `action_eligible=true`, it remains `execution_authorized=false`, `dispatch_eligible=false`, and `execution=not_executed`. The next product milestone is **Stage 82 safety review and read-only contract closure before real approval-ledger integration**: review the authorization boundary between fixture approvals, the current inbox, and any future real binding without reading a real ledger or invoking an Agent.

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
- [`docs/129-stage81-current-operator-inbox-and-approval-collection.md`](docs/129-stage81-current-operator-inbox-and-approval-collection.md): current fact source for the operator inbox, approval collection, stale-target blocking, and the read-only control projection.
- [`docs/00-index.md`](docs/00-index.md): topic-based navigation.
- [`docs/02-roadmap.md`](docs/02-roadmap.md): completed capability packages and next candidates.
- [`docs/111-pi-controlled-dry-run-print-implementation.md`](docs/111-pi-controlled-dry-run-print-implementation.md): latest real-execution fact source.
- [`docs/113-pi-runtime-binding-implementation.md`](docs/113-pi-runtime-binding-implementation.md): current binding-only review-evidence source; it does not authorize runner migration or execution.
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

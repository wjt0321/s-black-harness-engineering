# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

An auditable multi-Agent collaboration control hub. Kimi Code, Claude Code, OMP/Pi, and QwenPaw agents are replaceable plugs; the project provides shared sockets, task decomposition, capability routing, handoffs, reviews, evidence, and operator boundaries so their work can ultimately be observed and controlled from one board.

The target product is a GUI-first, local-first control plane for external Agents, not another chat Agent or a CLI/TUI-first tool. The Harness owns plans, state, approvals, handoffs, reviews, artifacts, audit, and recovery, while Claude, Kimi, OMP/Pi, QwenPaw, and future Agents keep ownership of their native models, sessions, and tools.

## Current Status

Stage 87 is complete and archived. The repository now provides:

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
- single-work-item dispatch proposals, ACP readiness evidence foundations, and audit boundaries;
- a transport-neutral External Agent adapter contract, a 25-code failure matrix, and a bounded GUI live-read-model fixture;
- the first `omp-acp` read-only live-status reader, with a fixed atomic snapshot, a 15-second TTL, bounded stable reads, exact identity/producer binding, normalized evidence, and fail-closed GUI mapping;
- project-local in-process Pi/OMP status extensions, a single-writer lease, atomic publication, and a Chinese Control Panel external-agent live-status section;
- one-time-approved single-work-item dispatch to an already-open, idle, tool-free Pi/OMP session, with bounded result collection and closed execution audit.

The Harness still does not start, stop, or restart Kimi, Claude, Pi, or OMP. Stage 87 has completed real Pi/OMP acceptance for one explicitly approved fixed work item. Dispatch fails closed when tools are active, the host is busy, evidence drifts, the request times out, or the result is unsafe.

Three constrained real capabilities are available: fixed Git status, fixed Pi print, and fixed single-work-item dispatch to Pi/OMP. All require explicit commit, fixed inputs, a machine-local lease, and execution audit. Process-based operations retain Windows Job Object containment; single-work-item dispatch does not expose arbitrary commands or Agent tools.

## Security Boundary

The project does not currently provide:

- a general shell or arbitrary adapter execution;
- POSIX real execution;
- network adapters, long-running services, databases, or automatic background jobs;
- Pi read/write/edit/bash tool authority;
- silent access to `.env`, tokens, keyrings, or credential files;
- any additional real operation without a separate design gate and authorization;
- starting, stopping, or restarting external Agents from the Harness;
- dispatch without one-time approval, multiple work items, automatic retry, parallel dispatch, or autonomous loops.

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
- [`docs/130-gui-first-external-agent-control-plane-target.md`](docs/130-gui-first-external-agent-control-plane-target.md): durable GUI-first external-Agent target, MVP boundary, and anti-drift checklist.
- [`docs/archive/136-stage87-single-work-item-controlled-execution.md`](docs/archive/136-stage87-single-work-item-controlled-execution.md): the archived Stage 87 fact source for controlled Pi/OMP single-work-item execution and real acceptance.
- [`docs/archive/135-stage86-pi-omp-live-status-integration.md`](docs/archive/135-stage86-pi-omp-live-status-integration.md): the archived Stage 86 fact source for read-only Pi/OMP status integration.
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

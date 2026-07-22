# Stage 51 Fixed Execution Operational Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the frozen Stage 50 operational recovery contract without expanding the single Windows fixed Git status execution authority.

**Architecture:** Add one machine-local execution lease shared by fixed execution, trust writes, and recovery closure; replace unbounded execution-audit reads with one bounded snapshot contract; add dedicated trust/recovery projections and a fixed outcome-unknown closure. Preserve historical `execution-audit/v1` and add v2 only for Job accounting evidence required by new fixed executions.

**Tech Stack:** Python 3.11+, pathlib, Win32 APIs through ctypes, JSON Schema 2020-12, JSONL ledgers, pytest.

---

### Task 1: Machine-local execution lease

**Files:**
- Create: `agent_runtime/execution_lease.py`
- Create: `tests/test_execution_lease.py`
- Modify: `agent_runtime/execution_trust.py`
- Modify: `agent_runtime/orchestration_git_status_execution.py`

1. Write failing tests for fixed location, read-only inspection, atomic persistent creation, contention, identity replacement, noninheritance, project overlap, unsafe file shape, and release.
2. Run `python -m pytest tests/test_execution_lease.py -q` and confirm RED from the missing API.
3. Implement the minimal injectable lease backend and Windows production backend.
4. Integrate one held lease around trust commit/rotation and the complete fixed execution lifecycle.
5. Run lease, trust, Git status execution, and controlled-write tests.
6. Commit the isolated task.

### Task 2: Bounded audit snapshot and v1/v2 compatibility

**Files:**
- Create: `agent_runtime/bounded_ledger.py`
- Create: `tests/test_bounded_execution_audit.py`
- Create: `tasks/execution-audit-event-v2.schema.json`
- Modify: `tasks/execution-audit-event.schema.json`
- Modify: `agent_runtime/execution_audit_writer.py`
- Modify: `agent_runtime/task_validation.py`
- Modify: `agent_runtime/doctor.py`
- Modify: `tests/test_execution_audit_writer.py`

1. Write failing tests for 16 MiB file, 50,000 line/record, 64 KiB line, depth-32, strict UTF-8, duplicate keys, identity drift, and no partial result.
2. Write failing schema tests proving v1 remains valid, v2 success requires all six Job fields, and mixed-version chains fail.
3. Run the focused tests and confirm RED.
4. Implement one streaming bounded snapshot and route all execution audit validation/preflight/post-check through it.
5. Add version-dispatched validation; keep v1 unchanged and use a distinct v2 schema.
6. Run audit writer, task validation, doctor, and controlled-write tests.
7. Commit the isolated task.

### Task 3: Trust inspection and reviewed rotation binding

**Files:**
- Modify: `agent_runtime/execution_trust.py`
- Modify: `agent_runtime/cli.py`
- Modify: `tests/test_execution_trust.py`
- Modify: `tests/test_cli.py`

1. Write failing tests for missing/current/drifted/invalid/candidate-unavailable/platform-unavailable and value-safe output.
2. Write failing tests requiring expected old binding ID and exact new executable/PATH identities for replace commit under the shared lease.
3. Run focused tests and confirm RED.
4. Implement read-only trust inspection without creating lease/binding state.
5. Implement lease-scoped rediscovery and expected identity checks for commit/rotation.
6. Add `orchestration execution trust inspect` without path or actor overrides.
7. Run focused tests and commit.

### Task 4: Open-attempt inspection and fixed recovery close

**Files:**
- Create: `agent_runtime/orchestration_execution_recovery.py`
- Create: `tests/test_orchestration_execution_recovery.py`
- Modify: `agent_runtime/execution_audit_writer.py`
- Modify: `agent_runtime/cli.py`
- Modify: `agent_runtime/orchestration_contract.py`
- Modify: `tests/test_orchestration_contract.py`
- Modify: `tests/test_orchestration_boundary_contract.py`

1. Write failing tests for bounded deterministic open list, 128-result cap, safe inspect semantics, invalid/missing states, and no-write behavior.
2. Write failing tests for preview, lease-scoped commit, expected started ID/plan hash binding, fixed terminal shape, rollback, stale preview, and result withholding.
3. Run focused tests and confirm RED.
4. Implement dedicated recovery projections and a recovery-only terminal writer with no caller-supplied event/evidence surface.
5. Add `list-open`, `inspect`, and `close-open` CLI commands and versioned contract entries.
6. Run focused, CLI, contract, audit, and controlled-write tests.
7. Commit the isolated task.

### Task 5: Windows Job accounting and audit v2 release gate

**Files:**
- Modify: `agent_runtime/fixed_process_runner.py`
- Modify: `agent_runtime/orchestration_git_status_execution.py`
- Modify: `agent_runtime/execution_audit_writer.py`
- Modify: `tests/test_fixed_process_runner.py`
- Modify: `tests/test_orchestration_git_status_execution.py`
- Modify: `tests/test_execution_audit_writer.py`

1. Write failing fake-backend tests for active-zero success, active-nonzero cleanup/requery, query failure, unreaped child, invalid counts, and containment-close failure.
2. Run focused tests and confirm RED.
3. Implement synchronous Job accounting after child reap/readers and before containment close.
4. Withhold all output unless active zero, direct child reaped, accounting passed, and containment closed.
5. Write new fixed execution audit events as v2 and require accounting evidence for success; preserve v1 recovery compatibility.
6. Run focused runner/executor/audit tests and controlled-write regression.
7. Commit the isolated task.

### Task 6: Stage 51 closure and milestone integration

**Files:**
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/progress.md`
- Create: `docs/100-fixed-execution-operational-recovery-implementation.md`
- Create: `docs/archive/release-notes/110-release-notes-stage51-fixed-execution-operational-recovery.md`
- Create: `tasks/handoff-2026-07-22.md`

1. Update current-stage facts, CLI usage, recovery boundaries, verification evidence, and next conditional stage without claiming broader execution authority.
2. Run `python -m pytest tests -q`.
3. Run `python -m agent_runtime.cli doctor`.
4. Run `python tools/public_scan.py`.
5. Run `python -m pytest tests/test_controlled_write_regression.py -q`.
6. Run `python -m compileall -q agent_runtime tests tools`.
7. Run `python -m agent_runtime.cli docs context --json`.
8. Run `git diff --check` and `bash .githooks/pre-commit`.
9. Request final security/spec/code-quality review and fix every Critical or Important finding.
10. Create the local Stage 51 milestone commit, merge it into `main`, rerun verification on `main`, then remove the worktree and feature branch.

Real Git status smoke remains skipped unless separately authorized through its existing environment gate. No push or tag is part of this plan.

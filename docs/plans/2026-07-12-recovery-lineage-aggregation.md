# Recovery Lineage Aggregation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic, read-only recovery lineage aggregation view to `orchestration run inspect --aggregate-lineage`.

**Architecture:** Build a standalone `orchestration_recovery.py` projection over existing run lifecycle events. Attach its safe result to `RunInspectResult` only when explicitly requested, preserving default output compatibility and all no-execution/no-write boundaries.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, argparse, pytest.

---

### Task 1: Freeze the read-model contract

**Files:**
- Create: `docs/73-recovery-lineage-aggregation-read-model.md`
- Modify: `docs/00-index.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/02-roadmap.md`

1. Document the ledger-backed data source, deterministic ordering, branch semantics, validation failures, and safety boundary.
2. Add the active document to the index and make Stage 12 post-freeze wording authoritative.
3. Run `python -m agent_runtime.cli doctor` and expect PASS.

### Task 2: Add core aggregation tests

**Files:**
- Create: `tests/test_orchestration_recovery.py`

1. Write failing tests for a normal run, retry/fallback chain, branch ambiguity, missing/cross-task parent, cycle, and duplicate metadata conflict.
2. Run `python -m pytest tests/test_orchestration_recovery.py -q` and verify collection/import fails before production code exists.

### Task 3: Implement the recovery projection

**Files:**
- Create: `agent_runtime/orchestration_recovery.py`

1. Add safe result/node dataclasses and `aggregate_recovery_lineage`.
2. Load existing lifecycle events read-only, merge request records, validate lineage, resolve root/descendants/leaves, and produce stable output.
3. Run the focused tests until green, then refactor without changing behavior.

### Task 4: Integrate run inspect CLI with TDD

**Files:**
- Modify: `agent_runtime/orchestration_run.py`
- Modify: `agent_runtime/cli.py`
- Modify: `tests/test_orchestration_run_inspect.py`

1. Add failing JSON/human/default-compatibility tests for `--aggregate-lineage`.
2. Add the parser flag and optional aggregation call.
3. Serialize `recovery_lineage` only when requested and render a compact human summary.
4. Run focused inspect and recovery tests.

### Task 5: Documentation and verification

**Files:**
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `tasks/progress.md`

1. Add CLI usage and progress entry.
2. Run `python -m pytest tests -q`.
3. Run `python -m agent_runtime.cli doctor`.
4. Run `python tools/public_scan.py`.
5. Run `git diff --check`.
6. Review that no target, payload, secret, timestamp-dependent ordering, write path, or network behavior was introduced.

# Recovery Lineage Report Reuse Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reuse the existing recovery lineage aggregation in `orchestration report generate` behind an explicit compatibility-preserving flag.

**Architecture:** Extend `ReportGenerateResult` with an optional `RecoveryLineageResult`, invoke the existing `aggregate_recovery_lineage` only when requested, and render the same compact summary used by run inspect. Keep run list unchanged because its envelope-scoped collection contract is not compatible with implicit ledger aggregation.

**Tech Stack:** Python 3.11+, argparse, dataclasses, pytest.

---

### Task 1: Lock the report reuse contract with failing tests

**Files:**
- Modify: `tests/test_orchestration_report.py`

**Steps:**
1. Add JSON test asserting `recovery_lineage` appears only with `--aggregate-lineage`.
2. Add human test asserting root/latest/attempt count are rendered safely.
3. Add validation-failure test asserting missing focus raises overall status to `validation_failed`.
4. Run the new tests and verify they fail because the flag is not accepted.

### Task 2: Implement the minimal report integration

**Files:**
- Modify: `agent_runtime/orchestration_report.py`
- Modify: `agent_runtime/cli.py`

**Steps:**
1. Add optional `recovery_lineage` to `ReportGenerateResult.to_dict()`.
2. Add `aggregate_lineage=False` to `generate_report`, invoke the existing aggregator only when true, and merge status with the same precedence as run inspect.
3. Add the parser flag, pass it through the command handler, and render a compact human summary.
4. Run report/recovery tests and verify they pass.

### Task 3: Update authoritative documentation and verify

**Files:**
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/73-recovery-lineage-aggregation-read-model.md`
- Modify: `docs/00-index.md`
- Modify: `tasks/handoff-2026-07-12-recovery-lineage-aggregation.md`
- Modify: `tasks/progress.md`
- Modify: `AGENTS.md`

**Steps:**
1. Document the explicit report flag and the decision to defer run list integration.
2. Run targeted tests, full pytest, doctor, public scan, compileall, diff check, and docs hook.
3. Commit the implementation and documentation.

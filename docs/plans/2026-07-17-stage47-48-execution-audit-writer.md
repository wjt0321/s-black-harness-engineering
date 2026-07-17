# Stage 47–48 Execution Audit Writer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Freeze and implement a dedicated controlled writer for reserved execution lifecycle events without enabling subprocess execution.

**Architecture:** Add a strict execution-audit event schema and an internal-only writer that constructs started/terminal events, appends one line with byte-size rollback, validates the resulting ledger, and exposes a read-only recovery view. Keep the shared event schema compatible, while explicitly blocking reserved types in generic append/import paths.

**Tech Stack:** Python 3.11+, `jsonschema`, pathlib, dataclasses, pytest, existing `CheckResult`/`Finding` and controlled-write helpers.

---

### Task 1: Freeze Stage 47 contract

**Files:**
- Create: `docs/97-execution-lifecycle-audit-writer-design-and-implementation.md`
- Create: `docs/plans/2026-07-17-stage47-48-execution-audit-writer.md`

**Step 1: Record design alternatives**

Document and reject shared-enum-only and caller-supplied provenance approaches. Adopt a dedicated schema, internal writer API, generic-entry rejection, separate started/terminal append transactions, and safe recovery states.

**Step 2: Check documentation formatting**

Run:

```bash
git diff --check
```

Expected: exit `0`.

### Task 2: Freeze reserved schema and generic-entry rejection

**Files:**
- Create: `tasks/execution-audit-event.schema.json`
- Modify: `tasks/event.schema.json`
- Modify: `agent_runtime/runtime_event_append.py`
- Modify: `agent_runtime/runtime_event_import.py`
- Modify: `agent_runtime/doctor.py`
- Test: `tests/test_execution_audit_writer.py`
- Test: `tests/test_runtime_event_append_commit.py`
- Test: `tests/test_runtime_event_import_dry_run.py`

**Step 1: Write failing schema and rejection tests**

Assert four reserved types are accepted by the shared schema, the dedicated schema requires fixed provenance and rejects extra/raw fields, and generic append/import return `blocked` with `reserved-execution-event-type` without changing ledger bytes.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_execution_audit_writer.py tests/test_runtime_event_append_commit.py tests/test_runtime_event_import_dry_run.py -q
```

Expected: FAIL because the dedicated schema and reserved rejection do not exist.

**Step 3: Implement minimal schema and rejection**

Add the four enum values, strict dedicated schema, doctor registration, a shared reserved-type constant/helper, and explicit append/import preflight rejection.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 3: Implement started writer with rollback

**Files:**
- Create: `agent_runtime/execution_audit_writer.py`
- Modify: `tests/test_execution_audit_writer.py`
- Modify: `tests/test_controlled_write_regression.py`

**Step 1: Write failing started tests**

Cover happy path, generated event/attempt ids, fixed actor/origin/version/message/phase, safe result, unknown task, invalid plan hash, missing/unsafe ledger, newline guard, write failure, post-check rollback, rollback failure, and no subprocess/network imports.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_execution_audit_writer.py tests/test_controlled_write_regression.py -q
```

Expected: FAIL because the writer module/API does not exist.

**Step 3: Implement minimal started append**

Reuse project-local ledger path checks and byte-size rollback behavior, but construct the event internally and validate both shared and dedicated schemas plus task/event and audit consistency.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 4: Implement terminal writer and recovery validation

**Files:**
- Modify: `agent_runtime/execution_audit_writer.py`
- Modify: `tests/test_execution_audit_writer.py`
- Modify: `tests/test_controlled_write_regression.py`

**Step 1: Write failing terminal/recovery tests**

Cover succeeded/failed/cancelled phase mapping, terminal references, matching identities, duplicate/missing/terminal-only chains, open and closed recovery states, terminal post-check rollback preserving started, and audit-incomplete output.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_execution_audit_writer.py tests/test_controlled_write_regression.py -q
```

Expected: FAIL on terminal and recovery behavior.

**Step 3: Implement terminal and read-only validator**

Add attempt aggregation, strict chain validation, safe inspection states, terminal construction, single-line append, post-check, and terminal-only rollback.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 5: Preserve historical readiness and close Stage 48

**Files:**
- Modify: `agent_runtime/orchestration_execution_readiness.py`
- Modify: `tests/test_orchestration_execution_readiness.py`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/64-versioning-governance.md`
- Modify: `docs/97-execution-lifecycle-audit-writer-design-and-implementation.md`
- Create: `docs/archive/release-notes/107-release-notes-stage47-stage48-execution-audit-writer.md`
- Create: `tasks/handoff-2026-07-17.md`
- Modify: `tasks/progress.md`

**Step 1: Add failing historical compatibility test**

Assert Stage 44 readiness v1 still reports 10 design checks pass and three historical implementation gaps blocked even after the new reserved schema exists.

**Step 2: Run RED test**

```bash
python -m pytest tests/test_orchestration_execution_readiness.py -q
```

Expected: FAIL because the old pre-execution enum check sees the new terminal event names.

**Step 3: Implement compatibility rule and update docs**

Keep `execution_started` absent and preserve v1 as a permanent historical snapshot. Mark Stage 47/48 complete, keep Stage 49 conditional/unavailable, and do not create a tag.

**Step 4: Run focused regression**

```bash
python -m pytest tests/test_execution_audit_writer.py tests/test_runtime_event_append_dry_run.py tests/test_runtime_event_append_commit.py tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_orchestration_execution_readiness.py tests/test_controlled_write_regression.py -q
```

Expected: PASS.

**Step 5: Run full verification**

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

Expected: every command exits `0`.

**Step 6: Commit locally**

```bash
git add AGENTS.md README.md README.en.md agent_runtime docs tasks tests
git commit -m "Complete execution lifecycle audit writer milestone"
```

Do not push or create a tag.

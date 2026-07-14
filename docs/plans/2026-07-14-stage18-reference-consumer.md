# Stage 18 Local Reference Consumer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standard-library-only stdin consumer that independently validates the Stage 17 Control Panel handoff contract without reading representations or executing argv.

**Architecture:** Add one standalone module under `tools/` with no imports from `agent_runtime`. It reads at most 1 MiB from binary stdin, rejects ambiguous JSON, validates the public v1 descriptor and its content hashes, and emits a deterministic validation JSON result. Tests may use the producer to create valid fixtures, but consumer validation remains implementation-independent.

**Tech Stack:** Python 3.11+ standard library (`dataclasses`, `hashlib`, `json`, `pathlib`, `re`, `sys`, `typing`) and pytest.

---

### Task 1: Freeze the valid consumer result contract

**Files:**
- Create: `tests/test_control_panel_handoff_consumer.py`
- Create: `tools/control_panel_handoff_consumer.py`

**Step 1: Write the failing happy-path test**

Create a producer fixture with `build_control_panel_handoff(ROOT, envelope_file=ENVELOPE).to_dict()`. Call `validate_handoff_document()` and assert the exact output field order, schema `control-plane/control-panel-host-consumer-validation/v1`, consumer id, source handoff id, ordered checks, guarantees, next action, status `pass`, and exit code `0`.

**Step 2: Run the test to verify RED**

Run:

```bash
python -m pytest -p no:cacheprovider tests/test_control_panel_handoff_consumer.py::test_reference_consumer_accepts_valid_handoff -q
```

Expected: FAIL because `tools.control_panel_handoff_consumer` does not exist.

**Step 3: Implement the minimal result model and happy-path validator**

Add constants, `ConsumerFinding`, `ConsumerValidationResult`, canonical SHA-256 helper, ordered check ids, exact v1 field sets, and `validate_handoff_document(document)` with the minimum checks required by the happy-path test. Do not add stdin handling yet.

**Step 4: Run the happy-path test to verify GREEN**

Run the same pytest command. Expected: PASS.

**Step 5: Commit**

```bash
git add tools/control_panel_handoff_consumer.py tests/test_control_panel_handoff_consumer.py
git commit -m "Add Stage 18 handoff consumer contract"
```

### Task 2: Freeze strict shape, identity, and safety rejection

**Files:**
- Modify: `tests/test_control_panel_handoff_consumer.py`
- Modify: `tools/control_panel_handoff_consumer.py`

**Step 1: Write failing parameterized tests**

Cover:

- unknown top-level field and missing required field;
- wrong nested field type;
- unsupported handoff schema;
- handoff id mismatch;
- render id mismatch;
- snapshot/render metadata drift;
- argv not a list or containing a non-string;
- unsafe boundary flag;
- absolute/project-escaping source path;
- producer status other than `pass`.

Assert deterministic `blocked` versus `validation_failed` status, project exit codes (`2` or `5`), ordered checks, stable rule ids, and no raw descriptor values in findings.

**Step 2: Run tests to verify RED**

```bash
python -m pytest -p no:cacheprovider tests/test_control_panel_handoff_consumer.py -q
```

Expected: FAIL on the first unsupported rejection behavior.

**Step 3: Implement strict validators**

Add small helpers for exact-key checking, SHA-256 format, typed mappings/lists, project-relative source validation, representation metadata, argv shape, scoped unavailable rows, boundary booleans, and status aggregation. Unsupported schema and producer non-pass are `blocked`; shape/hash mismatches are `validation_failed`; unsafe boundaries are `blocked`.

**Step 4: Run tests to verify GREEN**

Run the same test file. Expected: PASS.

**Step 5: Commit**

```bash
git add tools/control_panel_handoff_consumer.py tests/test_control_panel_handoff_consumer.py
git commit -m "Validate Stage 18 handoff identity and boundaries"
```

### Task 3: Add bounded stdin and deterministic CLI behavior

**Files:**
- Modify: `tests/test_control_panel_handoff_consumer.py`
- Modify: `tools/control_panel_handoff_consumer.py`

**Step 1: Write failing input/CLI tests**

Cover empty stdin, input over 1 MiB, invalid UTF-8, malformed JSON, duplicate object keys, valid JSON CLI output, deterministic repeated output, and exit-code/status alignment. Feed a sentinel secret/absolute path in malformed or unknown content and assert it is not echoed.

**Step 2: Run input tests to verify RED**

```bash
python -m pytest -p no:cacheprovider tests/test_control_panel_handoff_consumer.py -q
```

Expected: FAIL because bounded stdin parsing and `main()` are missing.

**Step 3: Implement bounded parsing and main**

Implement `read_stdin_document(stream)`, duplicate-key rejecting `object_pairs_hook`, strict UTF-8 decode, JSON object requirement, safe input findings, JSON-only stdout rendering, and `main(stdin=None, stdout=None)`. Read `MAX_INPUT_BYTES + 1`, never read files, and never import/call subprocess, socket, or producer modules.

**Step 4: Run tests to verify GREEN**

Run the same test file. Expected: PASS.

**Step 5: Add independence/no-side-effect tests**

Assert tool source has no `agent_runtime`, `subprocess`, `socket`, `open(`, or representation renderer imports; snapshot project/temp file bytes before and after valid/invalid runs.

**Step 6: Run tests again**

Expected: PASS with no warnings using `-p no:cacheprovider`.

**Step 7: Commit**

```bash
git add tools/control_panel_handoff_consumer.py tests/test_control_panel_handoff_consumer.py
git commit -m "Add bounded stdin handoff consumer CLI"
```

### Task 4: Document and close Stage 18

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/00-index.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `docs/79-read-only-host-consumer-validation-boundary.md`
- Modify: `tasks/handoff-2026-07-14.md`
- Create: `docs/archive/release-notes/82-release-notes-stage18-read-only-host-consumer-validation.md`

**Step 1: Add usage and boundary documentation**

Document the pipeline, JSON output schema, exit codes, 1 MiB limit, duplicate-key rejection, standard-library independence, and explicit non-execution boundary.

**Step 2: Update stage recovery sources**

Mark Stage 18 complete, add release notes to recovery order, and define the next step as a design gate rather than speculative implementation.

**Step 3: Run focused tests**

```bash
python -m pytest -p no:cacheprovider tests/test_control_panel_handoff_consumer.py tests/test_orchestration_control_panel.py tests/test_orchestration_contract.py tests/test_orchestration_boundary_contract.py -q
```

Expected: PASS.

**Step 4: Run full verification**

```bash
python -m pytest -p no:cacheprovider tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest -p no:cacheprovider tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

Expected: every command exits `0`.

**Step 5: Commit stage closure**

```bash
git add README.md AGENTS.md docs tasks tools tests
git commit -m "Complete Stage 18 host consumer validation"
```

**Step 6: Preserve branch for review**

Do not push, merge, tag, or delete the worktree without explicit user direction.

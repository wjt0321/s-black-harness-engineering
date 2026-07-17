# Stage 49 Fixed Git Status Executor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement and locally enable the single fixed `git status --short --branch` executor on Windows without opening a generic command surface.

**Architecture:** Keep the Stage 44 readiness snapshot immutable. Add a v1 machine-local trust binding stored outside the project, a lstat-first bounded repository guard, a finite porcelain-v1 parser, and a Windows-only suspended-process Job Object runner. The orchestration layer owns the exact argv/environment, writes the dedicated started audit before spawn, rechecks trust and guard identity, writes exactly one terminal audit, and releases only a safe summary after all post-run checks pass. Unsupported platforms or missing/drifted trust bindings remain unavailable.

**Tech Stack:** Python 3.11+, standard library (`ctypes`, `subprocess`, `threading`, `hashlib`, `pathlib`), `jsonschema`, pytest, existing `CheckResult`/`Finding`, adapter registry, and execution audit writer.

---

### Task 1: Freeze executable trust binding and safe discovery

**Files:**
- Create: `agent_runtime/execution_trust.py`
- Create: `adapters/execution-trust-binding.schema.json`
- Modify: `agent_runtime/doctor.py`
- Test: `tests/test_execution_trust.py`

**Step 1: Write failing discovery and binding tests**

Cover empty/relative/nonexistent/project-local PATH entries, deterministic Windows case-insensitive normalization, `.cmd`/`.bat` rejection, fixed `git.exe` basename, external binding path ownership, strict schema, duplicate-key/size/UTF-8 guards, SHA-256/file identity/approved-root drift, writable parent blocking, Authenticode failure, and value-safe findings.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_execution_trust.py -q
```

Expected: FAIL because the module and schema do not exist.

**Step 3: Implement minimal Windows trust support**

Resolve the machine-local binding path without environment overrides, sanitize PATH, inspect a fixed candidate with Win32 handles, keep an executable handle open without write/delete sharing, verify Authenticode and signer certificate identity, check parent-directory write access, and atomically create/replace a strict operator-reviewed binding only through an explicit controlled action.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 2: Implement finite porcelain parser and safe result model

**Files:**
- Create: `agent_runtime/git_status_porcelain.py`
- Test: `tests/test_git_status_porcelain.py`

**Step 1: Write failing parser tests**

Cover every frozen branch-header form, canonical ahead/behind integers, LF/final-newline rules, UTF-8/NUL/control/line-count/line-size bounds, the complete XY allowlist, conflict/ordinary/untracked mapping, rename/copy single-entry counting, and rejection of `!!`, unknown pairs, duplicate headers, raw path projection, and stderr on exit zero.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_git_status_porcelain.py -q
```

Expected: FAIL because the parser does not exist.

**Step 3: Implement the pure parser**

Return only dirty/count/detached/ahead/behind, byte counts, and stdout digest. Never retain branch names or paths in the public result.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 3: Implement repository containment and no-write guard

**Files:**
- Create: `agent_runtime/git_repository_guard.py`
- Test: `tests/test_git_repository_guard.py`

**Step 1: Write failing containment tests**

Cover project markers, direct `.git` directory, `.git/commondir`, symlink/reparse/hardlink metadata, bounded refs/objects traversal, config size/grammar/duplicate and dangerous-key blocking, alternates, external path surfaces, submodule markers/index gitlinks, lock files, deterministic pre/post fingerprinting, and value-safe findings.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_git_repository_guard.py -q
```

Expected: FAIL because the guard does not exist.

**Step 3: Implement lstat-first guard**

Use bounded never-follow traversal before reading or hashing metadata. Produce an internal manifest/fingerprint and a public evidence status without exposing paths or config values.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 4: Implement the Windows Job Object bounded runner

**Files:**
- Create: `agent_runtime/fixed_process_runner.py`
- Test: `tests/test_fixed_process_runner.py`

**Step 1: Write failing runner tests**

Use injected process/platform seams to cover exact argv/environment ownership, `shell=False`, closed stdin, concurrent 64 KiB stream limits, timeout/cancel, terminate-grace-kill-wait ordering, suspended create, Job Object assignment before resume, process-image identity mismatch, spawn failure, no retry, and unsupported-platform unavailability.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_fixed_process_runner.py -q
```

Expected: FAIL because the runner does not exist.

**Step 3: Implement the bounded runner**

On Windows, create the process suspended, assign it to a `KILL_ON_JOB_CLOSE` Job Object, verify the actual process image against the still-open trusted executable handle, resume it, concurrently drain bounded binary streams, and always close/reap the complete job. Keep POSIX unavailable until an equally strong image/process-group implementation exists.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 5: Orchestrate preflight, audit, execution, and release gate

**Files:**
- Create: `agent_runtime/orchestration_git_status_execution.py`
- Modify: `agent_runtime/cli.py`
- Modify: `agent_runtime/orchestration_contract.py`
- Test: `tests/test_orchestration_git_status_execution.py`
- Modify: `tests/test_orchestration_boundary_contract.py`
- Modify: `tests/test_orchestration_contract.py`
- Modify: `tests/test_controlled_write_regression.py`

**Step 1: Write failing orchestration tests**

Freeze `orchestration execution trust bind` and `orchestration execution git-status`. Require `--commit`, `task_id`, and `request_id`; reject argv/path/cwd/env overrides. Cover registry drift, missing trust, preflight failure, deterministic plan hash, started-audit failure preventing runner invocation, pre-spawn drift, spawn/child/parser/guard failure terminal mapping, terminal-audit failure withholding results, and ready safe projection.

**Step 2: Run RED tests**

```bash
python -m pytest tests/test_orchestration_git_status_execution.py tests/test_orchestration_boundary_contract.py tests/test_orchestration_contract.py tests/test_controlled_write_regression.py -q
```

Expected: FAIL because the command surface and orchestrator do not exist.

**Step 3: Implement minimal orchestration and CLI**

Keep the exact operation constants internal. Build the fixed environment and canonical plan hash, commit started audit, perform final trust/guard recheck, invoke the bounded runner, validate output, compare post-run guard evidence, commit one terminal audit, and release only the v1 safe result. Non-commit invocation performs no subprocess and no write.

**Step 4: Run GREEN tests**

Run the same command. Expected: PASS.

### Task 6: Provision and run one authorized real Windows smoke

**Files:**
- No repository file is modified by the smoke beyond test-generated temporary files.

**Step 1: Inspect the candidate outside the product output**

Independently review the canonical installation root, executable SHA-256, file identity, and Authenticode signer thumbprint.

**Step 2: Create the machine-local binding explicitly**

```bash
python -m agent_runtime.cli orchestration execution trust bind --expected-sha256 <reviewed-digest> --expected-publisher-thumbprint <reviewed-thumbprint> --commit --json
```

Expected: `pass`, with only safe binding/executable identity digests returned.

**Step 3: Run a real smoke in a temporary standalone repository**

Create a temporary project containing `pyproject.toml`, `agent_runtime/`, direct `.git/`, and temporary task/event ledgers. Invoke the fixed executor once with `--commit`. Verify ready status, closed audit, safe summary, unchanged critical Git metadata, no raw paths/branch/output/environment, and cleanup of the temporary repository.

### Task 7: Close Stage 49 documentation and verify

**Files:**
- Modify: `docs/96-fixed-git-status-executor-design-gate.md`
- Create: `docs/98-fixed-git-status-executor-implementation-and-limited-enablement.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `docs/64-versioning-governance.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Create: `docs/archive/release-notes/108-release-notes-stage49-fixed-git-status-executor.md`
- Modify: `tasks/handoff-2026-07-17.md`
- Modify: `tasks/progress.md`

**Step 1: Update facts and boundaries**

Record Windows-only limited enablement, external trust binding, explicit `--commit`, real smoke evidence, safe projection, lack of OS filesystem write proof, POSIX unavailability, and continued prohibition of generic shell/network/service/DB/UI.

**Step 2: Run focused regression**

```bash
python -m pytest tests/test_execution_trust.py tests/test_git_status_porcelain.py tests/test_git_repository_guard.py tests/test_fixed_process_runner.py tests/test_orchestration_git_status_execution.py tests/test_execution_audit_writer.py tests/test_controlled_write_regression.py -q
```

Expected: PASS.

**Step 3: Run full verification**

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

**Step 4: Commit locally**

```bash
git add AGENTS.md README.md README.en.md adapters agent_runtime docs tasks tests
git commit -m "Complete fixed Git status executor milestone"
```

Do not push or create a tag.

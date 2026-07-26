<!-- parents: 112-pi-node-runtime-identity-binding-design.md -->
<!-- relates: 110-pi-controlled-dry-run-adapter-contract.md, 111-pi-controlled-dry-run-print-implementation.md -->

# 113 — Pi Runtime Binding Implementation (Stage 64)

> Status: **Stage 64 binding-only implementation complete; no Pi runner migration or execution authority**
> Date: 2026-07-26
> Prerequisite: Stage 63 review-bound Node/Pi identity design gate.

## 1. Delivered Surface

Stage 64 adds `agent_runtime.pi_runtime_binding` and a separate CLI namespace:

```text
orchestration execution pi-binding inspect
orchestration execution pi-binding bind
```

`bind` is preview-only unless it receives explicit `--commit`. It accepts reviewed `--node-path`, `--cli-entry`, and one or more `--module-root` package roots. Existing records reject replacement by default; rotation requires both `--replace` and the current `--expected-binding-id`.

The implementation creates a machine-local JSON record containing only review evidence:

- Node executable path and SHA-256;
- Pi CLI entry path and SHA-256;
- canonical module-root closure manifests with relative file path, byte count, and SHA-256;
- closure identity, binding identity, and explicit local-operator review provenance.

Public command output exposes only binding and closure digests. It does not expose file content, API keys, prompt text, session data, PATH, environment values, or raw package source.

## 2. Safety Properties

This stage never executes Node, Pi, npm, npx, package scripts, shell commands, or model calls. It does not modify Pi configuration, `.runtime`, package installations, task/event ledgers, execution audits, or the existing `pi_cli_print` runner.

Candidate validation is fail-closed:

- Node and CLI candidates must be regular, non-symlink files;
- CLI entry must reside under a reviewed module root;
- module closure rejects symlink/reparse traversal and paths escaping its root;
- closure is bounded to 2,048 files and 64 MiB;
- malformed, missing, oversized, or tampered records return safe failures;
- atomic replacement is the only write path.

The current Stage 62 runner remains unbound and continues to report:

```text
real_model_call=true
trusted_executable_chain=false
```

## 3. Verification

`tests/test_pi_runtime_binding.py` covers non-mutating preview, commit/inspection, explicit rotation, unsafe candidate rejection, and closure drift.

`tests/test_cli.py` covers fixed public inspection and reviewed-path forwarding. All test fixtures use temporary files and do not inspect or write the local Pi/npm installation.

Required final verification is the full pytest suite, public scan, doctor, docs context, diff check, and pre-commit hook.

## 4. Next Candidate

A future **bound runner migration gate** may allow `pi_cli_print` to launch direct reviewed Node + CLI-entry argv. It requires a separate authorization, post-run identity validation, exact integration tests, and a new real smoke. Until then, Stage 64 is evidence collection only and does not change execution authority.

<!-- stage64-implementation-status: complete-binding-only -->
<!-- execution-status: no-runner-migration -->

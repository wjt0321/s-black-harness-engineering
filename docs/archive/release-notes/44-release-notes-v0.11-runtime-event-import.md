# 44 — v0.11 Release Notes: Runtime Event Import

## Version

`v0.11.0-runtime-event-import`

## Summary

This release freezes the Runtime Event Import capability package for `s-black harness engineering`.

It extends the runtime from single-event append and task creation into a controlled batch event import workflow with dry-run preflight, commit-time transaction semantics, optional consistency-freeze protection, and controlled-write regression coverage.

## Highlights

- `runtime event import --dry-run` is available for batch event preflight.
- Candidate event batches use JSONL input, one event object per non-empty line.
- Dry-run uses all-or-nothing semantics and preserves input order.
- Dry-run validates schema, duplicate event ids, unknown tasks, status transitions, secret scan, public scan, and simulated ledger consistency.
- `runtime event import --commit` is available for controlled batch append to an existing event ledger.
- Commit appends candidate events as one continuous JSONL block at the end of the target event ledger.
- Commit reruns full preflight before writing and runs `task validate --schema event` plus `task check-ledger` after writing.
- Commit rolls back by truncating to the original byte size if writing or post-checks fail.
- Commit does not create a new event ledger in the first version; the target events file must already exist.
- Consistency freeze is available through dry-run `plan_hash` output and commit `--expected-plan-hash` input.
- Freeze mismatch returns `blocked` before preflight or append, preserving the reviewed dry-run context.
- Controlled write regression now covers `runtime event import --commit` and `--expected-plan-hash` behavior.

## CLI Commands

Batch event dry-run:

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

Batch event commit:

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit
```

Commit bound to a reviewed dry-run plan:

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --expected-plan-hash sha256:...
```

## Release Scope

This release includes the work from:

- `docs/37-runtime-event-import-dry-run.md`
- `docs/38-release-notes-runtime-event-import-dry-run.md`
- `docs/39-runtime-event-import-commit-design.md`
- `docs/40-release-notes-runtime-event-import-commit.md`
- `docs/41-runtime-event-import-consistency-freeze.md`
- `docs/42-release-notes-runtime-event-import-consistency-freeze.md`
- `docs/43-controlled-write-regression-event-import.md`

## Safety Boundary

This release does not add adapter execution or external side effects.

It does not:

- execute real adapters
- access the network as part of runtime commands
- send messages
- read `.env`, `.env.local`, credential files, tokens, or keyrings
- write task ledger records from event import
- write adapter envelopes from event import
- reorder imported events
- allow partial-success event imports
- automatically repair ledgers
- print full secret matches, event messages, metadata values, artifact payloads, evidence descriptions, raw refs, decision refs, targets, or inputs

The only new controlled write capability in this release is:

```text
runtime event import --commit
```

Its write boundary is limited to appending a continuous JSONL block to an existing project-local event ledger file, with post-check and byte-size rollback.

## Validation

The release has been validated with:

```text
python -m pytest tests/test_controlled_write_regression.py -q
python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

Expected current result:

```text
controlled write regression -> passed
focused event import tests -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
git diff --check -> PASS
```

## Known Limits

- `runtime event import --commit` requires the target events ledger to already exist.
- Consistency freeze is optional; commit behavior remains backward-compatible when `--expected-plan-hash` is omitted.
- The first freeze implementation only uses `--expected-plan-hash`; it does not expose separate `--expected-events-ledger-fingerprint` or `--expected-events-ledger-size-bytes` options.
- Tasks ledger fingerprinting is not enforced yet.
- JSON array input is not supported.
- Partial success and automatic event sorting are intentionally not supported.

## Recommended Next Steps

1. Decide whether to add strict freeze mode with `--require-dry-run`.
2. Decide whether tasks ledger fingerprinting should become part of the reviewed plan.
3. Consider whether controlled event ledger creation should be allowed in a later version.
4. Continue expanding regression coverage as additional controlled write points are introduced.

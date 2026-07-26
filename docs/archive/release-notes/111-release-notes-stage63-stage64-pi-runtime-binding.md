# Release Notes 111 — Stage 63–64 Pi Runtime Binding

> Date: 2026-07-26
> Status: Stage 63 design gate and Stage 64 binding-only implementation complete
> Milestone: `v0.18.0-pi-runtime-binding` annotated tag; main and tag pending push

## Delivered Scope

Stage 63 freezes the review-bound Node/Pi identity contract. It identifies the actual local launch chain as:

```text
pi shim -> node.exe -> Pi CLI entry -> module closure
```

Stage 64 implements the binding-only evidence surface:

- `agent_runtime.pi_runtime_binding` hashes reviewed Node, CLI entry, and bounded module closures without execution;
- `orchestration execution pi-binding inspect|bind` provides local inspection, preview, explicit `--commit` creation, and reviewed rotation;
- closure validation rejects unsafe files, symlink/reparse traversal, path escape, empty closures, and fixed file/byte bounds;
- records are machine-local and atomically written; existing records reject implicit replacement;
- CLI boundary tests freeze the new subcommand separately from Git executable trust.

Authoritative sources are `docs/112-pi-node-runtime-identity-binding-design.md` and `docs/113-pi-runtime-binding-implementation.md`.

## Security Conclusion

- Stage 64 does not execute Node, Pi, npm, npx, package scripts, shell commands, or model calls.
- It does not modify the Pi agent configuration, package installation, `.runtime`, execution audit, task/event ledger, or `pi_cli_print` runner.
- Existing fixed Pi print remains explicitly unbound and continues to report `trusted_executable_chain=false`.
- A local binding is review evidence, not protection against a hostile local administrator.
- No tools, sessions, JSON mode, POSIX backend, network adapter, third operation, or runner migration is authorized.

## Verification

- Focused binding, CLI, boundary contract, and Pi print tests pass.
- Full pytest suite passes with existing skips only.
- Public scan, doctor, docs context, Markdown links, pre-commit, and diff check pass.
- No real binding was created during automated verification; tests use temporary files only.

## Version and Next Step

This closes the `v0.18.0-pi-runtime-binding` milestone: Stage 52–64 now provide a bounded Pi host preflight path, fixed no-tools print execution, audited containment, and reviewed runtime-binding evidence. It does not add generic agent execution, Pi tool authority, session persistence, or a bound runner migration.

The next candidate is Stage 65, a design-only bound runner migration gate. It may define direct bound Node plus sealed CLI-entry launch, post-run identity validation, and separately authorized smoke requirements, but must not change the runner in the design stage.

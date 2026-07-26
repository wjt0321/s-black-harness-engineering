<!-- parents: 112-pi-node-runtime-identity-binding-design.md, 113-pi-runtime-binding-implementation.md -->
<!-- relates: 110-pi-controlled-dry-run-adapter-contract.md, 111-pi-controlled-dry-run-print-implementation.md -->

# 114 — Pi Bound Runner Migration (Stage 65, Design Only)

> Status: **Stage 65 design gate frozen; no runner implementation authority**
> Date: 2026-07-26
> Prerequisite: Stage 64 binding-only record creation and inspection are complete.
> This document does not create a binding, execute Node/Pi/npm, modify `pi_cli_print`, or make a model call.

## 1. Decision

A future implementation MAY introduce an opt-in bound mode for the existing fixed `pi_cli_print` operation. It replaces the current sanitized-PATH `pi` shim resolution with direct, bound argv:

```text
<bound node.exe> <bound cli-entry.js> --print --no-session --no-tools <bounded prompt>
```

It is not a new operation. Actor, adapter, capability, prompt validation, timeout limits, no-tools/no-session boundary, environment allowlist, lease, Job Object containment, output withholding, and audit lifecycle remain unchanged.

The old unbound path remains supported until a separately authorized implementation and migration validation are complete. It continues to report `trusted_executable_chain=false`.

## 2. Mode Selection

The future CLI MUST NOT silently switch an existing request from unbound to bound mode. It MUST use one explicit, fixed selection mechanism, chosen at implementation time:

- a dedicated `--require-runtime-binding` flag; or
- a separately named fixed command surface.

The selected mechanism MUST be included in the canonical plan identity. Caller-supplied Node path, entry path, module root, `PATH`, model, provider, cwd, flag, environment, loader, or binding file path remain forbidden.

If bound mode is requested and no valid machine-local binding exists, the result is `blocked` before lease acquisition, audit start, or child spawn. The runner MUST NOT fall back to the unbound PATH resolver.

## 3. Identity Release Gates

The future runner MUST perform these checks in order:

1. validate binding schema, binding id, supported closure-manifest version, and local record location;
2. reopen and re-hash the bound Node executable, CLI entry, and every closure file before `execution_attempt_started`;
3. build direct argv from those verified handles/paths only;
4. write started audit whose plan identity includes binding id, Node identity, CLI identity, closure identity, and bound-mode marker;
5. repeat identity validation immediately before spawn; any drift terminates before child launch;
6. run existing bounded Windows Job Object process tree handling;
7. repeat required identity validation after child completion and before safe-summary release;
8. only after terminal audit and post-run identity success release a bound-mode ready summary.

Pre-spawn drift blocks without an audit if it occurs before started. Drift after started becomes a terminal audit failure with summary withheld. Terminal-audit failure retains the existing recovery behavior; the migration MUST NOT add automatic retry.

## 4. Audit and Compatibility

Audit v2 records for bound mode MUST use the existing fixed operation identity plus explicit safe evidence:

```text
runtime_binding_id
node_identity
cli_entry_identity
closure_identity
launch_mode=bound
```

No binding record contents, absolute paths, package source, prompt, model text, PATH, environment values, or secret values may enter public audit/result projections.

Existing Stage 62 unbound audits remain historical facts. They MUST NOT be rewritten, upgraded, or interpreted as bound execution. Consumers that do not understand `launch_mode=bound` must treat it as an additional safe evidence field, not as permission to run a command.

## 5. Environment and Process Contract

Bound mode preserves the Stage 62 explicit allowlist. In addition it MUST remove `NODE_PATH`, `NODE_OPTIONS`, `NODE_DISABLE_COLORS`, loader/register flags, and all inherited npm configuration. The runner invokes no shell, `pi.cmd`, `npm`, or `npx`.

Windows remains the only supported backend. POSIX remains unavailable. Bound mode cannot enable Pi tools, sessions, JSON events, TUI automation, network adapters, a service, or another operation.

## 6. Real Smoke and Rollback

A bound-mode real smoke requires a fresh user authorization that explicitly covers:

- one fixed real model call;
- the reviewed local binding identity to be used;
- the isolated test root and no-tools/no-session prompt;
- audit/lease writes in the isolated test root.

The smoke MUST be opt-in, bounded, value-withholding, and run after all offline tests. It must prove exact direct Node argv, binding evidence, started/terminal closure, post-run identity success, and Job containment. A failed smoke does not permit fallback to unbound execution in the same invocation.

Rollback is configuration-free: do not select bound mode. The existing Stage 62 unbound runner stays unchanged. Deleting or rotating any real machine-local binding is a separate user-authorized action and is not included in migration implementation.

## 7. Stop Lines

This design stage MUST NOT:

- modify runner code, CLI behavior, audit schema, binding records, or tests;
- create/rotate/delete a machine-local binding;
- execute Node, Pi, npm, npx, package scripts, shell commands, or model calls;
- alter Pi package installation, `.runtime`, agent configuration, or credentials;
- claim `trusted_executable_chain=true` before an implementation stage passes its full acceptance matrix and separately authorized real smoke;
- expand beyond the existing fixed no-tools/no-session print operation;
- auto-commit, tag, push, or publish.

## 8. Future Implementation Acceptance Matrix

The implementation stage MUST prove:

1. bound mode is explicit and never falls back to PATH/shim/npm/npx;
2. missing/invalid/unsupported binding blocks before lease/audit/spawn;
3. plan hash and started/terminal audit contain bound safe identities, never raw paths or secret/prompt values;
4. Node, CLI entry, and closure drift are rejected before spawn and withheld after spawn;
5. direct argv is exactly bound Node + bound CLI + fixed Pi flags + prompt;
6. child environment excludes Node/npm loader and configuration variables;
7. existing unbound tests and audits remain unchanged and accurately marked unbound;
8. terminal audit/recovery behavior remains fail-closed with no retry;
9. dedicated bound-mode offline tests, full regression, public scan, doctor, docs context, link audit, pre-commit, and diff check pass;
10. a real bound-mode smoke runs only after separate explicit authorization.

## 9. Next Candidate

The next possible implementation is **Stage 66 — Pi Bound Runner Migration**. It requires a new explicit authorization because it changes the real execution launch chain and may require one model smoke. It is not automatically enabled by this document.

<!-- stage65-gate-status: frozen -->
<!-- execution-status: design-only-no-implementation -->

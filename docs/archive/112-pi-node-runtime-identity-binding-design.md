<!-- parents: 110-pi-controlled-dry-run-adapter-contract.md, 111-pi-controlled-dry-run-print-implementation.md -->
<!-- relates: archive/96-fixed-git-status-executor-design-gate.md, archive/98-fixed-git-status-executor-implementation-and-limited-enablement.md -->

# 112 — Pi Node Runtime Identity Binding (Stage 63, Design Only)

> Status: **Stage 63 design gate frozen; no implementation authority**
> Date: 2026-07-26
> Prerequisite: Stage 62 fixed `pi_cli_print` is complete and has passed one real DeepSeek smoke.
> This document adds no CLI, binding record, subprocess, npm action, model call, or execution permission.

## 1. Problem

Stage 62 proves that the fixed Pi print invocation is bounded, audited, and contained on Windows. It deliberately reports `trusted_executable_chain=false` because its current resolver selects the first sanitized-PATH `pi` candidate.

That candidate is normally an npm Windows shim. Its real chain is broader:

```text
pi.cmd / pi shim -> node.exe -> Pi CLI JavaScript entry -> Node module resolution
```

Binding only the shim, or only `cli.js`, cannot prove which Node runtime or package closure will execute. This is a trust-model gap, not an output-parsing problem. It must be closed before expanding Pi tools, sessions, JSON mode, or any additional real operation.

## 2. Decision

A future implementation MUST replace production reliance on `pi.cmd` / `npm` / `npx` with a review-bound launch specification:

```text
node.exe <sealed Pi CLI entry> --print --no-session --no-tools <bounded prompt>
```

The specification has three identity layers:

| Layer | Required identity | Purpose |
|:---|:---|:---|
| Node runtime | canonical path, volume/file identity, SHA-256, Authenticode signer evidence | binds the executable process image |
| Pi CLI entry | canonical path, regular-file/reparse checks, size, SHA-256 | binds the exact CLI entry script |
| Runtime closure | versioned manifest of declared Pi package roots and their safe content identities | detects drift in code Node may resolve at launch |

The resulting assurance is **review-bound identity**, not protection against a hostile local administrator. A local operator who can alter a runtime and create a new binding can still change what is reviewed. The system MUST accurately report this distinction and MUST NOT claim a generic trusted executable chain merely because a binding exists.

## 3. Candidate Discovery and Binding

### 3.1 Discovery is not execution

Candidate discovery MAY inspect a sanitized-PATH `pi.cmd` or equivalent package metadata as an untrusted hint. It MUST NOT execute `pi`, `npm`, `npx`, `node`, package scripts, or arbitrary JavaScript merely to discover a candidate.

A discovery result is advisory only. It MUST expose only safe identities and fixed findings, never API keys, PATH values, prompt text, session data, or package file contents.

### 3.2 Binding creation

A future `trust pi` surface, if introduced, MUST require explicit `--commit` and create a machine-local, append-safe or atomic binding record. It MUST:

1. reject missing, relative, symlink/reparse, non-regular, or out-of-scope paths;
2. record the three identities from Section 2 plus a canonical manifest digest;
3. record package name/version metadata only as explanatory evidence, never as the identity substitute;
4. write no npm lockfile, package file, agent settings, or project runtime configuration;
5. reject replacement by default; rotation MUST require explicit `--replace --commit` and create an audit trail;
6. return only identity digests, display-safe paths, and fixed findings.

`package.json` version, npm cache integrity, and a `pi.cmd` digest are useful diagnostics but MUST NOT be sufficient to authorize execution.

## 4. Runtime Closure

Node can resolve modules beyond the direct CLI entry. An entry-only digest is therefore insufficient.

The future implementation MUST use a finite, explicit closure manifest with these properties:

- each included root is canonical, contained in an approved package scope, and has no symlink/reparse traversal;
- every included regular file has a relative path, byte size, and SHA-256 in canonical ordering;
- manifests have hard file-count and total-byte limits; excessive or unreadable trees fail closed;
- environment rebuilding MUST continue to omit `NODE_PATH`, `NODE_OPTIONS`, loaders, proxies, and all unspecified variables;
- the production launch MUST resolve only Node plus the sealed CLI entry, never a shell shim or package manager;
- an unresolved or dynamically broadened dependency is a binding failure, not a reason to fall back to PATH or npm discovery.

The implementation may narrow the initially supported package layout, but it MUST NOT silently widen the closure to an arbitrary global `node_modules` tree. A package update or any manifest drift requires a new reviewed binding before a real Pi invocation may run.

## 5. Execution Release Gate

Before every future `pi_cli_print --commit` invocation, the runner MUST:

1. load the active binding and reject its absence, invalid schema, or unsupported manifest version;
2. reopen and revalidate Node, CLI entry, and every required closure identity immediately before spawn;
3. construct direct fixed argv from the bound `node.exe` and bound entry only;
4. retain the existing prompt validation, environment allowlist, lease, readiness checks, Windows Job Object containment, bounded I/O, and started/terminal audit chain;
5. bind the canonical plan hash to the binding version and manifest digest;
6. revalidate relevant identity after child completion before releasing any safe summary.

Any identity mismatch, missing file, reparse point, manifest overflow, unsupported package layout, or binding write/audit failure MUST block or fail the attempt with raw output withheld. The runner MUST NOT fall back to `pi.cmd`, `npm`, `npx`, a user-supplied executable, or a generic Node command.

## 6. Compatibility and Migration

Stage 62 remains operationally unchanged until a separately authorized implementation is complete. Its status remains:

```text
real_model_call=true
trusted_executable_chain=false
```

A later implementation MAY introduce a stricter binding-required execution mode. It MUST NOT reinterpret older Stage 62 audit records or claim that the earlier smoke used a bound Node/package chain.

Existing `.runtime/pi-agent` contains agent configuration, not the globally installed Pi executable package. It MUST remain isolated from binding records and MUST NOT be used as a reason to trust an npm installation.

## 7. Stop Lines

This stage MUST NOT:

- implement a runner, binding CLI, schema, trust record, subprocess, or migration;
- execute `pi`, `node`, `npm`, `npx`, package scripts, or a model call;
- install, update, remove, repair, or relocate Node/Pi/npm packages;
- accept caller-supplied node path, CLI path, package root, model, provider, cwd, environment, flag, or loader override;
- enable Pi tools, TUI automation, session persistence, JSON mode, POSIX execution, network adapters, or a third real operation;
- read `auth.json`, sessions, `.env*`, keyrings, or credentials;
- claim that file hashing protects against a hostile local administrator;
- auto-commit, push, tag, or publish.

## 8. Future Implementation Acceptance Matrix

A later implementation stage MUST add TDD coverage for at least:

1. missing, malformed, stale, or replaced binding blocks before audit start/spawn;
2. Node executable digest, signer, volume/file identity, and reparse failures;
3. CLI entry replacement, size/hash mismatch, and path escape failures;
4. closure entry drift, added/removed file, duplicate relative path, count/byte overflow, and symlink/reparse failure;
5. direct Node + entry argv is exact and no `cmd.exe`, `pi.cmd`, npm, npx, shell, or caller override is used;
6. `NODE_PATH`, `NODE_OPTIONS`, loader variables, proxies, and non-allowlisted values are absent from child environment;
7. plan/audit identity includes binding version and manifest digest but never secret or prompt values;
8. binding rotation is explicit, auditable, and cannot replace a valid binding implicitly;
9. post-run identity drift withholds the summary and leaves a recoverable audit state;
10. existing Stage 62 behavior remains accurately marked unbound until the stricter mode is explicitly selected.

Full regression, public scan, doctor, docs context, diff check, pre-commit, and a separately authorized real smoke are required before any binding-backed execution claim.

## 9. Next Candidate

After this gate, the highest-value implementation candidate is a **binding-only Stage 64**: inspect/create/rotate the review-bound Node/Pi manifest without changing `pi_cli_print` execution. Only after that is verified should a later stage switch the fixed print runner to the direct bound Node launch specification.

<!-- stage63-gate-status: frozen -->
<!-- execution-status: design-only-no-implementation -->

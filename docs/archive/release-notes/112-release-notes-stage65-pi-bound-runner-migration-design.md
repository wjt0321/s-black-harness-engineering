# Release Notes 112 — Stage 65 Pi Bound Runner Migration Design

> Date: 2026-07-26
> Status: design gate complete; no implementation, binding mutation, or model call
> Milestone: follows `v0.18.0-pi-runtime-binding`; no new tag

## Delivered Scope

Stage 65 defines the only permitted future migration of fixed `pi_cli_print` from sanitized-PATH `pi` shim discovery to direct reviewed Node plus sealed Pi CLI entry launch.

The gate freezes:

- explicit bound-mode selection with no silent migration or fallback;
- pre-start, pre-spawn, and post-run Node/entry/closure identity checks;
- plan and audit binding to safe runtime identities;
- compatibility with historical Stage 62 unbound audit records;
- restricted environment and Windows-only process contract;
- separately authorized real-smoke and rollback requirements.

The authoritative source is `docs/114-pi-bound-runner-migration-design.md`.

## Security Conclusion

- Existing unbound Stage 62 behavior remains unchanged and explicitly untrusted-chain.
- Bound mode is not implemented and cannot be selected yet.
- Stage 65 does not execute Node, Pi, npm, npx, shell commands, or a model call.
- It creates, rotates, or deletes no machine-local binding.
- It does not open Pi tools, sessions, JSON mode, TUI automation, POSIX, network adapters, or any further operation.

## Verification

This document-only gate requires docs context, public scan, doctor, Markdown link audit, pre-commit, diff check, and full test regression. It does not require or authorize a real smoke.

## Next Candidate

Stage 66 may implement the bound runner migration only after a separate user authorization. That authorization must cover code changes to the real launch chain and a separately opt-in real smoke; it does not follow automatically from Stage 65.

<!-- parents: 121-acp-readiness-collection-design-gate.md, 120-controlled-collaboration-dispatch-foundation.md -->

# 122 - ACP Readiness Collector and Dispatch Binding (Stage 74)

> Status: complete, bounded snapshot collector only
> Date: 2026-07-26

## Scope

Stage 74 implements a deterministic collector for one ACP readiness evidence level. It reads the shared socket registry, explicit ACP runner bindings, and a project-local bounded runner-state snapshot. It does not contact QwenPaw or any runner at runtime.

The CLI entry is:

```bash
python -m agent_runtime.cli orchestration socket readiness collect <socket-id> \
  --snapshot-file <project-local-json> \
  --evaluated-at <timezone-aware-timestamp> \
  --ttl-seconds <1-900>
```

## Evidence Level

The collector can produce:

- `status=available` and `level=runner_listed` when the bound runner appears in an unexpired snapshot; or
- `status=unknown` when the runner is missing or the snapshot has aged beyond its TTL.

Both outcomes keep `sufficient_for_dispatch=false`. A listed runner has not proven that a session can be opened without a prompt, that a model is available, or that execution is authorized.

## Dispatch Binding

A dispatch proposal may optionally bind one readiness evidence file and an explicit evaluation time. The read model verifies:

- evidence schema and timezone-aware timestamps;
- content-addressed `evidence_id`;
- socket binding;
- expiry at dispatch evaluation time; and
- the evidence's explicit sufficiency flag.

Valid Stage 74 evidence changes the blocker from `readiness_not_collected` to `readiness_insufficient`. `execution_authority_unavailable` remains, `dispatch_eligible=false`, and `execution=not_executed`.

## Control Panel

The optional dispatch section displays the evidence status, level, id, expiry, blocked reasons, and execution state. Snapshot, HTML, and handoff representations remain read-only.

## Guarantees

- no runner, process, session, prompt, model, credential, network, quota, ledger, or project write;
- deterministic output for fixed files and explicit timestamps;
- path-contained and bounded JSON reads;
- evidence hash, socket, and expiry validation fail closed;
- no execution authority and no real dispatch.

## Deferred

A future milestone may design a stronger, still bounded ACP transport/session-openability proof. It requires separate authorization and must not send a model prompt. Real work dispatch remains a separate gate after that evidence exists.

<!-- stage74-status: complete-bounded-collector -->

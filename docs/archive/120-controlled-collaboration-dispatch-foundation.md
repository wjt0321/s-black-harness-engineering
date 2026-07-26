<!-- parents: 119-socket-readiness-evidence-and-routing-explanations.md, 117-collaboration-plan-read-model.md, 118-control-panel-collaboration-projection.md -->

# 120 - Controlled Collaboration Dispatch Foundation (Stage 72)

> Status: complete, proposal and eligibility projection only
> Date: 2026-07-26

## Scope

Stage 72 turns one validated collaboration-plan work item into a deterministic dispatch proposal. The proposal binds the current content-addressed plan, work item, socket, incoming artifact types, timeout, and review requirement.

The proposal is inspectable through:

- `orchestration collaboration dispatch validate`;
- `orchestration collaboration dispatch inspect`; and
- the optional Control Panel `--dispatch-file` section.

## Eligibility

A valid proposal may report `plan_eligible=true`, but Stage 72 always reports:

- `dispatch_eligible=false`;
- `status=blocked`;
- `execution=not_executed`;
- `readiness_not_collected`; and
- `execution_authority_unavailable`.

This distinction prevents a structurally valid plan from being presented as executable.

## ACP Readiness Contract

`adapters/acp-readiness-evidence.schema.json` freezes the static `socket-readiness/acp-session/v1` evidence shape. Its sample remains `not_collected` and explicitly forbids prompts, model calls, quota use, credential reads, and session persistence.

No collector or eligibility binding is implemented in this stage.

## Validation Boundary

The dispatch read model fails closed on:

- project-root path escape or non-JSON input;
- schema failure;
- collaboration plan drift;
- unknown work item or socket mismatch;
- review-policy mismatch; and
- incoming handoff artifact mismatch.

## Guarantees

- deterministic and read-only;
- one work item per proposal;
- no request, task, session, process, or event creation;
- no readiness probe, Agent invocation, model call, network access, or quota use;
- no ledger or project write;
- no execution authority.

## Deferred

A later design-only gate may define bounded readiness collection, expiry, withholding, and eligibility binding for one socket family. Real collection and dispatch require separate implementation gates and explicit authorization.

<!-- stage72-status: complete-read-only-dispatch-proposal -->

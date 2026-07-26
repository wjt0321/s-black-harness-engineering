<!-- parents: 116-multi-agent-collaboration-plan-and-socket-admission.md, 115-agent-socket-registry-v1.md -->
<!-- relates: 47-orchestration-hub-vision.md -->

# 117 - Collaboration Plan Read Model (Stage 69)

> Status: complete, read-only only
> Date: 2026-07-26

## Scope

Stage 69 implements the deterministic proposal layer described by Stage 68. A project-local JSON collaboration plan can bind declared sockets to role-based work items, explicit dependencies and handoffs, expected artifact types, and review gates.

```text
agent-runtime orchestration collaboration plan --file adapters/collaboration-plan.example.json
agent-runtime orchestration collaboration validate --file adapters/collaboration-plan.example.json
agent-runtime orchestration collaboration inspect --file adapters/collaboration-plan.example.json
```

`plan` and `inspect` return the same safe board projection today. `validate` is retained as the explicit validation intent and future compatibility point.

## Boundary

All three commands are deterministic and read-only. They do not persist plans, create task/event/artifact/approval records, probe readiness, execute commands, contact a socket, access a network, or invoke an Agent.

Plan files must be UTF-8 JSON below 128 KiB, use a `.json` suffix, and resolve beneath the selected project root. The public projection excludes free-form payloads: it returns only stable identities, roles, declared capabilities, dependency IDs, artifact types, and planned state.

## Validation

Validation fails closed for unknown or disabled sockets, capability mismatches, duplicate identifiers, invalid/self dependencies, cycles, invalid handoffs, unsupported artifact types, malformed review gates, and review-required work without a covering review gate.

The output includes a content-addressed `plan_id` and a registry identity. A changed safe plan or declared socket set produces a new identifier for a future approval/review workflow.

## Example

`adapters/collaboration-plan.example.json` is a non-executable sample:

```text
planner (Kimi) -> implementer (OMP) -> reviewer (Claude)
```

It is only a declared graph. No provider is contacted and no Agent receives the plan.

## Deferred

Stage 69 does not implement plan persistence, readiness evidence, routing selection, artifact values, event projection, approvals, background work, retries, fallbacks, model calls, or the visual board. The next stage should consume this normalized read model for a passive Control Panel projection before any execution authority is added.

<!-- stage69-status: complete-read-only -->

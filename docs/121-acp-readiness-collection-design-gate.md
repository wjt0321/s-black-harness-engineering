<!-- parents: 120-controlled-collaboration-dispatch-foundation.md, 119-socket-readiness-evidence-and-routing-explanations.md, 115-agent-socket-registry-v1.md -->

# 121 - ACP Readiness Collection Design Gate (Stage 73)

> Status: complete, contract freeze only
> Date: 2026-07-26

## Scope

Stage 73 freezes the first bounded readiness collection contract for `acp_delegate` sockets. It separates four facts that must not be conflated:

- the socket is declared in the adapter registry;
- the socket is explicitly bound to an ACP runner id;
- the runner appears in a read-only control-plane snapshot; and
- the runner is sufficiently ready and authorized for dispatch.

Only the first three can be represented by the Stage 73 contract. Runner presence is not session readiness, model availability, or execution authority.

## Contracts

- `acp-runner-bindings.schema.json` maps each ACP socket to one explicit runner id.
- `acp-runner-state-snapshot.schema.json` accepts a bounded `qwenpaw_acp_runner_list` observation.
- `acp-readiness-evidence-v2.schema.json` defines content-addressed, expiring evidence.

The initial bindings are `kimi-code-acp -> kimi_code`, `claude-code-acp -> claude_code`, and `omp-acp -> omp`.

## Lifecycle

- evidence requires timezone-aware `observed_at` and `evaluated_at`;
- TTL is bounded to 1-900 seconds;
- evaluation before observation is invalid;
- evaluation after expiry cannot be used by dispatch;
- content, socket, and runner bindings are immutable through the evidence hash;
- missing runners produce `unknown`, not an optimistic fallback.

## Stop Lines

The collection contract cannot:

- start a runner or process;
- open or persist an ACP session;
- send a prompt or invoke a model;
- read credentials or model configuration;
- access the network;
- write project files or ledgers; or
- grant execution authority.

## Stage 74 Gate

Implementation is allowed only as a deterministic reader of an explicit project-local runner snapshot. It may produce `available/runner_listed` evidence, but the evidence schema must keep `sufficient_for_dispatch=false` until a separately authorized stronger readiness level exists.

<!-- stage73-status: complete-design-gate -->

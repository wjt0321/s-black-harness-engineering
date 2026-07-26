<!-- parents: 118-control-panel-collaboration-projection.md, 115-agent-socket-registry-v1.md, 49-capability-routing-model.md -->

# 119 - Socket Readiness Evidence and Routing Explanations (Stage 71)

> Status: complete, explanation projection only
> Date: 2026-07-26

## Scope

Stage 71 exposes why each socket appears in a validated collaboration plan without adding a second router. The Stage 69 safe projection now includes `routing_explanations` derived only from the explicit plan binding and the shared socket registry.

Each explanation reports:

- socket and role;
- `selection_basis=explicit_plan_binding`;
- matched required capabilities;
- declared availability and invocation mode;
- a socket-family readiness evidence contract; and
- `readiness_evidence.status=not_collected` with `live_probe_performed=false`.

The existing Control Panel collaboration section renders these explanations as an escaped table.

## Readiness Evidence Families

Readiness evidence is transport-specific and cannot be inferred from `enabled=true` or `availability=declared`:

| Invocation mode | Future evidence contract | Evidence boundary |
|:---|:---|:---|
| `acp_delegate` | `socket-readiness/acp-session/v1` | A future bounded ACP session/runner check; no prompt or Agent turn. |
| `local_cli` | `socket-readiness/local-cli/v1` | A future bounded executable/configuration check; no model call or tool execution. |
| `agent_api` | `socket-readiness/agent-api/v1` | A future bounded endpoint/auth contract; no task submission or quota-consuming call. |

Stage 71 names these contracts only. It does not implement or claim their evidence.

## Routing Boundary

`orchestration route preview --explain` remains the authoritative capability-routing decision trace. Collaboration plans currently use explicit socket bindings, so Stage 71 explains those bindings rather than silently re-routing them. It does not select a replacement, score providers, execute a fallback, or change plan identity outside the added safe explanation fields.

## Guarantees

- deterministic and read-only;
- no plan persistence or ledger write;
- no process, session, network, credential, quota, or model probe;
- no Agent invocation or readiness claim;
- no provider-specific UI branch.

## Deferred

A later design gate may define how one evidence contract is collected, expires, is withheld, and affects eligibility. Until then, `declared` is not `ready`, and collaboration plans remain proposals with `execution=not_executed`.

<!-- stage71-status: complete-read-only-explanation -->

# Release Notes 113 — Agent Socket Registry v1

> Date: 2026-07-26
> Status: implemented read-only control-plane capability

## Delivered

The control plane now exposes a unified Agent Socket Registry from the existing source-backed adapter registry:

- `orchestration socket list [--capability <capability>]`
- `orchestration socket inspect <socket_id>`
- Control Panel adapter section includes `agent_sockets` and socket summary counts.

Pi, Kimi Code, Claude Code, OMP, and the configured QwenPaw Agent API are represented as declared Agent sockets with one common schema. The adapter registry remains the single source of truth; no parallel registry or execution path was introduced.

## Boundary

Socket availability is `declared`, not live readiness. Discovery does not start a process, contact an Agent, read session/configuration secrets, access a network, probe quota, write a file or ledger, or execute an adapter.

Stage 66 Pi bound-runner migration is now deferred security work. It is not the next product milestone.

## Next Product Candidate

Design a deterministic multi-Agent collaboration plan: task, selected sockets, roles, expected artifacts, review points, and handoff relationships. It remains read-only until a later, separately authorized invocation stage.

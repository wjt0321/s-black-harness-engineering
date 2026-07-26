<!-- parents: 47-orchestration-hub-vision.md, 48-adapter-runtime-interface.md, 49-capability-routing-model.md -->
<!-- relates: 109-pi-adapter-discovery-capability-projection.md, 114-pi-bound-runner-migration-design.md -->

# 115 — Agent Socket Registry v1 (Stage 67)

> Status: implemented read-only control-plane projection
> Date: 2026-07-26
> Scope: declared Agent discovery only; no Agent invocation authority

## Product Correction

Agent Runtime is a control plane with pluggable Agent sockets. Pi, Kimi Code, Claude Code, OMP, and the configured QwenPaw Agent API are interchangeable connection points behind one capability-oriented registry.

Guardrails, approval, audit, leases, and controlled execution remain core infrastructure. They are not the product's primary navigation model and must not force the roadmap to harden one Agent launch chain ahead of multi-Agent orchestration.

## v1 Contract

`orchestration socket list` and `orchestration socket inspect <socket_id>` project every shared-registry adapter whose `adapter_type` is `agent`.

Each socket exposes a stable read model:

- `socket_id` and linked `adapter_id`;
- display name, declared capabilities, risk level, and enabled state;
- normalized invocation mode: `acp_delegate`, `local_cli`, or `agent_api`;
- declared availability only;
- session/background/cancel and approval contract flags.

The projection comes from `adapters/adapters.sample.json`; it does not create a second registry. Existing capability routing and preflight remain the authoritative selection path.

## Availability Boundary

`availability=declared` means only that the local registry declares an enabled Agent socket. It does not claim that the Agent is running, authenticated, reachable, funded, compatible, or ready for a task.

Socket discovery MUST NOT start a process, contact an Agent, read a session or credential store, access a network, probe quota, write a file or ledger, or execute an adapter.

Live readiness is a later, independently designed concern. It must be bounded by socket type and cannot be inferred from a generic registry listing.

## Control Panel

The existing `adapters` Control Panel section now includes `agent_sockets`, retaining the snapshot v1 top-level and section structure. The summary adds `agent_socket_count` and `enabled_agent_socket_count`.

This makes the plug-in topology visible without presenting a live-service dashboard or promising execution.

## Explicit Non-Goals

v1 does not:

- invoke Pi, Kimi Code, Claude Code, OMP, QwenPaw, or any other Agent;
- probe ACP sessions, CLI processes, models, quota, network, or credentials;
- schedule, fan out, pass messages between, or automatically select Agents;
- change routing scores, existing preflight decisions, approval behavior, or controlled execution;
- create a generic execution API, background service, database, or UI write path.

## Next Candidate

The next product-oriented design gate is **multi-Agent collaboration planning**: represent a parent task, selected sockets, bounded roles, expected artifacts, review points, and handoff relationships as a deterministic plan. It must remain read-only before any inter-Agent invocation is enabled.

Stage 66 Pi bound-runner migration remains deferred security work. It is not the next product milestone and requires a separate explicit authorization if resumed.

<!-- socket-registry-v1: implemented-read-only -->

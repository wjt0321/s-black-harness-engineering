# Handoff — Stage 71 Socket Readiness Contracts and Routing Explanations

> Date: 2026-07-26
> Status: complete; read-only explanations implemented, readiness evidence not collected

## Product Direction

Agent Runtime is an extensible, board-oriented multi-Agent control plane. Pi, Kimi Code, Claude Code, OMP, QwenPaw Agent API, and future providers are registry-backed sockets. The board should show structured work, handoffs, artifacts, reviews, approvals, and evidence instead of treating raw chats as the control-plane record.

Stage 66 Pi bound-runner migration remains deferred security work. Do not resume it automatically.

## Stage 68 Contract

- New Agents enter through the shared adapter registry and Socket Registry, never a provider-specific routing or UI branch.
- Socket lifecycle is draft -> declared -> readiness_evidenced -> eligible -> disabled -> deprecated -> removed; Stage 67 currently exposes declared/disabled only.
- A collaboration plan binds a parent task to socket roles, bounded work items, dependencies, handoffs, expected artifacts, and review gates.
- Roles select capabilities, not vendors. Routing chooses a compatible socket under explicit constraints.
- Plan validity fails closed on unknown/disabled sockets, capability mismatch, cycles, invalid handoffs, skipped review gates, or unsafe public data.
- Stage 69 validates project-local JSON below 128 KiB against declared sockets and produces a content-addressed safe projection.
- It fails closed on unknown/disabled sockets, capability mismatch, duplicate IDs, cycles, invalid handoffs, missing required review gates, unsafe fields, and path escape.
- `orchestration collaboration plan|validate|inspect --file <project-local-json>` remains read-only: it does not persist plans or records, probe readiness, start processes, access network/quota/session data, or invoke an Agent.

## Stage 70 Result

- `orchestration control-panel snapshot|render|handoff --collaboration-file <project-local-json>` consumes the Stage 69 safe projection as an optional file-scoped section.
- The JSON snapshot exposes sockets, work items, handoffs, review gates, planned states, and findings; the self-contained HTML renders an accessible dependency graph plus escaped tables.
- Omitting `--collaboration-file` preserves the existing Control Panel shape. Invalid, missing, or escaping plans fail closed without a graph or plan payload.
- No plan persistence, UI write path, readiness probe, process launch, network access, or Agent invocation was added.

## Evidence

- `docs/118-control-panel-collaboration-projection.md`
- `docs/117-collaboration-plan-read-model.md`
- `adapters/collaboration-plan.example.json`
- `docs/archive/release-notes/118-release-notes-stage70-control-panel-collaboration-projection.md`
- Full pytest, focused Ruff, doctor, public scan, CLI snapshot/handoff/render, and diff check passed.

## Stage 71 Result

- Collaboration safe projections now include one routing explanation per explicit socket binding: role, matched capabilities, declared availability, invocation mode, and selection basis.
- Readiness is explicitly `not_collected`; each explanation names a future family-specific contract for `acp_delegate`, `local_cli`, or `agent_api` and records `live_probe_performed=false`.
- The Control Panel renders these explanations as an escaped table. Existing `route preview --explain` remains the routing authority; plans are not silently re-routed.
- No process, session, network, credential, quota, model, or Agent probe was added.

## Evidence

- `docs/119-socket-readiness-evidence-and-routing-explanations.md`
- `docs/118-control-panel-collaboration-projection.md`
- `docs/archive/release-notes/119-release-notes-stage71-socket-readiness-and-routing-explanations.md`

## Next Candidate

Stage 72 may select one socket family and freeze a design-only readiness evidence collection gate. It must not implement a live probe or change selection/execution authority without separate explicit authorization.

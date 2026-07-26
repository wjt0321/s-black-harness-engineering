<!-- parents: 117-collaboration-plan-read-model.md -->
<!-- relates: 47-orchestration-hub-vision.md -->

# 118 - Control Panel Collaboration Projection (Stage 70)

> Status: complete, passive read-only projection
> Date: 2026-07-26

## Scope

Stage 70 consumes the Stage 69 safe plan projection inside the existing read-only Control Panel. `control-panel snapshot`, `render`, and `handoff` accept an optional `--collaboration-file <project-local-json>`:

```text
agent-runtime orchestration control-panel snapshot \
  --collaboration-file adapters/collaboration-plan.example.json --json
agent-runtime orchestration control-panel render \
  --collaboration-file adapters/collaboration-plan.example.json > control-panel.html
agent-runtime orchestration control-panel handoff \
  --collaboration-file adapters/collaboration-plan.example.json --json
```

When the flag is supplied, the snapshot gains a file-scoped `collaboration` section (`scope=file`, `availability=stable_limited`) holding the Stage 69 validated projection. When the flag is omitted, snapshot, render, and handoff payloads are byte-identical to Stage 16–18 behavior.

## Boundary

The projection is passive. It reuses `inspect_collaboration_plan` and never persists plans, writes files or ledgers, probes socket readiness, starts processes, accesses the network, or invokes an Agent. Validation failures fail closed: the section reports `validation_failed` with findings and no plan payload, and the aggregate snapshot status follows the existing section ranking.

The handoff binds the same normalized plan path into both representation `argv` arrays; out-of-root paths normalize to `null` and are never echoed.

## Visualization

`render` adds a deterministic self-contained collaboration view after the reports section:

- an inline SVG graph (no external resources, `role="img"` with a `figcaption` summary) that layers work items by dependency level, draws handoffs as labeled arrows, and shows review gates as dashed-edge diamonds;
- escaped data tables for socket bindings, work items, handoffs, and review gates so the full graph is available without the SVG;
- a boundary callout plus findings table instead of the graph when validation fails.

## Deferred

Stage 70 does not implement plan persistence, readiness evidence, routing selection, execution authority, live board state, or any write path from the panel. Blocked-reason surfaces beyond validation findings remain future work.

<!-- stage70-status: complete-passive-read-only -->

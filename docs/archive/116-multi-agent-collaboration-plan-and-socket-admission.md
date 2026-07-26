<!-- parents: 115-agent-socket-registry-v1.md, 48-adapter-runtime-interface.md, 49-capability-routing-model.md, 50-control-plane-state-model.md -->
<!-- relates: 47-orchestration-hub-vision.md, 114-pi-bound-runner-migration-design.md -->

# 116 — Multi-Agent Collaboration Plan and Socket Admission (Stage 68, Design Only)

> Status: Stage 68 design gate frozen; no Agent invocation authority
> Date: 2026-07-26
> Prerequisite: Stage 67 Socket Registry v1 is complete.

## 1. Product Decision

Agent Runtime is an extensible control plane. An Agent is admitted as a socket; a task is organized as a bounded collaboration plan; the Control Panel presents the resulting task graph, handoffs, artifacts, reviews, and blocked decisions.

A socket is not a special-case integration. Pi, Kimi Code, Claude Code, OMP, QwenPaw Agent API, and future Agents must enter through the same registry-backed contract. Guardrails remain available at side-effect boundaries, but must not force the product roadmap to harden one Agent's local launch chain before the collaboration model exists.

This document defines the admission and planning contracts only. It creates no socket, plan CLI, task, event, artifact, process, session, network request, model call, or write path.

## 2. Socket Admission Contract

### 2.1 Single source and stable identity

The adapter registry remains the single source of socket declarations. A future socket admission implementation MUST project `adapter_type=agent` into the existing Socket Registry; it MUST NOT introduce a second Agent list, per-UI configuration, or hard-coded routing branch.

A socket declaration MUST have:

- a stable lowercase `adapter_id` / `socket_id`, never silently reused for another provider or protocol;
- a human display name and declared capability set;
- an enabled/disabled state and risk level;
- a bounded invocation family: `acp_delegate`, `local_cli`, `agent_api`, or `manual`;
- input/output schema references and explicit approval, session, background, artifact, cancel, timeout, and failure semantics.

The existing `kind` mapping is a legacy source detail. A future schema extension MUST add a generic Agent socket declaration path before accepting an unbounded new `kind` for every provider. New providers should normally select an existing invocation family; a genuinely new transport requires a separately reviewed family contract and cannot be inferred from its display name.

### 2.2 Capability and compatibility rules

Capabilities describe what a socket can be selected to do, not its brand name or a raw command. A new capability MUST be stable, documented, and consumable by routing and the collaboration planner. Provider-only labels, arbitrary command fragments, model identifiers, credentials, endpoint URLs, and operator-specific paths MUST NOT become capabilities.

Admission validation MUST reject or keep unavailable any declaration with:

- duplicate identity or capability ambiguity that changes an existing route silently;
- missing input/output boundary, risk level, timeout, or failure mapping;
- an unknown invocation family;
- arbitrary executable/command/loader/environment fields in registry data;
- secret-bearing, session-bearing, or private runtime data;
- a claimed live state without socket-family-specific readiness evidence.

### 2.3 Lifecycle and extension

Socket lifecycle is explicit:

```text
draft -> declared -> readiness_evidenced -> eligible -> disabled -> deprecated -> removed
```

Stage 67 only exposes `declared` and `disabled`. `readiness_evidenced` is not a generic process ping: it must be separately designed for each invocation family and must remain bounded, non-secret, and non-invoking. `eligible` may be used by routing only after that readiness contract exists.

Disabling a socket stops future selection but preserves historical plan, event, artifact, and audit references. Deprecation communicates a replacement path. Removal requires a migration/audit review; existing records must remain interpretable.

## 3. Collaboration Plan Contract

A collaboration plan is a deterministic, read-only proposal for work distribution. It binds a parent task to selected sockets and bounded roles before any Agent is contacted.

```text
CollaborationPlan
  parent_task_ref
  socket_bindings[]
  work_items[]
  handoffs[]
  review_gates[]
  expected_artifacts[]
```

### 3.1 Required safe fields

A future v1 plan MUST contain:

| Object | Required fields | Meaning |
|:---|:---|:---|
| Plan | `plan_id`, `parent_task_ref`, `status=planned`, `revision`, `socket_registry_identity` | Stable proposal identity and source binding. |
| Socket binding | `socket_id`, `role`, `required_capabilities`, `selection_reason` | Why this socket is eligible for this role. |
| Work item | `work_item_id`, `socket_id`, `role`, `depends_on`, `input_refs`, `expected_artifact_types`, `review_required` | One bounded contribution. |
| Handoff | `from_work_item_id`, `to_work_item_id`, `artifact_types`, `handoff_reason` | Explicit dependency and transferable output. |
| Review gate | `gate_id`, `after_work_item_ids`, `review_role`, `decision_options` | A visible pause before downstream work or side effects. |

All IDs must be deterministic or explicitly supplied, unique within a plan, and display-safe. `plan_id` MUST bind a canonical safe payload including socket identities and registry identity, but excluding raw prompt text, secret values, full paths, session data, and model output.

### 3.2 Roles are not vendors

Initial roles may include `researcher`, `planner`, `implementer`, `tester`, `reviewer`, and `synthesizer`. A role does not select an Agent by itself. Each work item also declares `required_capabilities`; routing then evaluates declared sockets against those capabilities and explicit constraints.

This keeps a workflow stable when a socket is replaced. For example, a `reviewer` work item can request `quality_review` without hard-coding Claude Code; an `implementer` can request `light_coding` or `heavy_coding` without hard-coding Kimi or OMP.

### 3.3 Plan validity

A future implementation MUST fail closed when a plan has:

- an unknown, disabled, or non-Agent socket binding;
- required capability absent from a bound socket;
- duplicate ids, self-dependency, cycle, or orphaned dependency;
- handoff whose source cannot produce its declared artifact type;
- downstream work that consumes an artifact without an upstream handoff;
- review gate referencing unknown work or offering a side-effect decision without the normal approval path;
- raw prompts, credentials, arbitrary command argv, full model output, or unrestricted file paths in public projections.

The planner MUST NOT silently replace a selected socket, add a work item, remove a review gate, or execute a fallback. Such changes require a new deterministic plan revision for review.

## 4. Collaboration States for the Future Board

The board consumes normalized state, not chat transcripts:

```text
planned -> ready -> waiting_on_handoff -> running -> awaiting_review
        -> blocked | failed | canceled | completed
```

A work item may become `ready` only when every dependency and required review gate is satisfied. `running` means an authorized future invocation has started; Stage 68 does not create this state in real data. `awaiting_review` is distinct from approval: review judges work quality or completeness, while approval permits a protected action.

The future Board should show:

- parent task and collaboration plan identity;
- work-item graph with selected socket, role, status, and blocked reason;
- handoff edges annotated only with safe artifact type/count/summary;
- review gates and approvals as visible decision nodes;
- artifacts and evidence in task context; and
- a compact event timeline for traceability.

It must not make raw private Agent conversations the primary control-plane record.

## 5. Invocation Release Boundary

Stage 68 does not authorize inter-Agent communication. A later invocation stage must separately define:

1. the exact request envelope passed to one selected socket;
2. input artifact selection and value-withholding rules;
3. timeout, cancellation, cost/budget, retry, fallback, and failure behavior;
4. started/terminal event and artifact/evidence projection;
5. review before a downstream Agent receives material output; and
6. approval boundaries for writes, external sends, deployment, publication, or other side effects.

The initial release MUST execute at most one declared work item per explicit authorization. It MUST NOT fan out, recurse, or let Agents independently contact other sockets.

## 6. Stop Lines

Stage 68 MUST NOT:

- implement socket admission, registry schema expansion, readiness probes, collaboration-plan CLI, or persistence;
- invoke or contact Pi, Kimi Code, Claude Code, OMP, QwenPaw, or any future socket;
- start a process, access network/quota/session/credential data, or make a model call;
- create task/event/artifact/approval records or alter routing behavior;
- add a service, database, background queue, UI write path, or autonomous loop;
- resume Stage 66 Pi bound-runner migration;
- auto-commit, tag, push, or publish.

## 7. Acceptance Matrix for Later Implementation

A future implementation must prove at least:

1. new sockets use one registry source and project consistently through socket list, inspect, route, and Control Panel;
2. unknown invocation family and unsafe registry fields fail validation without running anything;
3. disabled/deprecated sockets remain historically readable but are not selected for new plans;
4. collaboration plan identity is deterministic and changes when socket/role/capability/handoff/review semantics change;
5. graph validation blocks cycles, unknown bindings, capability mismatch, invalid handoff, and skipped review gates;
6. public plan/board projection excludes secrets, raw prompts, raw model output, session data, arbitrary argv, and unrestricted paths;
7. no plan or registry operation invokes an Agent, consumes quota, writes files, or writes ledgers unless a later explicitly authorized command says otherwise;
8. one-work-item invocation cannot fan out or call another socket without new explicit authorization.

## 8. Next Candidate

**Stage 69 — Collaboration Plan Read Model** may implement a deterministic `orchestration collaboration plan/validate/inspect` surface over declared sockets. It must remain read-only, perform no readiness probes, and create no Agent invocation. Socket admission/schema implementation remains a separate candidate after this plan model proves what fields are actually needed.

<!-- stage68-gate-status: frozen -->
<!-- execution-status: design-only-no-implementation -->

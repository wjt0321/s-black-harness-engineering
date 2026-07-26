<!-- parents: 47-orchestration-hub-vision.md, 48-adapter-runtime-interface.md, 49-capability-routing-model.md -->

# 123 - Multi-Agent Control Hub Current State and Stage 75 Gate

> Status: Stage 75 historical baseline; superseded as current fact source by `124-stage76-manual-collaboration-board.md`
> Date: 2026-07-26

## Plain-Language Goal

This project is a control desk with reusable sockets. Kimi Code, Claude Code, OMP/Pi, and QwenPaw agents are plugs. A user should be able to submit one task, see how it is split, see which plug owns each work item, review handoffs and artifacts, and approve bounded execution from one board.

The guardrails, evidence, and readiness work exist to make that control desk truthful and controllable. They are infrastructure, not the product itself.

## What Exists Now

- A shared registry projects the available Agent sockets and declared capabilities.
- A validated collaboration plan describes roles, work items, dependencies, handoffs, expected artifacts, and review gates.
- The Control Panel renders the plan, socket bindings, routing explanations, dispatch eligibility, and blocked reasons.
- One work item can be converted into a content-addressed dispatch proposal.
- ACP sockets are explicitly bound to runner ids.
- A bounded runner-list snapshot can produce expiring, content-addressed readiness evidence.
- Dispatch verifies plan, work item, socket, runner binding, evidence hash, evaluation time, expiry, artifacts, and review policy.

## What Does Not Exist

- The board cannot yet start a real Kimi, Claude, or OMP collaboration turn.
- It cannot prove that an ACP transport can open a session without sending a prompt.
- It cannot grant execution authority from readiness evidence.
- It does not persist a live collaboration run, timeline, messages, or produced artifacts.
- It has no interactive operator workflow for approve, start, cancel, retry, review, and handoff.
- It does not yet show multiple agents working through one real task end to end.

Current dispatch therefore remains `dispatch_eligible=false` and `execution=not_executed`.

## Stage 75 - ACP Transport and Session-Openability Design Gate

Stage 75 defines the stronger evidence required before a real ACP work-item dispatch can be considered. It does not implement the probe.

### Required Evidence

A future bounded probe must prove all of the following for one explicitly bound runner:

1. the runner remains declared and enabled;
2. the local ACP transport entry is available;
3. a transport handshake completes within a fixed timeout;
4. session initialization can complete without a user prompt or model turn;
5. the probe session is closed immediately and leaves no retained conversation;
6. no model output, quota-consuming request, credential value, or session content is emitted;
7. start and close outcomes are recorded as safe metadata only.

### Proposed Evidence Level

The future level is `session_openable_no_turn`. It is stronger than `runner_listed` but still does not authorize a work-item prompt.

Required fields include:

- socket id, runner id, contract version, probe id;
- observed, evaluated, and expiry timestamps;
- transport handshake status and bounded duration bucket;
- session initialization and close status;
- `prompt_sent=false`, `model_turn_started=false`, `model_output_received=false`;
- `credentials_read=false`, `session_persisted=false`;
- content-addressed evidence id;
- explicit execution-authority decision from a separate policy gate.

### Failure Rules

The future probe must fail closed on timeout, permission request, runner mismatch, unexpected output, session close failure, retained session, schema drift, hash mismatch, or expired evidence. It must never retry automatically.

### Stop Lines

Stage 75 performs no probe and adds no executable path. A future implementation requires separate authorization before it may start a runner or initialize a session. Sending a prompt, invoking a model, consuming quota, accepting a permission request, or dispatching work remains prohibited.

## Direction Decision

Stages 67-71 correctly returned the project to the multi-Agent socket and board model. Stages 72-75 then spent four stages on controlled dispatch and readiness infrastructure. That work is relevant, but continuing deeper into probe mechanics would make the project infrastructure-led again.

After Stage 75, the recommended product milestone is a usable collaboration board over the existing safe read models:

- task intake and plan review;
- work-item lanes by Agent socket;
- handoff and artifact timeline;
- clear blocked/ready/approval states;
- one operator-controlled action surface;
- a simulated or fixture-backed end-to-end collaboration walkthrough before any real Agent dispatch.

Only after that board exposes the exact operator workflow should the project implement the no-prompt ACP probe and one real work-item dispatch. This keeps safety work driven by a visible product need.

## Archived Detail

Detailed Stage 67-74 design and implementation records are retained under `docs/archive/115-*.md` through `docs/archive/122-*.md`. They are historical evidence, not the current reading path.

<!-- stage75-status: complete-design-only -->

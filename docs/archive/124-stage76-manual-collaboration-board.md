<!-- parents: 47-orchestration-hub-vision.md, 123-multi-agent-control-hub-current-state-and-stage75-gate.md -->

# 124 - Stage 76 Manual Collaboration Board

> Status: implemented and locally verified
> Date: 2026-07-26

## Plain-Language Decision

The operator may split a task manually. This is now the default product direction.

The intended planning modes are:

1. `manual`: the operator chooses the work items, Agent sockets, dependencies, handoffs, artifacts, and review points;
2. `suggested`: the system proposes a split, but the operator must review and confirm it;
3. `automatic`: reserved for later and not enabled.

Stage 76 implements the first mode as a validated, fixture-backed walkthrough. It does not call an Agent.

## What Was Added

- `adapters/manual-collaboration-board.schema.json` defines the strict fixture shape.
- `adapters/manual-collaboration-board.example.json` records an operator-authored example with three work items.
- `orchestration collaboration manual-board inspect` validates the fixture against the existing collaboration plan.
- Control Panel section 11 renders:
  - an operator-authored planning banner;
  - one work lane per manually assigned Agent socket;
  - dependency, expected artifact, fixture artifact, and review state;
  - a handoff and artifact timeline;
  - disabled operator controls that show the future workflow.
- Control Panel snapshot, render, and handoff accept `--manual-board-file`.

## Example Walkthrough

The included example is intentionally simple:

- Kimi Code plans;
- OMP implements;
- Claude Code reviews;
- the plan artifact is handed to implementation;
- patch and test-result artifacts are handed to review;
- the review gate is approved.

Every lane and action is labelled `simulated`. No prompt was sent, no model turn started, no quota was consumed, and no execution authority was granted.

## How To Inspect It

```text
python -m agent_runtime.cli orchestration collaboration manual-board inspect --file adapters/manual-collaboration-board.example.json --json
```

```text
python -m agent_runtime.cli orchestration control-panel render --collaboration-file adapters/collaboration-plan.example.json --manual-board-file adapters/manual-collaboration-board.example.json
```

The generated local walkthrough is `build/manual-collaboration-board.html`.

## Validation Boundary

The manual board fails closed when:

- a work item is missing or unknown;
- fixture artifacts do not match the planned artifact contract;
- review state contradicts `review_required`;
- timeline sequence is not contiguous;
- a timeline event references an unknown work item;
- a produced artifact does not match the work item contract;
- the referenced collaboration plan is invalid;
- a file path escapes the project root.

The existing collaboration plan hash and dispatch contract were not changed.

## Still Not Implemented

- editing the task split directly inside the HTML board;
- saving a board from a form;
- system-generated split suggestions;
- approve, start, cancel, retry, request-changes, or approve-handoff actions;
- live Agent sessions, messages, artifacts, or run persistence;
- the Stage 75 no-prompt ACP session-openability probe;
- one real controlled work-item dispatch.

## Recommended Next Milestone

Stage 77 should add a local operator editing workflow for the manual plan, but remain non-executing:

1. edit task title and work-item rows;
2. choose an Agent socket from the registry;
3. choose dependencies, expected artifacts, and review requirements;
4. validate and preview the resulting collaboration plan;
5. require explicit operator confirmation before the fixture becomes eligible for any later dispatch proposal.

Real Agent dispatch should remain deferred until this editing and confirmation workflow is clear enough to drive the exact approval semantics.

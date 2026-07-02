# 0001 — Project Location

## Decision

The long-term Agent Runtime project lives outside the primary agent workspace.

For the current local development environment, the working directory is:

```text
D:\agent-runtime
```

## Rationale

This project is meant to become an independent Agent Runtime / Harness Orchestrator. It should not be tightly coupled to a single host workspace, otherwise the runtime design would inherit that workspace's assumptions, tools, and boundaries.

Keeping it in a separate project directory makes the intended boundary explicit:

- This is an independent long-term project.
- QwenPaw is expected to become one adapter, not the whole runtime boundary.
- The repository should be understandable outside the original local workspace.

## Impact

- The first phase remains documentation, schemas, and examples.
- The project does not automatically take over existing host workflows or scheduled jobs.
- Scripts and tests should run with the project directory as their explicit working directory.
- Local absolute paths in examples should be treated as placeholders and avoided in public sample files.

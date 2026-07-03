# 11 — v0.1 Release Notes

## Version

`v0.1.0-planning-poc`

## Summary

This release freezes the first planning and read-only CLI proof of concept for `s-black harness engineering`.

The project now has a documented runtime boundary, policy model, task state model, agent registry, adapter registry, policy-to-task bridge, and a minimal CLI that can inspect the repository without executing external actions.

## Highlights

- Project structure and public README are in place.
- Policy schema and sample policies are available.
- Task and event JSONL schemas are available.
- Agent registry schema and sample registry are available.
- Adapter registry schema and sample adapters are available.
- Policy results are mapped to task state transitions.
- Minimal read-only CLI is implemented.
- Read-only task ledger queries are implemented.
- Action preflight now aggregates adapter risk, command rules, publish rules, and completion rules.
- Policy profile selection is available through `--policy-profile`.
- Local read-only task ledger examples are available in `tasks/tasks.jsonl` and `tasks/events.jsonl`.

## CLI Commands

Current CLI entry points:

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli check action --adapter github-cli --operation git_push --target origin/main
python -m agent_runtime.cli task status task-20260703-001
python -m agent_runtime.cli task events task-20260703-001
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
python -m agent_runtime.cli --policy-profile s-black policies
```

## Safety Boundary

This release remains read-only.

It does not:

- execute external commands
- access the network
- send messages
- delete files
- write task ledger records through the CLI
- read `.env`, `.env.local`, or credential files
- print full secret matches

## Validation

The release has been validated with:

```text
python -m pytest tests -q
python -m agent_runtime.cli doctor
public repository scan
```

Expected current result:

```text
34 passed
PASS
OK public scan
```

## Known Limits

- No background service exists yet.
- No real adapter execution layer exists yet.
- Task ledger files are still local JSONL files.
- The CLI can query task records, but it does not write task records.
- Policy profiles are selected manually; automatic agent-to-policy mapping is not implemented yet.
- Package metadata and a console script are available for local development, but the documented default remains `python -m agent_runtime.cli`.

## Recommended Next Steps

1. Add preflight schema validation for future ledger writes while keeping writes disabled.
2. Add automatic agent-to-policy profile mapping.
3. Productize the public repository scan as a sanitized in-repository tool before adding it to CI.
4. Design the adapter execution envelope without connecting real external systems yet.

# Release Notes - Stage 71 Socket Readiness and Routing Explanations

> Date: 2026-07-26
> Status: included in v0.19.0 multi-Agent collaboration board milestone

## Added

- Safe `routing_explanations` for explicit collaboration-plan socket bindings.
- Declared capability match, invocation mode, and socket-family readiness contract names.
- A Control Panel table for routing explanations.

## Safety Boundary

- Readiness remains `not_collected`; every explanation records `live_probe_performed=false`.
- No process, session, network, credential, quota, model, or Agent probe was performed.
- Existing `route preview --explain` remains the routing authority; collaboration plans are not silently re-routed.

## Verification

- Focused tests cover ACP delegate, local CLI, and Agent API readiness-contract mappings.
- Full regression, static checks, real CLI/HTML rendering, public scan, doctor, and diff check are required before completion.

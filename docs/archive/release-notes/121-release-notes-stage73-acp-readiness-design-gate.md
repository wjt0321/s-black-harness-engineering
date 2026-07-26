# Release Notes - Stage 73 ACP Readiness Collection Design Gate

> Date: 2026-07-26
> Status: included in the next ACP readiness milestone

## Added

- Explicit ACP socket-to-runner bindings.
- A bounded QwenPaw ACP runner-list snapshot contract.
- Content-addressed readiness evidence with explicit evaluation time and TTL.

## Safety Boundary

- Runner presence is not session readiness, model availability, or execution authority.
- No runner, session, prompt, model, credential, network, quota, or write action is allowed.
- Initial evidence is hard-bound to `sufficient_for_dispatch=false`.

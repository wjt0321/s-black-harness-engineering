<!-- parents: 102-pi-interactive-approval-roundtrip.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 97-execution-lifecycle-audit-writer-design-and-implementation.md -->

# 103 - Pi Postflight Audit Projection v1 (Stage 54)

> 状态：Stage 54 v1 已实现并完成本地 Node 验证
> 日期：2026-07-25
> 里程碑：本地 commit-level；不创建 tag，不自动 push

## 1. 阶段结论

Stage 54 在 Pi/OMP `tool_result` hook 上增加默认关闭的 postflight projection。它只生成 host-side、value-free 的结果摘要块，不写 Harness ledger，不访问网络，不执行工具，不改变工具成功/失败语义。

该 projection 的目的不是证明 Harness 执行了工具，而是在 Pi/OMP 已经执行完工具后，为会话内后续模型/人工审查追加一个脱敏绑定摘要。

## 2. 启用方式

默认关闭。只有显式设置：

```text
AGENT_RUNTIME_POSTFLIGHT_MODE=summary
```

同时仍需：

```text
AGENT_RUNTIME_ROOT=<Harness repository root>
AGENT_RUNTIME_PYTHON=<optional Python launcher>
```

## 3. 绑定方式

`tool_result` 收到结果后，extension 使用当前 `event.input` 重新构造 Stage 52 bridge request 并再次运行 `pi-bridge preflight`。

摘要只包含：

- tool name；
- bridge decision；
- original `isError` flag；
- bridge `request_id`；
- bridge `request_hash`；
- bridge `target_hash`；
- hashed `toolCallId`；
- content block counts；
- text block character count；
- static guarantees `writes_ledgers=false`、`executes_tools=false`。

摘要不包含 path、command、file content、tool output text、stderr/stdout text、details payload 或 credential-like values。

## 4. Result semantics

Stage 54 returns a `content` patch that preserves the original result content and appends one text summary block. It does not return `isError`, so Pi/OMP's existing success/failure status remains unchanged. It does not patch `details`.

If the mode is disabled, the tool is outside the gated default set, or the input cannot be normalized, the handler returns `undefined` and leaves the result unchanged.

## 5. Safety boundaries

- No persistent audit writer in this stage.
- No approval ledger.
- No cross-session or cross-process audit authority.
- No network calls.
- No second command or wider shell authority.
- No claim that Harness executed the tool.
- No final-arguments authority beyond re-preflighting the current `tool_result.input` supplied by Pi/OMP.

This remains a host-side projection. If future stages need durable audit, they must separately design and implement a bounded writer with explicit event schema, identity binding, result redaction rules, rollback semantics and post-checks.

## 6. Verification

`integrations/pi/test/preflight-bridge.test.ts` now covers 22 cases, including:

- default-off postflight projection;
- pass summary without echoing output or path;
- blocked summary without echoing sensitive target;
- unchanged `isError` semantics;
- ignored ungated/malformed tool results.

No real `git push` was executed. No Pi/OMP persistent configuration was modified.

## 7. Next candidate

Next candidate: Stage 55 - Pi Extension Install / Operator Handoff Gate. It should decide whether to install the extension persistently into the local Pi/OMP extension directory, how to handle coexistence with existing Orca extensions, and what exact smoke should prove persistent discovery without modifying user workflows unexpectedly.

<!-- stage54-status: implemented-local -->
<!-- authority: host-side-postflight-projection-only -->
<!-- next-stage: stage55-pi-extension-install-operator-handoff-gate -->

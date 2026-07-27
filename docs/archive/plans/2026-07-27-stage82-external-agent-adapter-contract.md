# Stage 82 External Agent Adapter Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 冻结 transport-neutral 的外部 Agent adapter contract、approval/dispatch authority 边界、failure matrix、测试计划与 GUI 最小 live read model，同时保持 design-only、零真实执行。

**Architecture:** 使用一个 contract bundle schema 描述统一 identity/capability/readiness/session/dispatch/event/cancel/artifact/recovery/approval/audit 语义，并以 ACP、CLI、local process 三类 fixture 证明 transport-neutral。另设独立 live read model schema，为中文 GUI 提供有界、安全、确定性的 Agent、任务、事件、审批、artifact 与 recovery 投影；不接入 CLI、执行器、ledger 或 live adapter。

**Tech Stack:** JSON Schema draft 2020-12、JSON fixture、Python 3.11、jsonschema、pytest、Markdown。

---

### Task 1: 写失败的 Stage 82 契约测试

**Files:**
- Create: `tests/test_external_agent_adapter_contract.py`

1. 校验两个 schema 自身合法且示例通过验证。
2. 校验示例覆盖 ACP、CLI、local process，以及 Planner、Executor、Reviewer。
3. 校验结构化 dispatch 不包含 argv/cwd/env/shell/command 等旁路。
4. 校验 readiness、approval、lease、expected state、idempotency、event ordering、terminal 和 outcome unknown 语义。
5. 校验 GUI 投影有界、中文默认、安全且固定不授权执行。
6. 运行专项测试，确认因 Stage 82 资产不存在而失败。

### Task 2: 实现 contract schema 与三 transport 示例

**Files:**
- Create: `adapters/external-agent-adapter-contract.schema.json`
- Create: `adapters/external-agent-adapter-contract.example.json`

1. 冻结稳定 identity/version/transport/capability binding。
2. 冻结 readiness evidence 来源、TTL、binding、stale/fail-closed。
3. 冻结 Harness run/attempt 与外部 session mapping。
4. 冻结结构化 work-item dispatch、approval evidence、lease、expected state 和 idempotency。
5. 冻结 ordered event、dedup、disconnect、cancel、artifact、review、recovery 与唯一 terminal audit。
6. 示例只使用 fixture，所有真实执行/探测/ledger 标志为 false。

### Task 3: 实现 GUI 最小 live read model

**Files:**
- Create: `adapters/external-agent-live-read-model.schema.json`
- Create: `adapters/external-agent-live-read-model.example.json`

1. 投影 Agent 状态、capability、transport、readiness、session、当前任务。
2. 投影 work item、recent event、pending approval、artifact、recovery item。
3. 限制数组、字符串和摘要大小；不暴露原始输出、路径、凭据或任意执行参数。
4. 中文标签与安全摘要为 GUI 默认显示字段。

### Task 4: 编写 Stage 82 事实源与 failure matrix

**Files:**
- Create: `docs/131-stage82-external-agent-adapter-contract-and-mvp-boundary.md`

1. 记录权威边界、共同 transport 语义和状态机。
2. 列出稳定 failure code、phase、terminal effect、retry/recovery 行为。
3. 给出 schema/fixture、未来 conformance、live integration 三层测试计划。
4. 冻结 MVP 验收线和 Stage 82 停止线。

### Task 5: 更新恢复入口与里程碑状态

**Files:**
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-26.md`
- Archive: `docs/plans/2026-07-27-stage82-external-agent-adapter-contract.md`

将 Stage 82 标记为 design-only 完成；下一候选设为外部 Agent 只读 live status adapter 的独立 design gate，真实调用继续要求再次明确授权。

### Task 6: 完整验证

1. 运行 Stage 82 专项测试并确认通过。
2. 运行 `python -m pytest tests -q`。
3. 运行 `python -m agent_runtime.cli doctor`。
4. 运行 `python tools/public_scan.py`。
5. 运行 docs context、Markdown 相对链接检查、`git diff --check` 和 `.githooks/pre-commit`（环境可用时）。
6. 不调用 Agent、不启动 session、不探测 readiness、不读取真实 approval ledger、不提交或推送。

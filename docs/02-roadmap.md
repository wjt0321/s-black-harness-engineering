# 02 — 路线图

> 本页只记录能力包和下一候选。逐 Stage 历史已归档到 `docs/archive/`，治理前长版见 `archive/snapshots/2026-07-26/02-roadmap.md`。

## 已完成能力包

### 1. Guardrail 与账本内核

- Policy/schema、secret scan、路径与 action gate。
- Task/Event ledger、Runtime report、execution envelope。
- Dry-run、plan hash、受控追加、写后校验和失败回滚。

### 2. Orchestration 控制面

- Source-backed agent/adapter registry。
- Capability routing、decision trace、profile/workflow/contract 校验。
- Task/Run/Approval/Artifact read model 与 recovery lineage。
- 静态只读 Control Panel、one-shot producer/consumer/host 管道。

### 3. 受控执行基础设施

- Machine-local lease 与 executable trust binding。
- Started/terminal execution audit、open-attempt recovery、audit v2。
- Windows Job Object tree containment、bounded stdout/stderr、safe projection。

### 4. Agent Socket Registry v1 and Collaboration Planning

- Stage 68 freezes socket admission/lifecycle rules and the deterministic multi-Agent collaboration plan contract: roles, work items, handoffs, expected artifacts, and review gates.
- Future Agent additions must use the shared registry/socket contract; they cannot add custom routing or UI branches.
- Stage 68 remains design-only: no plan persistence, readiness probe, or Agent invocation.

### 5. Agent Socket Registry v1

- Pi、Kimi Code、Claude Code、OMP 与 QwenPaw Agent API 统一以 Agent socket 投影进入 control plane。
- 同一 source-backed adapter registry 继续是唯一事实源；socket 显示 declared capability、invocation mode 和边界，不探测在线状态或调用 Agent。
- `orchestration socket list` / `orchestration socket inspect <socket_id>` 与 Control Panel adapters 区可见插头拓扑。

### 6. Controlled Collaboration Dispatch Foundation

- 单个 collaboration work item 可生成 schema-validated、content-addressed dispatch proposal。
- CLI 与 Control Panel 只读展示 `plan_eligible`、`dispatch_eligible`、blocked reasons 和 `execution=not_executed`。
- ACP readiness evidence 仅冻结静态契约；未实现 collector、eligibility binding 或真实派发。

### 7. ACP Readiness Evidence Foundation

- ACP socket 显式绑定 runner id，并可从项目内受限 runner-list snapshot 生成内容寻址、带 TTL 的 evidence。
- collector 仅证明 `available/runner_listed`，不启动 runner、不打开 session、不发送 prompt，也不读取凭据。
- dispatch 校验证据哈希、socket binding 与过期时间；当前仍固定 `sufficient_for_dispatch=false`、`dispatch_eligible=false`。

### 8. 当前真实 operation

- fixed Git status：固定 `git status --short --branch`。
- fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`。

Stage 62 真实 smoke 已通过 DeepSeek：child exit 0、audit closed、Job accounting 与进程回收完整。当前事实源为 `111-pi-controlled-dry-run-print-implementation.md`。

## 当前停止线

- 不开放通用 shell 或任意 adapter execution。
- 不开放 POSIX fallback。
- 不开放网络 adapter、服务、数据库或自动后台执行。
- Pi 不开放 read/write/edit/bash 工具，也不保存 session。
- Stage 63–65 的 Pi npm/Node runtime binding 与 runner migration 设计保留为 deferred security work；不再作为当前产品主线。
- 新增真实 operation、live Agent readiness 或 Agent-to-Agent invocation 必须独立设计、测试和用户授权。

## 下一产品里程碑

Stage 76-81 已完成人工计划看板、fixture 端到端演示、中文默认 UI/UX、浏览器内存编辑器、候选校验与导出、协作运行事件模型、checkpoint 操作资格，以及只聚合最新状态的操作者待办和审批集合。后续优先级：

1. **Stage 82 真实 approval ledger 接入前的安全审查与只读契约收口**：审查 fixture approval、current inbox、受控写入审计和未来 readiness probe 的字段与授权边界；不读取或修改真实 ledger。
2. **真实审批绑定设计**：只有 Stage 82 明确独立授权、写入事务、审计和回滚契约后才允许设计；current inbox 仍不得被解释为授权。
3. **无 prompt ACP 探针实现**：只有当前态资格契约明确需要真实 readiness 时才恢复，并需单独授权启动 runner/session。
4. **单 work-item 真实派发**：在探针、真实审批绑定、取消、重试、审阅、交接和 artifact 回收契约齐备后另行设计和授权。

Stage 65 Pi bound runner migration 设计已归档为 `archive/114-pi-bound-runner-migration-design.md`，继续作为 deferred 安全强化项，不抢占产品主线。人工计划“已确认”不得被解释为派发授权。

## 治理原则

- 能合并到现有事实源就不新增 Stage 文档。
- 已完成的 design、implementation、plan、smoke 和 release notes 立即归档。
- `README*`、`AGENTS.md`、`00-index`、`000-stage-digest` 保持短小，只描述当前状态。
- 版本治理详见 `64-versioning-governance.md`。

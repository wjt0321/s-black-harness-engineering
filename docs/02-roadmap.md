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

### 7. 当前真实 operation

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

## 下一候选

优先级从高到低：

1. **Stage 73 readiness collection design gate**：仅为一个 socket family 冻结有界证据采集、过期、withholding 与 eligibility binding；未获独立授权前不实现 live probe 或 Agent 调用。
2. **Stage 66 Pi bound runner migration**：保留为 deferred security work；只有 Pi 成为明确优先执行器且获独立授权时再恢复。
3. **canonical approval binding**：继续作为安全内核的独立强化项，不阻塞协作主线。

## 治理原则

- 能合并到现有事实源就不新增 Stage 文档。
- 已完成的 design、implementation、plan、smoke 和 release notes 立即归档。
- `README*`、`AGENTS.md`、`00-index`、`000-stage-digest` 保持短小，只描述当前状态。
- 版本治理详见 `64-versioning-governance.md`。

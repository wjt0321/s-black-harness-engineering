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

### 4. Agent Socket Registry v1

- Pi、Kimi Code、Claude Code、OMP 与 QwenPaw Agent API 统一以 Agent socket 投影进入 control plane。
- 同一 source-backed adapter registry 继续是唯一事实源；socket 显示 declared capability、invocation mode 和边界，不探测在线状态或调用 Agent。
- `orchestration socket list` / `orchestration socket inspect <socket_id>` 与 Control Panel adapters 区可见插头拓扑。

### 5. 当前真实 operation

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

1. **Stage 68 multi-Agent collaboration plan design gate**：先把 parent task、selected sockets、角色、预期 artifact、review point 与 handoff 关系做成确定性只读计划。
2. **Socket-specific readiness design**：只在明确需要时，为不同 invocation mode 定义有界、非秘密、非调用的 readiness 证据；不将 declared 误称为在线。
3. **Capability routing explanation**：让 route preview 清楚展示为什么选择某个插头、哪些可替代及风险/成本约束。
4. **Stage 66 Pi bound runner migration**：保留为 deferred security work；只有 Pi 成为明确优先执行器且获独立授权时再恢复。
5. **canonical approval binding**：继续作为安全内核的独立强化项，不阻塞协作主线。

## 治理原则

- 能合并到现有事实源就不新增 Stage 文档。
- 已完成的 design、implementation、plan、smoke 和 release notes 立即归档。
- `README*`、`AGENTS.md`、`00-index`、`000-stage-digest` 保持短小，只描述当前状态。
- 版本治理详见 `64-versioning-governance.md`。

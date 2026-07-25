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

### 4. 当前真实 operation

- fixed Git status：固定 `git status --short --branch`。
- fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`。

Stage 62 真实 smoke 已通过 DeepSeek：child exit 0、audit closed、Job accounting 与进程回收完整。当前事实源为 `111-pi-controlled-dry-run-print-implementation.md`。

## 当前停止线

- 不开放通用 shell 或任意 adapter execution。
- 不开放 POSIX fallback。
- 不开放网络 adapter、服务、数据库或自动后台执行。
- Pi 不开放 read/write/edit/bash 工具，也不保存 session。
- npm/node chain 尚未形成完整 trusted executable identity。
- 新增真实 operation 必须独立设计、测试和用户授权。

## 下一候选

优先级从高到低：

1. **Pi TUI 人工验收**：operator 在真实终端验证交互入口，不改变 Harness 权限。
2. **npm identity binding design gate**：解决 Pi npm shim → node → cli.js 的可信链问题。
3. **Pi read roundtrip design gate**：仅研究 read containment 与 preflight 复用，不直接开放工具。
4. **canonical approval binding**：把批准对象与固定 plan/runtime identity 更严格绑定。
5. **里程碑冻结**：在能力边界稳定后再决定是否创建新的 semver tag。

## 治理原则

- 能合并到现有事实源就不新增 Stage 文档。
- 已完成的 design、implementation、plan、smoke 和 release notes 立即归档。
- `README*`、`AGENTS.md`、`00-index`、`000-stage-digest` 保持短小，只描述当前状态。
- 版本治理详见 `64-versioning-governance.md`。

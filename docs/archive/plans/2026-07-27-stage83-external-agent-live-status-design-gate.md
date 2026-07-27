# Stage 83 External Agent Read-Only Live Status Adapter Design Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为一个外部 Agent 冻结零 session、零 prompt、零凭据、零网络、零进程启动的只读 live status observation contract，并证明其不能产生 dispatch authority。

**Architecture:** 选择 `omp-acp` 作为首个目标，但使用 transport-neutral 的 adapter-owned atomic snapshot contract。未来 Harness reader 只能读取固定 `.runtime/external-agent-status/omp-acp.v1.json`，验证 regular-file/containment/atomicity/size/schema/TTL/identity/producer binding，并生成 normalized evidence 与 Stage 82 GUI mapping；Stage 83 不实现 reader，也不创建真实 snapshot。

**Tech Stack:** JSON Schema draft 2020-12、JSON fixture、Python 3.11、jsonschema、pytest、Markdown。

---

### Task 1: 编写失败的 Stage 83 契约测试

**Files:**
- Create: `tests/test_external_agent_live_status_design_gate.py`

1. 校验 snapshot 与 adapter design schema 自身合法、fixture 通过。
2. 校验目标固定为 `omp-acp`，生产路径固定且无路径覆盖。
3. 校验 64 KiB、TTL 1-60 秒、regular file、无 symlink/reparse/hardlink、稳定读与原子 replace 契约。
4. 校验零进程、零 ACP 连接、零 session/prompt/model/credential/network/write/dispatch authority。
5. 校验 normalized evidence 永不声明 ready，且映射兼容 Stage 82 GUI 状态。
6. 校验 failure matrix、替代方案 deferred 和停止线。
7. 运行专项测试，确认因 Stage 83 资产不存在而失败。

### Task 2: 冻结通用状态快照 schema

**Files:**
- Create: `adapters/external-agent-status-snapshot.schema.json`
- Create: `adapters/external-agent-status-snapshot.example.json`

定义 producer/target identity binding、snapshot id、generation、complete marker、观察时间、安全 transport/session 摘要和无副作用 attestation；禁止原始输出、endpoint、PID、session identity 或凭据字段。

### Task 3: 冻结 live status adapter design contract

**Files:**
- Create: `adapters/external-agent-live-status-adapter.schema.json`
- Create: `adapters/external-agent-live-status-adapter.example.json`

定义固定生产路径、reader/producer policy、TTL、normalized evidence、GUI mapping、failure matrix 与 implementation authorization=false。

### Task 4: 编写 Stage 83 事实源

**Files:**
- Create: `docs/132-stage83-external-agent-read-only-live-status-adapter-design-gate.md`

记录方案比较、选择理由、数据流、文件边界、evidence 状态机、GUI 映射、failure matrix、测试计划、Stage 84 gate 与停止线。

### Task 5: 更新恢复入口并归档 Stage 82

**Files:**
- Archive: `docs/131-stage82-external-agent-adapter-contract-and-mvp-boundary.md`
- Archive: this plan
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/130-gui-first-external-agent-control-plane-target.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-27.md`

将 Stage 83 标为 design-only completed；下一候选设为 Stage 84 bounded snapshot reader implementation，真实 producer/probe 仍需独立授权。

### Task 6: 完整验证

运行 Stage 83 专项、full pytest、doctor、原样 public scan、docs context、Markdown link audit、活跃文档数、pre-commit 和 diff check。不得调用 Agent、创建 snapshot、启动 session、连接 ACP、读取凭据、提交或推送。

# Stage 84 Bounded Atomic Snapshot Reader Implementation Plan

> **For Codex:** Use test-driven development and verification-before-completion; do not delegate unless explicitly requested.

**Goal:** 实现固定 `.runtime/external-agent-status/omp-acp.v1.json` 的 bounded、只读、fail-closed reader，输出 normalized evidence、Stage 82 兼容 GUI 投影、deterministic JSON 与 stable failure code。

**Architecture:** reader 只读取仓库内固定 snapshot 路径和已跟踪的 reviewed read binding；通过 lstat-first、regular-file/no-indirection/no-hardlink、64 KiB、descriptor identity、stable stat、strict UTF-8 JSON、schema、content identity、producer/target binding、显式评估时间、15 秒 TTL 与显式 previous generation 校验后生成证据。任何失败都只输出安全中文提示，不释放源文件内容；reader 不写文件、不联系 Agent、不启动进程、不连接 ACP、不创建 session，也不授予 dispatch authority。

**Tech Stack:** Python 3.11、标准库、jsonschema、pytest、现有 argparse CLI/result contract、JSON Schema draft 2020-12。

---

### Task 1: 冻结 reader API、binding 与 evidence contract

**Files:**
- Create: `adapters/external-agent-live-status-binding.schema.json`
- Create: `adapters/external-agent-live-status-binding.json`
- Create: `adapters/external-agent-live-status-evidence.schema.json`
- Create: `tests/test_external_agent_live_status_reader.py`

1. 先写失败测试，固定 production path、15 秒 TTL、64 KiB、target/producer binding 和零权限 guarantees。
2. 定义 snapshot/evidence content digest 规则：对移除自身 id 后的 canonical JSON 计算 SHA-256。
3. 校验 schema 自身、binding 和 Stage 83 fixture。

### Task 2: 实现 bounded stable reader

**Files:**
- Create: `agent_runtime/orchestration_external_agent_live_status.py`
- Modify: `tests/test_external_agent_live_status_reader.py`

按 RED→GREEN 覆盖 missing、directory、symlink、reparse、hardlink、oversize、UTF-8/JSON/schema、incomplete、stable-stat drift、content id drift、future、expiry、generation replay、producer/target drift、runner missing、unknown presence 和 unbound open session。所有读取保持 project-contained、fixed-path-only、read-only。

### Task 3: 生成 normalized evidence 与 Stage 82 GUI 投影

**Files:**
- Modify: `agent_runtime/orchestration_external_agent_live_status.py`
- Modify: `tests/test_external_agent_live_status_reader.py`

1. observed/unavailable/stale/blocked 映射到 Stage 82 enum。
2. 固定 `sufficient_for_dispatch=false`、`execution_authorized=false`、`session_binding=null`、`event_cursor=null`。
3. projection schema 校验失败必须 fail closed 为 `status_projection_invalid`。

### Task 4: 接入只读 CLI 与 discovery contract

**Files:**
- Modify: `agent_runtime/cli.py`
- Modify: `agent_runtime/orchestration_contract.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_orchestration_contract.py`
- Modify: `docs/10-cli-poc-usage.md`

新增 `orchestration external-agent status inspect --evaluated-at ... [--expected-after-generation ...]`。禁止 snapshot path、TTL、producer 或 transport override；JSON 稳定，human output 默认简体中文。

### Task 5: 更新事实源与恢复入口

**Files:**
- Create: `docs/133-stage84-bounded-atomic-snapshot-reader-implementation.md`
- Archive: this plan to `docs/archive/plans/`
- Archive: `docs/132-stage83-external-agent-read-only-live-status-adapter-design-gate.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/130-gui-first-external-agent-control-plane-target.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-27.md`

记录 Stage 84 reader 已实现但 producer/probe 仍未授权；下一阶段只能是独立 producer/probe design gate 或 GUI host integration design gate，不能默认扩权。

### Task 6: 完整验证

运行 Stage 84 专项、Stage 82-84 contract、full pytest、doctor、public scan、docs context、Markdown link/path audit、活跃文档数、`git diff --check` 和 pre-commit。不得创建 production snapshot、调用 Agent、启动进程、连接 ACP、读取凭据、写 ledger、commit 或 push。

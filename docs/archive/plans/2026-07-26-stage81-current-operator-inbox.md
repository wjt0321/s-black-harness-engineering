# Stage 81 当前态操作者待办与审批集合 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于一个项目内 current-run fixture 和 fixture approval 集合，生成最新运行状态下的操作者待办、当前操作资格、待处理审批和稳定阻止原因；不读取真实 approval ledger，不授予执行权。

**Architecture:** 新增独立 current-run fixture 与 operator-inbox fixture。current-run 复用 Stage 79 schema 和事件重放校验，但只保留一个处于 `blocked` 的最新运行前缀；inbox validator 读取最新 run projection，按固定 action/state 矩阵检查当前目标、当前 attempt、审批精确绑定、重复幂等键和 pending approval，生成只读 inbox projection。CLI、Control Panel 和 handoff 只消费该投影，不调用 Stage 80 历史 checkpoint evaluator 来避免把历史资格误当成当前资格。

**Tech Stack:** Python 3.11、标准库、jsonschema、argparse、自包含 HTML、pytest。

---

## 冻结设计

当前态只允许从 latest run projection 推导：

- `approve_start`：run / `awaiting_approval`；
- `cancel`：run / `ready|running|blocked`；
- `retry`：latest work item attempt / `changes_requested|failed`；
- `request_changes`：current review / `in_review`；
- `approve_handoff`：current handoff / `ready`。

每条 inbox action request 绑定 run id、run projection id、action、target type/id 和 expected state。审批绑定必须精确匹配这些字段；审批状态为 `pending` 的记录进入待处理审批集合，但不产生执行候选。历史 attempt、历史 review 和已 accepted handoff 不得被重新解释为当前目标。

### Task 1: 编写失败测试与 fixture 契约

**Files:**
- Create: `tests/test_orchestration_collaboration_operator_inbox.py`
- Create later: `adapters/collaboration-run-state-current.example.json`
- Create later: `adapters/collaboration-operator-inbox.schema.json`
- Create later: `adapters/collaboration-operator-inbox.example.json`

1. 测试 current run projection、5 条当前 action、1 个 eligible cancel、4 个 blocked action 和 1 条 pending approval。
2. 测试路径逃逸、schema 失败、run source 失败、审批绑定漂移、pending approval、历史 target/stale target、已记录幂等键和同一投影重复 action。
3. 测试 CLI 确定性、无 argv/cwd/env、`execution_authorized=false`。
4. 先运行并确认因模块和 fixture 不存在而失败。

### Task 2: 实现 current-run/inbox 校验器

**Files:**
- Create: `adapters/collaboration-run-state-current.example.json`
- Create: `adapters/collaboration-operator-inbox.schema.json`
- Create: `adapters/collaboration-operator-inbox.example.json`
- Create: `agent_runtime/orchestration_collaboration_operator_inbox.py`

1. 复用 Stage 79 current-run schema/事件校验，保持 project containment 和 128 KiB 限制。
2. 读取最新 run projection，构建 current attempts、reviews、handoffs 的实体索引。
3. 校验 action/target/state 矩阵，只允许 latest/current target。
4. 校验审批精确绑定、pending 集合、recorded idempotency keys 和投影内重复命令。
5. 生成 current inbox rows、pending approvals、eligible command candidates、blocked reasons 和 deterministic projection id。
6. 不读取真实 approval ledger，不写文件或 ledger。

### Task 3: 接入 collaboration CLI

**Files:**
- Modify: `agent_runtime/cli.py`
- Modify: `tests/test_orchestration_boundary_contract.py`

新增：

```text
orchestration collaboration inbox inspect --file <json> --json
```

### Task 4: 接入 Control Panel 与 handoff

**Files:**
- Modify: `agent_runtime/orchestration_control_panel.py`
- Modify: `agent_runtime/cli.py`
- Create: `tests/test_orchestration_control_panel_operator_inbox.py`

1. 为 snapshot/render/handoff 增加 `--collaboration-inbox-file`。
2. 增加中文“协作 / 当前待办”区段。
3. 展示当前 Run、待处理审批、当前 action、阻止原因、幂等候选。
4. 五个控件仍全部 disabled，标记“当前待办不是执行授权”。
5. invalid fixture fail closed；省略参数保持旧 shape。

### Task 5: 文档整理与归档

**Files:**
- Create: `docs/129-stage81-current-operator-inbox-and-approval-collection.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-26.md`
- Archive: `docs/128-stage80-operator-action-eligibility-and-approval-binding.md`
- Archive: this plan

下一阶段设为真实 approval ledger 仍不可接入的安全审查，或重新评估无 prompt readiness 探针；真实派发继续 deferred。

### Task 6: 验证、提交与推送

1. 运行 Stage 81 专项和现有协作/Control Panel 回归。
2. 运行 full pytest、doctor、public scan、docs context、Markdown link audit、pre-commit、diff check。
3. 用 Edge 验证自包含 HTML 静态渲染。
4. 提交并推送当前 `main`；不读取或输出凭据。

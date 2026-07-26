# Stage 80 操作者操作资格与审批绑定 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Stage 79 协作运行事件流之上，生成 fixture-backed、确定性、只读的操作者操作资格、审批绑定和幂等命令候选，但不授予执行权。

**Architecture:** 新建独立 action-eligibility fixture/schema 和校验器。每个操作请求绑定一个 Stage 79 事件 checkpoint、目标实体、期望状态和审批证据；校验器复用已验证 run-state 投影，重放到 checkpoint，检查固定 action/state 矩阵、审批精确绑定和已记录幂等键，然后输出可审阅但不可执行的 command candidate。CLI、Control Panel 和 handoff 只消费安全投影，不接触 execution、dispatch authority、readiness、session、ledger 或 controlled-write 模块。

**Tech Stack:** Python 3.11、标准库、jsonschema、argparse、自包含 HTML、pytest。

---

## 设计选择

评估了三种方案：

1. **推荐：独立 action-eligibility fixture + 历史 checkpoint 投影。** 能复用 Stage 79 完整事件流，在同一 completed fixture 上展示五种操作的合法时点，同时不伪造当前可执行状态。
2. 将资格字段直接写入 run-state fixture。实现较少，但把策略、审批和运行事实耦合到同一 schema，后续演进和审计边界差。
3. 直接复用真实 approval ledger。更接近未来执行，但会把当前只读产品主线耦合到受控写入和执行审计，超出本阶段授权。

采用方案 1。fixture 审批只属于演示证据，不能解释为真实 ledger 授权。

## 冻结契约

固定五个 action/state 组合：

- `approve_start`：run 为 `awaiting_approval`；
- `cancel`：run 为 `ready`、`running` 或 `blocked`；
- `retry`：work item attempt 为 `changes_requested` 或 `failed`；
- `request_changes`：review 为 `in_review`；
- `approve_handoff`：handoff 为 `ready`。

所有操作都必须精确绑定：run id、run projection id、action、target type/id、as-of sequence、expected state 和 approval id。只有 fixture approval 状态为 `approved` 且未命中 recorded idempotency key 时，业务资格才为 true；即便为 true，仍固定 `execution_authorized=false`、`dispatch_eligible=false`、`execution=not_executed`，且不生成 argv/cwd/env。

### Task 1: 编写失败测试与 fixture 契约

**Files:**
- Create: `tests/test_orchestration_collaboration_action_eligibility.py`
- Create later: `adapters/collaboration-action-eligibility.schema.json`
- Create later: `adapters/collaboration-action-eligibility.example.json`

1. 测试五种 action 的 checkpoint 状态和稳定 command candidate。
2. 测试路径逃逸、schema 失败、run-state 来源失败和重复 ID。
3. 测试 checkpoint 越界、状态不匹配、审批未批准、审批绑定不一致和已记录幂等键。
4. 测试 CLI 确定性、稳定退出码和无执行字段。
5. 先运行并确认因模块/fixture 不存在而失败。

### Task 2: 实现 schema、fixture 与只读校验器

**Files:**
- Create: `adapters/collaboration-action-eligibility.schema.json`
- Create: `adapters/collaboration-action-eligibility.example.json`
- Create: `agent_runtime/orchestration_collaboration_action_eligibility.py`

1. 实现 128 KiB、project-contained JSON 读取和严格 schema。
2. 复用 `inspect_collaboration_run_state`，拒绝无效 run fixture。
3. 按 as-of sequence 从已验证事件流重建实体状态。
4. 校验 request/approval 唯一 ID 和精确绑定。
5. 生成稳定 blocked reason 或内容寻址的 command candidate/idempotency key。
6. 输出汇总与固定不可执行 guarantees。

### Task 3: 接入 collaboration CLI

**Files:**
- Modify: `agent_runtime/cli.py`
- Modify: `tests/test_orchestration_boundary_contract.py`

新增：

```text
orchestration collaboration action-eligibility inspect --file <json> --json
```

人类输出只显示 action、目标、checkpoint、资格和稳定阻止原因；不得输出凭据或执行参数。

### Task 4: 接入 Control Panel 与 handoff

**Files:**
- Modify: `agent_runtime/orchestration_control_panel.py`
- Modify: `agent_runtime/cli.py`
- Create: `tests/test_orchestration_control_panel_action_eligibility.py`

1. 为 snapshot/render/handoff 增加 `--collaboration-action-file`。
2. 增加中文“协作 / 操作资格”区段。
3. 展示 checkpoint、当前状态、审批状态、资格、阻止原因和幂等键。
4. 即使资格为 true，所有按钮仍 disabled，并标记“资格不等于执行授权”。
5. invalid fixture fail closed；省略参数保持旧 shape。

### Task 5: 更新文档并归档

**Files:**
- Create: `docs/128-stage80-operator-action-eligibility-and-approval-binding.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-26.md`
- Archive: `docs/127-stage79-collaboration-run-state-model.md`
- Archive: this plan

下一阶段设为操作资格的当前态/审批集合投影收口，或在契约确有需要时重新评估无 prompt readiness 探针；真实派发仍需独立授权。

### Task 6: 验证

1. 运行 action eligibility 和 Control Panel 专项 pytest。
2. 运行 full pytest。
3. 运行 doctor、public scan、docs context、Markdown link audit、活跃文档计数。
4. 两次运行 CLI 并比较确定性输出。
5. 用 Edge 检查自包含中文 HTML。
6. 运行 pre-commit 和 diff check。
7. 保持全部改动未提交，等待用户明确 commit 授权。

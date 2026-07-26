# Stage 79 协作运行状态模型 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现一个项目内、fixture-backed、事件驱动且完全只读的多 Agent 协作运行状态模型，展示 run、work-item attempt、review、handoff、artifact 和事件历史，但不调用 Agent 或授予执行权。

**Architecture:** 新建独立 `orchestration_collaboration_run_state.py`，读取严格 JSON schema 和 collaboration plan v1，校验实体引用、attempt/retry、事件转换链、terminal 不可变、review/handoff/artifact 约束，并生成内容寻址的安全投影。CLI 和 Control Panel 只消费该投影；不接触 execution、readiness、dispatch authority、ledger 或 controlled-write 模块。

**Tech Stack:** Python 3.11、标准库、jsonschema、argparse、静态 HTML、pytest。

---

## 冻结状态

- Run：`draft`、`awaiting_approval`、`ready`、`running`、`blocked`、`cancelling`、`cancelled`、`completed`、`failed`。
- Attempt：`planned`、`ready`、`running`、`blocked`、`review_pending`、`changes_requested`、`completed`、`failed`、`cancelled`。
- Review：`pending`、`in_review`、`approved`、`changes_requested`、`cancelled`。
- Handoff：`pending`、`ready`、`accepted`、`rejected`、`superseded`。
- Artifact：`expected`、`reported`、`validated`、`rejected`、`superseded`。

所有实体通过连续 sequence 的事件链投影；事件必须携带 `from_state`、`to_state`，且匹配固定转换表。terminal 状态之后不得继续转换。

### Task 1: 冻结 fixture 与失败合同

**Files:**
- Create: `adapters/collaboration-run-state.schema.json`
- Create: `adapters/collaboration-run-state.example.json`
- Create: `tests/test_orchestration_collaboration_run_state.py`

1. 编写有效 fixture 预期测试。
2. 编写路径逃逸、schema 错误和引用错误测试。
3. 编写 attempt 序号、retry、事件连续性、非法转换和 terminal 不可变测试。
4. 编写 review、handoff、artifact 与 collaboration plan 不一致测试。
5. 运行测试，确认因模块和 fixture 尚不存在而失败。

### Task 2: 实现只读校验器与投影

**Files:**
- Create: `agent_runtime/orchestration_collaboration_run_state.py`

1. 实现 128 KiB 项目内 JSON 安全读取。
2. 校验 JSON schema 和引用的 collaboration plan。
3. 校验唯一 ID、attempt 连续性、单活动 attempt 和 retry 前序关闭。
4. 校验 artifact 类型/hash/attempt 归属。
5. 校验 review gate、attempt、artifact 和最终决定。
6. 校验 handoff pair、attempt 与 artifact 合同。
7. 重放实体事件链并校验固定转换、事件类型、最终状态和 terminal 不可变。
8. 校验 `completed` run 的最新 attempts、reviews 和 handoffs 完整。
9. 生成确定性、内容寻址、安全、不可执行投影。
10. 运行专项测试确认通过。

### Task 3: 接入 CLI

**Files:**
- Modify: `agent_runtime/cli.py`
- Modify: `tests/test_orchestration_collaboration_run_state.py`

1. 新增 `orchestration collaboration run-state inspect --file <json> --json`。
2. JSON 输出保持确定性和稳定 exit code。
3. 人类输出只显示安全摘要，不显示 artifact 正文。
4. 测试两次输出一致且不写文件。

### Task 4: 接入 Control Panel

**Files:**
- Modify: `agent_runtime/orchestration_control_panel.py`
- Modify: `agent_runtime/cli.py`
- Create: `tests/test_orchestration_control_panel_run_state.py`

1. 为 snapshot/render/handoff 增加可选 `--collaboration-run-file`。
2. 增加中文“协作 / 运行状态”区段。
3. 展示 run 摘要、attempt 历史、reviews、handoffs、artifacts 和事件时间线。
4. 操作者动作全部 disabled，标记“仅模拟、无执行权限”。
5. invalid fixture fail closed；省略参数保持旧 shape。
6. 测试 HTML escaping、handoff argv 和确定性。

### Task 5: 更新文档并归档

**Files:**
- Create: `docs/127-stage79-collaboration-run-state-model.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Modify: `tasks/handoff-2026-07-26.md`
- Archive: `docs/126-stage78-manual-confirmation-and-controlled-export.md`
- Archive: this plan

下一里程碑设为只读 operator action eligibility / run projection refinement；ACP probe 和真实派发继续 deferred。

### Task 6: 验证

1. 运行 run-state 和 Control Panel 专项 pytest。
2. 运行 full pytest。
3. 运行 doctor、public scan、docs context、活跃 Markdown link audit、文档计数。
4. 运行 CLI fixture inspect 两次并比较输出。
5. 用本机 Edge 验证静态 Control Panel 新区段。
6. 运行 pre-commit 和 diff check。
7. 检查没有 `.runtime`、凭据或执行权限变更进入 diff。
8. 本轮不提交，等待用户另行授权。

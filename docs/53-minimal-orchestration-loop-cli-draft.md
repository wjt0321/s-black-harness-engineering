# 53 — 中枢台最小编排闭环 CLI / 脚本命令草案参考

## 阶段定位

本文是 `docs/52-minimal-orchestration-loop.md` 的配套过渡材料，目标是在不正式展开 `51 — Backend-first API Boundary` 的前提下，为 52 定义的七步闭环提供一份**命令面草案参考**。

它既不是正式接口承诺，也不是 HTTP / RPC / service 设计。它的作用是：

- 让后续实现者看到“如果要给 52 的闭环配一组 CLI / 脚本命令，大概会长什么样”。
- 明确哪些命令已经存在、哪些只是候选草案、哪些仍然故意不做。
- 为 51 真正设计 API 边界之前保留一个可讨论、可修改的命令面草稿。

## 这份文档不是什么

- **不是 API 边界设计**：不定义资源模型、URI、方法、状态码、序列化格式。
- **不是 HTTP / RPC / service 接口**：不选协议、不定义 endpoint、不设计鉴权。
- **不是 UI 设计**：不涉及页面、看板、交互流程。
- **不是正式接口承诺**：文中所有 `orchestration *` 子命令都是候选草案，后续可能改名、合并、拆分或取消。
- **不是实现文档**：不讨论模块划分、数据结构、测试策略。

## 图例

文中命令前缀约定：

| 前缀 | 含义 | 示例 |
|:---|:---|:---|
| `python -m agent_runtime.cli <existing>` | 仓库中已经存在的 CLI 命令，可直接运行（部分可能仍在 POC 阶段）。 | `runtime plan`、`runtime gate check` |
| `python -m agent_runtime.cli orchestration overview` | 已存在：只读总览聚合。 | `orchestration overview --json` |
| `python -m agent_runtime.cli orchestration task list` | 已存在：只读任务列表，支持 `--status` 过滤。 | `orchestration task list --json` |
| `python -m agent_runtime.cli orchestration task get` | 已存在：只读任务详情 + 事件时间线。 | `orchestration task get --task-id ... --json` |
| `python -m agent_runtime.cli orchestration run inspect` | 已存在：只读 run 检查（当前为 `runtime report` 的薄包装）。 | `orchestration run inspect --task-id ... --request-id ... --envelope ...` |
| `python -m agent_runtime.cli orchestration <draft> ...` | 为 52 闭环设计的其他候选子命令，**当前尚未实现**，仅作草案参考。 | `orchestration route preview` |
| `orchestrator.sh` / `loop.sh` | 示意性脚本名，表示未来可能由脚本/自动化工作流编排的调用序列。 | — |

## 命令总览：按 52 七步闭环组织

### 1. Submit Task（提交任务意图）

已存在：

```bash
python -m agent_runtime.cli runtime task create \
  --file tasks/candidate-task.json \
  --dry-run

python -m agent_runtime.cli runtime task create \
  --file tasks/candidate-task.json \
  --commit
```

候选草案：

```bash
python -m agent_runtime.cli orchestration task submit \
  --capability dispatch.agent.coding \
  --title "补全路径归一化函数" \
  --workspace project-root \
  --mode dry-run
```

边界：

- `--dry-run` 只读模拟，不落盘。
- `--commit` 受控写入，仅追加 task ledger 单行，写后校验、失败回滚。
- 不自动创建 event ledger 条目。

### 2. Preview Routing（预览能力路由）

已存在（只读列表查询，可间接辅助路由判断）：

```bash
python -m agent_runtime.cli adapters list --capability dispatch.agent.coding
python -m agent_runtime.cli agents list --capability dispatch.agent.coding
```

候选草案：

```bash
python -m agent_runtime.cli orchestration route preview \
  --task-id task-20260709-001 \
  --capability dispatch.agent.coding \
  --mode dry-run
```

期望输出摘要：

```text
selected_adapter: adapter-A
capability: dispatch.agent.coding
operation: edit_file
requires_approval: false
requires_dry_run: true
fallback_chain: [adapter-B, adapter-C]
routing_reason: 默认匹配 coding capability，工作区内低风险
```

边界：

- 只读，不写任何 ledger 或 envelope。
- 输出脱敏，不打印完整 adapter metadata 或 input payload。

### 3. Run Preflight（执行门禁预检）

已存在：

```bash
python -m agent_runtime.cli check action \
  --adapter adapter-A \
  --operation edit_file \
  --target agent-runtime/loader.py

python -m agent_runtime.cli runtime plan \
  --task-id task-20260709-001 \
  --adapter adapter-A \
  --operation edit_file \
  --target agent-runtime/loader.py \
  --draft-json
```

候选草案（面向 52 闭环的聚合 preflight）：

```bash
python -m agent_runtime.cli orchestration preflight \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --envelope drafts/runtime/task-20260709-001/req-20260709-001.envelope.json
```

期望输出摘要：

```text
preflight: ALLOWED_WITH_CONSTRAINTS
constraints:
  - mode forced to dry-run
  - requires_review: true
next: proceed with dry-run
```

边界：

- 只读，不执行 adapter、不写 ledger。
- 结果决定闭环执行模式，但不阻塞闭环设计本身。

### 4. Run Dry-run / Commit（执行受控运行）

已存在（受控写入基础）：

```bash
python -m agent_runtime.cli runtime draft export \
  --stdin \
  --output drafts/runtime/task-20260709-001/req-20260709-001.envelope.json \
  --dry-run

python -m agent_runtime.cli runtime draft export \
  --stdin \
  --output drafts/runtime/task-20260709-001/req-20260709-001.envelope.json \
  --commit
```

候选草案（面向 52 闭环的 run 命令）：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --mode dry-run

python -m agent_runtime.cli orchestration run \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --mode commit
```

边界：

- `--dry-run`：生成 envelope draft、artifact 引用、验证结果，不触发真实外部执行。
- `--commit`：在受控写入边界内执行，例如写入项目内 draft、追加 event ledger、导出 report。
- 两者都不访问外部系统、不发送消息、不删除文件。

### 5. Inspect Run / Report（查看运行与报告）

已存在：

```bash
python -m agent_runtime.cli orchestration overview
python -m agent_runtime.cli orchestration overview --json

python -m agent_runtime.cli orchestration task list
python -m agent_runtime.cli orchestration task list --status running --json

python -m agent_runtime.cli orchestration task get \
  --task-id task-20260709-001 \
  --json

python -m agent_runtime.cli orchestration run inspect \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --envelope drafts/runtime/task-20260709-001/req-20260709-001.envelope.json

python -m agent_runtime.cli task status task-20260709-001
python -m agent_runtime.cli task events task-20260709-001

python -m agent_runtime.cli runtime report \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --envelope drafts/runtime/task-20260709-001/req-20260709-001.envelope.json

python -m agent_runtime.cli runtime draft inspect \
  --file drafts/runtime/task-20260709-001/req-20260709-001.envelope.json
```

候选草案：

```bash
python -m agent_runtime.cli orchestration inspect \
  --task-id task-20260709-001 \
  --run-id run-20260709-001

python -m agent_runtime.cli orchestration report \
  --task-id task-20260709-001 \
  --run-id run-20260709-001
```

边界：

- 只读，不写 ledger 或 envelope。
- 输出脱敏，不打印完整 input / evidence / raw_ref / decision_ref。

### 6. Approval Resolve（审批决议）

已存在：

```bash
python -m agent_runtime.cli adapter approval check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260709-001
```

候选草案：

```bash
python -m agent_runtime.cli orchestration approval resolve \
  --approval-id appr-20260709-001 \
  --decision granted \
  --reason " reviewed, safe to proceed"

python -m agent_runtime.cli orchestration approval resolve \
  --approval-id appr-20260709-001 \
  --decision rejected \
  --reason "target not confirmed"
```

边界：

- 受控写入：审批决议会追加到 event ledger 或更新 envelope 中的 approval_record。
- 需要显式 `--decision` 和 `--reason`。
- 决议只作用于本次 `this command + this approval_id + this task_id + this request_id`。

### 7. Fallback / Retry（回退与重试）

候选草案：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260709-001 \
  --run-id run-20260709-001 \
  --retry

python -m agent_runtime.cli orchestration run \
  --task-id task-20260709-001 \
  --fallback-to adapter-B \
  --mode dry-run
```

边界：

- `--retry`：基于同一 capability 和 input，对同一 adapter 再次尝试，生成新的 `Run` 并标记 `retry_of`。
- `--fallback-to`：显式指定 fallback adapter，生成新的 `Run` 并标记 `fallback_from`。
- 两者都受 guardrail preflight 约束，不绕过审批。
- 仍然只执行 dry-run / 受控 commit，不触发真实外部系统。

## 命令边界说明

### 只读命令

| 命令 | 作用 |
|:---|:---|
| `adapters list --capability ...` | 查看候选 adapter |
| `agents list --capability ...` | 查看候选 agent |
| `check action ...` | 单次动作 preflight |
| `runtime plan ...` | 生成 task 级 action draft |
| `runtime gate check ...` | 判断 task + request 能否继续 |
| `runtime report ...` | 聚合报告 |
| `task status / task events ...` | 查询 task 状态与事件流 |
| `orchestration overview` | 总览聚合（已存在） |
| `orchestration task list` | 任务列表（已存在） |
| `orchestration task get` | 任务详情 + 事件时间线（已存在） |
| `orchestration run inspect` | run 检查（已存在，`runtime report` 薄包装） |
| `orchestration route preview`（草案） | 预览 routing 结果 |
| `orchestration preflight`（草案） | 聚合 preflight |
| `orchestration inspect / report`（草案） | 查看 run / report |

### 受控写入命令

| 命令 | 作用 |
|:---|:---|
| `runtime task create --commit` | 追加 task ledger 单行 |
| `runtime draft export --commit` | 写入 envelope draft 文件 |
| `runtime event append --commit` | 追加 event ledger 单行 |
| `runtime event import --commit` | 批量追加 event ledger |
| `orchestration run --commit`（草案） | 执行一次受控 run，沉淀 run / event / artifact / evidence |
| `orchestration approval resolve`（草案） | 写入审批决议 |

### 仍然故意不做

| 不做的事 | 原因 |
|:---|:---|
| 真实 adapter execution | 仍在受控写入 / dry-run 阶段 |
| 网络访问 / 消息发送 | 安全边界 |
| 长期后台调度 / 并发 worker | 不在最小闭环范围内 |
| 自动重试策略 | 需要更多运行时数据后再设计 |
| 审批消息通知 UI | 属于 51 / UI 阶段 |
| 数据库持久化选型 | 属于后续实现阶段 |

## 一个脚本化闭环示例

以下脚本示意如何用现有命令 + 候选草案命令串起一个最小闭环。它**不是可执行脚本**，只是命令面参考。

```bash
#!/usr/bin/env bash
# orchestrator-loop.sh — 最小闭环命令面示意（草案）

TASK_ID="task-20260709-001"
CAPABILITY="dispatch.agent.coding"

# 1. submit task
python -m agent_runtime.cli orchestration task submit \
  --capability "$CAPABILITY" \
  --title "示例编码任务" \
  --workspace project-root \
  --mode dry-run \
  --commit

# 2. preview routing
python -m agent_runtime.cli orchestration route preview \
  --task-id "$TASK_ID" \
  --capability "$CAPABILITY" \
  --mode dry-run

# 3. preflight
python -m agent_runtime.cli orchestration preflight \
  --task-id "$TASK_ID" \
  --request-id req-20260709-001

# 4. dry-run
python -m agent_runtime.cli orchestration run \
  --task-id "$TASK_ID" \
  --request-id req-20260709-001 \
  --mode dry-run

# 4.5. overview (already exists)
python -m agent_runtime.cli orchestration overview

# 5. inspect
python -m agent_runtime.cli orchestration inspect \
  --task-id "$TASK_ID" \
  --run-id run-20260709-001

# 6. if approval needed, resolve (otherwise skip)
# python -m agent_runtime.cli orchestration approval resolve \
#   --approval-id appr-20260709-001 \
#   --decision granted

# 7. report
python -m agent_runtime.cli orchestration report \
  --task-id "$TASK_ID" \
  --run-id run-20260709-001
```

说明：

- 真实环境中，`orchestration *` 命令可能合并到 `runtime *` 命名空间，也可能保持独立。
- `--commit` 语义与现有受控写入命令一致：显式、校验、回滚。
- 第 6 步是否执行取决于 preflight 是否触发 `NEEDS_APPROVAL`。

## 与 51/52 的关系

```text
52 (Minimal Orchestration Loop)
  -> 53 (CLI / Script Command Draft)  <- 本文：把 52 的七步闭环翻译成命令面草案
  -> 51 (Backend-first API Boundary)  <- 未来：把这些命令背后的资源与操作抽象成稳定后端接口
```

- 52 回答“闭环里有什么”。
- 53 回答“如果要从命令行/脚本驱动这个闭环，命令可能长什么样”。
- 51 才回答“这些命令背后依赖哪些资源模型、操作边界和调用约定”。

## 当前阶段不做什么

本文不实现：

- 除 `orchestration overview`、`orchestration task list`、`orchestration task get`、`orchestration run inspect` 之外的任何新的 CLI 子命令。
- HTTP / RPC / service 接口。
- 前端或看板。
- 数据库选型。
- 真实 adapter execution。
- 自动化调度引擎。

本文只提供一份可修改的命令面草案，供后续进入 51 或实现 Stage 14 时参考。

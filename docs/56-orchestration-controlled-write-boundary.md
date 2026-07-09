# 56 — Orchestration 受控写入命令边界

## 阶段定位

Stage 15 的 read-model CLI 已经封版：六类页面视角（overview / task / run / approval / artifact / report）都有了最小只读命令，且不写 ledger、不执行 adapter、不访问网络。

本文档是进入**第一批 orchestration 受控写入命令**前的 safety / design gate。目标不是立刻打开真实 adapter execution，而是在写任何新代码之前，先把下面几件事固定下来：

1. 哪些写入命令先进入实现，哪些继续留在草案。
2. `dry-run` / `commit` 的统一语义。
3. capability routing 的结果如何安全地 handoff 给 runtime plan / adapter request / guardrail preflight。
4. `approval resolve` 这类写入命令的最小安全语义。
5. 产物、状态、回滚、验收的边界。

遵循的原则仍然是：

- guardrail 是长期内核，但不阻塞主线。
- 积木式可插拔：每个新命令只负责一个清晰的 orchestration 切面。
- 不引入 DB / service / UI；写入仍然受控、显式、可审计、可回滚。

## 候选第一批写入命令建议优先级

### 第一梯队：先补只读 handoff 命令

在真正写入任何东西之前，建议先实现两个只读命令，把 capability routing 到 guardrail preflight 的 handoff 路径跑通：

1. `orchestration route preview`（**已落地**）
   - 输入：task intent（`requested_capability` + 可选 `--task-id` / `--adapter` / `--mode` 约束）。
   - 输出：routing decision（`selected_adapter_id`、`capability`、`operation`、`requested_mode`、`selected_mode`、`risk_level`、`requires_approval`、`requires_dry_run`、`fallback_candidates`、`routing_reason`、`constraints`、`next_action`）。
   - 只读，不写 ledger / envelope / 不执行 adapter / 不访问网络。
   - `--adapter` 显式指定时校验支持性，不支持则返回 `blocked` 并给出 fallback candidates。
   - 请求 `--mode commit` 时，若 adapter 为 external / destructive / privileged 或 `requires_approval`，`selected_mode` 会被强制降级为 `dry-run`；route preview 本身仍只读。
   - `operation` 仅在 adapter 的 `input_schema` 要求 `operation` 字段时才用 capability 推导，否则为 `null`，避免猜测。
   - 为 `orchestration preflight` 和 `runtime plan` 提供输入。

2. `orchestration preflight`（**已落地**）
   - 输入：`requested_capability` + 可选 `--task-id` / `--adapter` / `--operation` / `--target` / `--mode`。
   - 处理：先调用 `orchestration route preview` 得到 routing decision；若 routing 不通过，直接返回其状态并不继续 guardrail；否则用 `policy.check_action` 做 guardrail preflight。
   - 输出：聚合 preflight 结果，包括 `route` 安全摘要、`guardrail` 安全摘要、`requested_mode` / `selected_mode` / `effective_mode`、`requires_approval`、`requires_dry_run`、`constraints`、`findings`、`next_action`。
   - 只读，不写 ledger / envelope / 不执行 adapter / 不访问网络。
   - `--operation` / `--target` 缺失时，若 adapter `input_schema` 要求则返回 `needs_input`；不猜测 operation 或 target。
   - `--mode commit` 时，若 routing 或 guardrail 任一要求 dry-run / approval，则 `effective_mode` 强制为 `dry-run`；preflight 本身仍只读。
   - 明确 run 的 `mode`（dry-run / commit）、`requires_approval`、`requires_dry_run`。

### 第二梯队：第一个真正受控写入命令（已落地）

3. `orchestration approval resolve`
   - 当前最有价值的写入候选：它只记录审批决议，不直接触发外部执行。
   - 第一版采用 **event-ledger append** 方案：
     - `--dry-run` 只生成 `approval_resolved` event preview，不写 ledger。
     - `--commit` 通过 `runtime event append --commit` 的受控写入机制，向 event ledger 追加一条 `approval_resolved` event；失败按 byte size 回滚。
     - 不原地修改输入 envelope，不生成独立 Approval 存储。
   - `--decision` 限定为 `granted` / `denied` / `expired`；`--reason` 必填且长度受限，输出和 event metadata 中不回显完整 reason（使用 reason hash / length）。
   - 不直接解锁原请求继续执行；granted 后仍需重新发起 run / preflight。

### 暂缓的写入命令

以下命令仍留在 53 的命令草案中，等第一批 handoff + approval resolve 稳定后再进入实现：

- `orchestration run --commit`
- `orchestration task submit --commit`
- `orchestration run --retry`
- `orchestration run --fallback-to`

原因是：这些命令会真正改变 task / run / artifact / evidence 状态，必须先确认 routing handoff 和 approval resolve 的语义不会把错误决策固化进 ledger。

## dry-run / commit 统一语义

所有 write-like orchestration 命令必须同时满足以下约定：

### 1. 每个命令必须声明自己的模式

- 要么同时支持 `--dry-run` 和 `--commit`。
- 要么明确拒绝 commit（例如某些只读 handoff 命令可以只支持 dry-run，或者默认只读）。
- 不允许“静默 commit”：没有 `--commit` 时默认必须是 dry-run 或只读。

### 2. dry-run 语义

- 只产出 plan / preview / candidate，不写任何 ledger / draft / envelope。
- 可以读取现有 ledger / envelope 做预检。
- 输出必须包含稳定标识（如 `plan_hash`），供后续 commit 做 freeze guard。
- dry-run 结果可以展示安全摘要，但不能包含完整 input payload / secret / raw_ref。

### 3. commit 语义

- commit 只能在现有 controlled-write 机制内进行：
  - 向 event ledger 追加一行（`runtime event append --commit` 模式）。
  - 或生成新的 envelope draft（`runtime draft export --commit` 模式）。
  - 不原地修改输入 envelope，不删除已有文件。
- commit 前必须重新 load 相关 ledger / envelope 做 preflight 校验。
- commit 后必须做 post-check（schema / ledger consistency / runtime audit）。
- 失败时必须按原始 byte size 回滚，或删除刚刚生成的新文件。
- commit 成功后返回稳定的写入证据（event_id / output path / hash / appended bytes）。

### 4. commit 仍不等于真实外部执行

- 当前阶段，`--commit` 只表示“把决策/事件/draft 沉淀到项目内受控存储”。
- 不表示“现在执行 adapter”。
- 仍然禁止：网络访问、消息发送、真实外部系统调用、文件系统写删（受控写入路径除外）。

### 5. freeze guard

如果命令支持基于之前 dry-run 审阅结果做 commit，应支持类似机制：

- `--expected-plan-hash <hash>`：commit 前校验当前计划是否与审阅时一致。
- `--require-dry-run`：commit 必须绑定一次之前的 dry-run（可要求同时提供 expected hash）。
- hash mismatch 属于 blocked，不是 error；应返回非零退出码并说明原因，但不写 ledger。

## Capability routing handoff

### routing 输出模型

`orchestration route preview` 的输出应包含以下安全字段：

| 字段 | 说明 |
|:---|:---|
| `selected_adapter_id` | 选中的 adapter id |
| `capability` | 匹配到的 capability 名称 |
| `operation` | 对应的 operation |
| `mode` | 建议模式：`dry-run` / `commit`（由 risk_level 与 policy 共同决定） |
| `risk_level` | `local` / `external` / `destructive` / `privileged` |
| `requires_approval` | 是否需要用户授权 |
| `requires_dry_run` | 是否强制 dry-run（例如高风险但可预览动作） |
| `fallback_candidates` | 次选 adapter / capability 列表，不含完整 metadata |
| `routing_reason` | 选择理由摘要 |
| `constraints` | 应用的 policy / workspace / capability 约束安全摘要 |

### routing 输出禁止包含

- 完整 input payload。
- secret / token / credential。
- raw adapter metadata（如内部 endpoint、私有配置）。
- 用户提供的原始 target 完整值（可保留类型或脱敏摘要）。

### handoff 到 runtime plan / adapter request

routing decision 的下游消费路径：

1. `orchestration route preview` -> `orchestration preflight`
2. `orchestration preflight` -> `runtime plan --adapter <selected_adapter_id> --operation <operation> --target <safe_target>`
3. `runtime plan` 生成 envelope draft（`--draft-json`）。
4. 该 envelope 进入现有的 `runtime draft export --commit` / `runtime event append --commit` / `runtime gate check` / `runtime report` 链路。

关键点：

- routing 只做“选择”和“约束”，不绕过 guardrail。
- `runtime plan` / `adapter plan` 会重新执行 policy preflight，routing decision 中的 `requires_approval` / `requires_dry_run` 只是建议，最终由 guardrail 决定。
- 如果 routing 建议 dry-run 但 guardrail 允许 commit，应以更保守的 mode 为准（即 dry-run）。
- 如果 routing 建议 commit 但 guardrail 要求 approval，应进入 approval 流程。

## Approval resolve 安全语义

`orchestration approval resolve` 是第一批写入命令中最需要谨慎设计的一个。

### 基本原则

- 只记录 decision，不直接执行原请求。
- 不删除、不修改原 `approval_record`。
- decision 必须绑定到具体的 `(approval_id, task_id, request_id, envelope_context)`。

### granted 语义

- 记录 `granted` decision。
- 生成新的 event 或新的 envelope draft。
- **不能**直接复用旧的 preflight 结果去 commit 原请求。
- 下一步必须由用户/自动化显式发起新的 `orchestration run` / `runtime plan` / `adapter plan`，并在新的 preflight 中确认 approval 已 granted。

### rejected 语义

- 记录 `rejected` / `denied` decision。
- 生成拒绝 event 或报告摘要。
- 原 `approval_record` 保持 pending（历史保留），decision 作为新记录追加。

### decision 字段

| 字段 | 要求 |
|:---|:---|
| `approval_id` | 必须对应已有 approval_record |
| `task_id` | 必须与 approval.scope.task_id 一致 |
| `request_id` | 必须与 approval.request_id 一致 |
| `decision` | `granted` / `denied` / `expired` |
| `reason` | 长度限制、内容白名单，避免泄露敏感上下文 |
| `decided_by` | 决策人标识，可为空但不允许内部系统名 |
| `decision_ref` | 可选外部引用，输出时不回显完整值 |
| `envelope_path` / `ledger_context` | 仅保存相对路径或安全摘要 |

### 输出产物选项

第一版已选定 **event ledger append** 方案：

- 追加一条 `approval_resolved` event。
- 使用 `runtime event append --commit` 的受控写入机制。
- 失败按 byte size 回滚。
- event metadata 只保留 `approval_id`、`request_id`、`decision`、`reason_hash`、`reason_length`、`envelope_path` 等安全字段，不保留完整 reason、不保留 `decision_ref`。

envelope draft export 方案仍可作为未来候选，但不在第一版实现。

两种选项都必须在 post-check 中验证：

- event / draft schema 合法。
- approval_id 存在且 scope 未被篡改。
- 不引入新的 secret / 敏感路径。

## 状态与产物边界

### 第一版继续不引入

- 不引入数据库。
- 不引入后台服务或 API server。
- 不引入 UI / 前端。
- 不引入独立的 Run / Approval / Artifact / Report 存储。

### 写入原则

- 若写 ledger，优先 append-only event。
- 若改 envelope，优先生成新的 draft / export 文件，不原地修改输入 envelope。
- 所有写入走现有 controlled-write 路径（`runtime event append`、`runtime draft export`）。
- 写入产物必须可通过现有 read-model CLI（`task events`、`artifact list`、`report generate`）观察到。

## 验收标准

每个新增受控写入命令在实现前必须明确：

1. JSON 输出结构（含 `status`、稳定标识、写入证据、next_action）。
2. 人类可读输出结构（紧凑、脱敏）。
3. 测试覆盖：
   - dry-run 不写文件 / ledger。
   - commit 成功并产生可追溯产物。
   - commit 失败回滚（按 byte size truncate 或删除新生成文件）。
   - 非法输入 / missing approval / hash mismatch 的稳定错误行为。
   - 输出中不出现完整 input / secret / raw_ref / decision_ref / payload_refs。
4. 通过 `python -m pytest tests -q`。
5. 通过 `python -m agent_runtime.cli doctor`。
6. 通过 `python tools/public_scan.py`。
7. 通过 `git diff --check`。

## 与 51 / 52 / 53 / 54 的关系

- `docs/51-backend-first-api-boundary.md` 定义了资源与操作边界；本文档把其中 write-like 操作的 dry-run/commit 语义细化到可执行层面。
- `docs/52-minimal-orchestration-loop.md` 描述了七步闭环；本文档规定其中 `route preview` / `preflight` / `approval resolve` 三步的最小实现边界。
- `docs/53-minimal-orchestration-loop-cli-draft.md` 提供了命令草案；本文档筛选出第一批可进入实现的命令，并明确其余仍留在草案。
- `docs/54-backend-preparation-before-ui.md` 定义了页面 read model；本文档说明页面操作入口（如审批页的 resolve）在写入侧应如何安全落地。

## 下一步建议

1. ~~先实现 `orchestration route preview`（只读）~~ 已落地。
2. ~~再实现 `orchestration preflight`（只读）~~ 已落地。
3. ~~实现 `orchestration approval resolve`（受控写入，event-ledger append 方案）~~ 已落地。
4. 更新 53 / 10 / release notes，把 `orchestration approval resolve` 从草案标记为已存在。
5. 在 `route preview` / `preflight` / `approval resolve` 稳定前，不实现 `orchestration run --commit`、`orchestration task submit --commit`、retry / fallback 自动化。

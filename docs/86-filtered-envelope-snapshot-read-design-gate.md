<!-- parents: 85-envelope-scoped-consumer-filter-design-gate.md, 84-envelope-scoped-snapshot-read-design-gate.md -->
<!-- relates: 83-codex-desktop-snapshot-json-reader-implementation.md, 73-recovery-lineage-aggregation-read-model.md -->

# 86 — Filtered Envelope Snapshot Read Design Gate

> Stage 26 设计门事实源。用户已明确要求直接进入下一阶段；本设计门冻结结构化 task/request filter、关系闭包、版本化 filtered view identity 与 no-query/no-persistence 边界，但不在本阶段修改生产 reader。

## 1. 启动判定

Stage 25 因缺少具体消费者而冻结无 filter v2。用户随后明确要求直接进入下一阶段，因此 Stage 26 获得设计审计授权。该授权只覆盖**设计结构化 task/request filter**，不等同于授权通用 query、任意字段表达式、持久化、export 或真实 adapter execution。

现有 envelope-scoped snapshot 已提供可复用的安全摘要字段：

- runs：`task_id`、`request_id`；
- approvals：`task_id`、`request_id`；
- artifacts：`task_id`、`request_id`，其中 response 类摘要可能只有 `request_id`；
- reports：继续 request-scoped unavailable。

Stage 26 只基于 Stage 24 已验证 snapshot 的这些安全摘要设计过滤，不读取 raw envelope 的 `input`、payload refs、raw refs 或 evidence description。

## 2. 目标与非目标

### 目标

1. 冻结显式 `--task-id` / `--request-id` 输入契约；
2. 冻结单参数与双参数组合语义；
3. 处理 artifact 缺少直接 `task_id` 时的 request→task 关系闭包；
4. 定义 filter identity、base snapshot identity 与 filtered view identity；
5. 保持 v1/v2 兼容，并为未来 Stage 27 v3 实现给出完整验收矩阵。

### 非目标

- 本阶段不修改 `tools/codex_desktop_snapshot_json_reader.py` 的生产行为；
- 不增加通用 `--filter`、`--query`、JSONPath、正则、通配符或列表表达式；
- 不过滤 project-scoped tasks/overview 或 registry/automation sections；
- 不生成 report collection；
- 不保存、cache、export、上传或发送 filtered result；
- 不打开 HTML/browser，不启动 service，不访问网络，不执行 descriptor argv 或真实 adapter。

## 3. 输入契约

未来 Stage 27 实现仅允许：

```text
--representation snapshot-json
--envelope <validated-project-relative-path>
[--task-id <task-id>] [--request-id <request-id>]
```

规则：

1. `--task-id` 与 `--request-id` 至少提供一个才进入 filtered v3；
2. filter 必须与显式 `--envelope` 同时出现；无 envelope 时 filter 为 `validation_failed`；
3. 只有 envelope、无 filter 时继续返回 Stage 24 v2；
4. 无 envelope、无 filter 时继续返回 Stage 22 v1；
5. 两个 filter 可同时出现，语义为 AND；
6. 每个 flag 最多出现一次；重复 flag 拒绝，不采用 argparse 的 last-value-wins；
7. 不 trim、不大小写折叠、不 Unicode normalization；输入必须已经是 canonical ASCII；
8. 不接受逗号列表、空字符串、空白、通配符、正则或前后缀匹配。

### 3.1 ID 形状

- task：`^task-[0-9]{8}-[0-9]{3,}$`；
- request：`^req-[0-9]{8}-[0-9]{3,}$`；
- 每个值最大 128 ASCII bytes。

格式错误必须在启动任何 child process 前返回 `validation_failed`，finding 只包含 rule id、参数名和安全提示。

## 4. Filter 作用域

filter 只作用于已完整验证的 scoped snapshot 安全摘要：

- `sections.runs.runs`；
- `sections.approvals.approvals`；
- `sections.artifacts.artifacts`。

以下内容不进入 filtered view：

- project-scoped `overview` / `tasks`；
- registry-scoped `adapters`；
- project-scoped `automation`；
- raw envelope、descriptor、argv、stderr；
- report collection。

`reports` 在 filtered view 中继续明确返回 `unavailable/request_context_required`，不能因为提供 request filter 就调用 `report generate` 或伪造 report。

## 5. 匹配与关系闭包

先从已验证 runs summaries 构造确定性映射：

```text
request_task[request_id] = task_id
```

envelope validation 已拒绝冲突 request identity；filtered reader 不重新解释 raw artifacts。

### 5.1 仅 task filter

1. 选择 `run.task_id == task_id` 的 runs；
2. 得到这些 runs 的 selected request ids；
3. approvals：`approval.task_id == task_id` 或 `approval.request_id` 在 selected request ids；
4. artifacts：`artifact.task_id == task_id` 或 `artifact.request_id` 在 selected request ids。

关系闭包保证只有 `request_id`、没有直接 `task_id` 的 adapter response 不会从 task view 中丢失。

### 5.2 仅 request filter

runs、approvals、artifacts 均按 `request_id` exact match。不会自动扩展到 parent/retry/fallback lineage；lineage filter 必须另开设计门。

### 5.3 task + request

先确认 request 对应 run 同时满足两个 exact match，再以该单一 selected request set 过滤 approvals/artifacts。二者不一致时返回合法空视图，不猜测、不降级为单参数。

### 5.4 无匹配

格式合法但无匹配时：

- reader 状态仍为 `ready`；
- scoped section 状态为 `pass`，列表为空；
- summary counts 为 0；
- `matched=false`；
- 不返回 `needs_input`，不自动选择最近 request/task。

## 6. 顺序、上限与确定性

- 保持 base snapshot 中各 section 的原始确定性顺序；
- 不新增 sort 参数；
- 每个 section 的结果数量不会超过 base snapshot；
- v3 wrapper 与 payload 仍受 1 MiB 最终输出上限；
- 不分页，不生成 continuation token；
- 相同 root、envelope bytes、base snapshot 与 canonical filter 必须产生相同 filter/view identity 和输出 bytes。

## 7. 版本化输出

未来 filtered mode 使用新版本，不静默改变 v2：

| 内容 | 版本 |
|:---|:---|
| reader result schema | `control-plane/codex-desktop-snapshot-read/v3` |
| reader id | `codex-desktop-filtered-envelope-snapshot-json-reader/v3` |
| filtered payload schema | `control-plane/filtered-envelope-snapshot/v1` |
| filter schema | `control-plane/envelope-snapshot-filter/v1` |

filtered payload 只包含：

```text
status
schema_version
source.base_snapshot_id
source.scope_id
source.filter_id
filter
summary
sections.runs
sections.approvals
sections.artifacts
sections.reports
```

不把过滤后的 payload 标记为原始 `control-panel-snapshot/v1`，也不复用 base `snapshot_id` 冒充 filtered payload 的 canonical hash。

## 8. Identity 契约

canonical filter object 固定为：

```json
{
  "request_id": "<string-or-null>",
  "schema_version": "control-plane/envelope-snapshot-filter/v1",
  "task_id": "<string-or-null>"
}
```

使用 UTF-8、sorted keys、无多余空白的 canonical JSON：

```text
filter_id = sha256(canonical(filter))
```

filtered payload 的 `source` 必须包含：

- Stage 24 `base_snapshot_id`；
- Stage 24 `scope_id`；
- `filter_id`。

`view_id` 为 filtered payload（不含 `view_id` 自身）的 canonical SHA-256：

```text
view_id = sha256(canonical(filtered_payload_without_view_id))
```

consumer 必须能独立重算 `filter_id` 与 `view_id`。base snapshot id 继续由 Stage 24 既有验证链校验，不能由 filtered reader 重新发明。

## 9. 生命周期与固定执行链

v3 生命周期冻结为：

```text
created → scoping → producing → validating → reading → filtering → ready → closed
```

固定 child argv 仍然只有：

```text
handoff --envelope <validated-path> --json
reference consumer(stdin=handoff bytes)
snapshot --envelope <validated-path> --json
```

filter 参数绝不传给 child process，也不写入 descriptor。过滤只在 snapshot schema/source/guarantees/id/hash 和 envelope content drift 全部通过后，对内存中的安全 summaries 执行。

## 10. Finding 与状态矩阵

| 条件 | 状态 | 启动 child |
|:---|:---|:---:|
| filter 无 envelope | `validation_failed` | 否 |
| filter 为空、非 canonical、超长或格式错误 | `validation_failed` | 否 |
| filter flag 重复 | `validation_failed` | 否 |
| envelope gate 失败 | 沿用 Stage 24 状态 | 否 |
| base handoff/snapshot validation 失败 | 沿用 Stage 24 状态 | 按既有阶段停止 |
| 合法 filter 无匹配 | `ready` / `matched=false` | 是 |
| 合法 filter 有匹配 | `ready` / `matched=true` | 是 |

新增 findings 只允许 value-free message；不得回显完整非法参数、raw envelope 或绝对路径。

## 11. Stage 27 实现进入条件

Stage 27 开始前必须按 TDD 覆盖：

1. v1/v2 byte/field compatibility；
2. task-only、request-only、task+request AND；
3. task relation closure 包含 response summary；
4. mismatch/zero-match ready empty view；
5. invalid/duplicate/no-envelope filters 在 spawn 前失败；
6. filter_id、view_id 重算与 tamper mismatch；
7. filtered payload 不包含 project/registry sections 或 raw values；
8. lifecycle 包含 filtering，child argv 不包含 filter；
9. deterministic order、1 MiB、no-write/no-network/no-service/no-HTML/no-execute；
10. full pytest、doctor、public scan、controlled-write regression 与 docs hook。

## 12. Design Gate 结论

**Stage 26 已通过并收口。**

已具备进入 Stage 27 的设计事实：

- 仅结构化 task/request exact filter；
- 双参数 AND 与合法空视图；
- request→task 关系闭包；
- v3/new payload schema，不修改 v2；
- filter/base snapshot/view 三层 identity；
- fixed child argv 与 post-validation in-memory filtering；
- no query、no lineage expansion、no persistence/export、no HTML/browser/network/write/execute。

下一阶段为 **Stage 27 — Filtered Envelope Snapshot JSON Reader Implementation（条件启动）**。

<!-- gate-status: passed -->
<!-- implementation-status: stage27-not-started -->

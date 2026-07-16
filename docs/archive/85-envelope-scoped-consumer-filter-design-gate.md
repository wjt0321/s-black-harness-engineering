<!-- parents: 84-envelope-scoped-snapshot-read-design-gate.md -->
<!-- relates: 83-codex-desktop-snapshot-json-reader-implementation.md, 79-read-only-host-consumer-validation-boundary.md -->

# 85 — Envelope-scoped Consumer Integration / Filter Design Gate

> Stage 25 设计门事实源。结论：保持 Stage 24 单 envelope、无 filter 的 v2 reader；冻结宿主只能一次性消费已验证 stdout JSON 的展示边界，不新增 task/request filter、通用 query、持久化或 export。

## 1. 启动与审计范围

用户明确要求继续推进并做到阶段性收口，因此 Stage 25 设计门启动。本阶段审计以下问题：

1. 当前是否已有明确的 task/request filter 消费者；
2. 是否需要在 reader 上新增筛选、排序、分页或 query 语法；
3. 宿主能否安全消费 Stage 24 scoped v2；
4. filter identity 是否已经具备可冻结的输入、规范化与 hash 契约；
5. 是否会扩大 arbitrary path、HTML/browser、write/network/service 权限。

审计对象仅限既有 `tools/codex_desktop_snapshot_json_reader.py`、Stage 17 handoff、Stage 18 validation 与 Stage 24 scoped v2。没有把未来 UI、外部 host 或未实现 service 当成现存消费者。

## 2. 消费者需求审计

当前仓库没有以下已冻结事实：

- 一个只需要某个 `task_id` 或 `request_id` 的具体宿主动作；
- filter 的组合语义、缺失值语义、结果为空语义或优先级；
- filter 与 snapshot canonical hash / scope id 的版本化绑定方式；
- 结果排序、分页、上限或多 envelope 聚合需求；
- 允许保存、导出或跨会话缓存 scoped result 的授权。

当前已经存在且足够安全的消费面是：用户显式选择 `snapshot-json` 与单个 allowlist envelope，reader 返回一个经过 schema/source/identity/hash/content-drift 校验的有界 v2 JSON 文档。

因此，“继续推进”不解释为自动发明 filter 语义或扩大宿主权限。

## 3. 方案评估

### 方案 A：自动增加 `--task-id` / `--request-id`

拒绝。原因：

- 没有具体消费者证明 filter 必要；
- task 与 request 的交集、父子 lineage、无匹配结果尚未冻结；
- 如果 filter 不参与内容寻址，可能出现相同 snapshot id 表示不同视图；
- 如果直接复用 section 内部字段过滤，容易绕过未来 read-model 兼容边界。

### 方案 B：增加通用 `--filter` / `--query`

拒绝。原因：

- 会引入未受控表达式、字段探测和复杂度/资源上限问题；
- 容易演变为 arbitrary query 或隐式数据发现；
- 当前没有 schema、语法版本、规范化或 deterministic identity 契约。

### 方案 C：保持无 filter 的单-envelope v2，并冻结 consumer 展示契约

采用。该方案复用已验证 representation，不改变 Stage 24 reader schema、reader id、snapshot id 或命令面，同时为未来宿主留下最小、可审计的消费边界。

## 4. 冻结决策

Stage 25 冻结以下事实：

1. `control-plane/codex-desktop-snapshot-read/v2` 继续表示**一个显式 envelope 的完整安全摘要视图**；
2. reader CLI 不新增 `--task-id`、`--request-id`、`--filter`、`--query`、`--sort`、`--page` 或 `--export`；
3. 不从 descriptor、snapshot payload、HTML、UI event、环境变量或最近文件推导 filter；
4. 不对 runs / approvals / artifacts 做 reader-local 二次筛选；
5. `reports` 继续保持 request-scoped unavailable，不伪造 collection；
6. `ready` 只表示 scoped representation 已通过验证，不表示 adapter 已执行、审批已解决或 artifact 已持久化；
7. Stage 24 v1/v2 schema、reader id、scope id 与 snapshot canonical hash 均保持兼容。

## 5. 宿主消费边界

未来宿主如果消费当前 v2，只允许：

```text
explicit user action
  -> spawn fixed snapshot JSON reader once
  -> read bounded stdout JSON once
  -> require status=ready and v2 schema/reader id
  -> render existing safe summaries in memory
  -> discard process-local result when the view closes
```

宿主不得：

- 执行 result、descriptor 或 snapshot 中的 argv；
- 保存、export、上传、发送或写回 JSON；
- 缓存为新的持久 Run/Event/Report/Artifact；
- 打开 HTML 或浏览器；
- 自动刷新、轮询、重试或启动长期后台进程；
- 访问网络、DB、auth/session 或真实 adapter；
- 对 payload 做未版本化的任意 query，并把结果冒充为 reader 输出。

宿主状态映射保持最小：

| reader status | 宿主含义 | 可展示 representation |
|:---|:---|:---:|
| `ready` | 已验证的一次性只读 representation | 是 |
| `blocked` | 前置 handoff 未满足 | 否 |
| `validation_failed` | 输入、identity 或协议不可信 | 否 |
| `error` | 本地一次性读取失败 | 否 |

## 6. Filter identity 的延期条件

未来如果出现具体 filter 消费者，必须新开版本化设计门，至少冻结：

1. 只允许结构化 `task_id` / `request_id`，还是允许二者组合；
2. filter 只作用于已验证 envelope 的安全 summaries，不能触碰 raw envelope；
3. filter 的 canonical form、空值、无匹配、重复参数与大小上限；
4. filter identity 如何绑定 `scope_id`、snapshot id 与新的 reader result id；
5. 是否需要新的 `v3` schema / reader id，禁止静默改变 v2；
6. 确定性排序、结果数量上限和跨 section 一致性；
7. no arbitrary query/path、no persistence/export、no HTML/browser/network/write/execute 回归证据。

在这些条件齐备前，filter 状态为 `unavailable`，不是“待 host 自行实现”。

## 7. 验收证据

新增契约测试冻结 reader 命令面不暴露：

- `--task-id`
- `--request-id`
- `--filter`
- `--query`
- `--sort`
- `--page`
- `--export`

Stage 24 既有测试继续覆盖 v1/v2、allowlist、secret scan、identity、content drift、fixed argv 与真实 stdio。Stage 25 不修改生产 reader，不改变任何已发布 schema。

## 8. Design Gate 结论

**Stage 25 已收口。**

收口结果不是“实现 filter”，而是：

- 明确当前没有足够需求证明 filter 必要；
- 把无 filter 的单-envelope v2 固定为当前唯一受支持 scoped consumer contract；
- 给宿主冻结一次性、内存态、只展示已验证 stdout JSON 的边界；
- 阻止 host-local query、持久化/export 或 schema v2 静默漂移。

下一阶段为 **Stage 26 — Filtered Envelope Snapshot Read Design Gate（条件启动）**。只有具体消费者给出 task/request filter 需求、identity 与结果边界后才启动；否则继续维持 Stage 25 冻结状态。

<!-- gate-status: passed -->
<!-- implementation-status: no-filter-contract-frozen -->

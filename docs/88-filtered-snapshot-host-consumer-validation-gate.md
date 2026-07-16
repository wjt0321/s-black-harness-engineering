<!-- parents: 87-filtered-envelope-snapshot-json-reader-implementation.md, 79-read-only-host-consumer-validation-boundary.md -->
<!-- relates: archive/81-codex-desktop-read-only-adapter-implementation.md, 86-filtered-envelope-snapshot-read-design-gate.md -->

# 88 — Filtered Snapshot Host Consumer Validation Gate

> Stage 28 设计门与验收事实源。用户已明确要求继续推进到下一阶段收口；本阶段选择 Codex Desktop 本地任务进程作为具体宿主边界，冻结 filtered v3 独立 consumer contract，但不实现 consumer、不读取文件、不执行 reader 或 descriptor argv。

## 1. 决策摘要

Stage 28 已满足条件启动：

- 具体宿主：Codex Desktop 的本地一次性任务进程；
- 具体输入：Stage 27 reader 输出的完整 `control-plane/codex-desktop-snapshot-read/v3` JSON result；
- 具体需求：宿主在展示 filtered safe summaries 前，不直接信任 reader stdout，而是用独立标准库 consumer 校验 wrapper、lifecycle、guarantees、scope/filter/view identity 与安全 section shape；
- 明确授权：用户于 2026-07-16 要求继续推进到下一阶段收口。

本阶段只冻结设计。未来候选实现：

```text
tools/codex_desktop_filtered_snapshot_consumer.py
```

它不得修改或复用 Stage 18 `tools/control_panel_handoff_consumer.py` 的生产入口。

## 2. 方案选择

### 方案 A — 扩展 Stage 18 handoff consumer

**拒绝。** Stage 18 consumer 的唯一输入是 `control-plane/control-panel-handoff/v1`，检查 handoff/render identity、representation argv 与 boundary。把 filtered v3 混入同一工具会形成多 schema 分支，降低独立性并改变已冻结的 Stage 18 contract。

### 方案 B — 新增专用标准库-only stdin consumer

**采用为 Stage 29 候选实现。** 优点：

- 与 reader 实现解耦；
- 输入和检查范围单一；
- 可严格拒绝 unknown fields/schema drift；
- 不需要导入 `agent_runtime` 或 reader builder；
- 可通过固定本地 stdio 管道供 Codex Desktop 使用。

### 方案 C — 只接收 filtered payload

**拒绝。** payload-only 无法独立验证 reader id、ready lifecycle、handoff/representation status、wrapper guarantees、scope identity 来源与 wrapper/payload cross-field links。

### 方案 D — Codex Desktop 直接信任 reader stdout

**拒绝。** 这会把 producer 实现当作 consumer contract，无法发现 wrapper/schema/identity drift。

### 方案 E — 直接实现宿主 bridge、UI 或长期 service

**延期。** Stage 28/29 只讨论一次性 stdin/stdout validation，不引入专有 API、后台进程、刷新、缓存或写操作。

## 3. 输入契约

未来 consumer 唯一输入是 stdin 中的一份完整 v3 reader result：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json | python tools/codex_desktop_filtered_snapshot_consumer.py
```

冻结规则：

- stdin-only；不接受文件路径、URL、socket、环境变量或 credential 参数；
- 最多 1 MiB，在 JSON parse 前拒绝超限；
- strict UTF-8；拒绝空输入、非法 JSON、duplicate object key、非 object；
- 每次进程只消费一个 document，输出一个 validation result 后退出；
- 不自动调用 reader；reader 由宿主通过固定命令显式启动；
- 不接受 v1/v2，也不接受 payload-only document；未来扩展必须升级 consumer schema/version。

## 4. 信任与授权边界

consumer 提供的是**结构、内容 identity 与只读边界验证**，不是签名或真实性证明：

- canonical hash 能发现未同步 identity 的篡改，但不能证明输入一定来自可信 producer；
- Codex Desktop 必须控制固定 reader argv 和本地 stdin pipe，不能从任意文件、剪贴板或网络接收同形 JSON 后宣称可信；
- consumer `pass` 只表示该 document 符合冻结 contract，不授权执行 adapter、approval、command、export 或任何写操作；
- reader 的 `ready` 与 consumer 的 `pass` 都不是 execution permission。

## 5. Version 与 ready gate

只接受：

| 字段 | 固定值 |
|:---|:---|
| reader result schema | `control-plane/codex-desktop-snapshot-read/v3` |
| reader id | `codex-desktop-filtered-envelope-snapshot-json-reader/v3` |
| filtered payload schema | `control-plane/filtered-envelope-snapshot/v1` |
| filter schema | `control-plane/envelope-snapshot-filter/v1` |

验证顺序先检查基础 object/schema/reader。随后：

- `status != ready`：返回 `blocked`，不把失败 reader result 当成可展示 payload；
- `handoff.status != pass` 或 `representation.status != pass`：返回 `blocked`；
- ready document 的 `findings` 必须为空；
- lifecycle 必须精确为：

```text
created → scoping → producing → validating → reading → filtering → ready → closed
```

且 `lifecycle.state == closed`。

## 6. 顶层严格形状

ready v3 顶层字段集合固定为：

```text
status
schema_version
reader
source
lifecycle
handoff
representation
findings
guarantees
next_action
```

关键 nested shape：

- `source`：`project_root`、`relative_envelope`、`envelope_content_id`、`scope_id`、`filter_id`；
- `handoff`：`status`、`exit_code`、`source_handoff_id`；
- `representation`：`status`、`type`、`media_type`、`encoding`、`exit_code`、`base_snapshot_id`、`view_id`、`payload`；
- `next_action.code == filtered_snapshot_loaded`；
- unknown field、missing field 或 wrong type 均为 contract drift，返回 `validation_failed`。

`relative_envelope` 必须是 canonical project-relative allowlist path；consumer 只验证字符串路径语义，不打开该文件。

## 7. Identity 校验

### 7.1 Scope identity — 可重算

wrapper 已包含 scope identity 所需的公开字段：

```text
scope_id = sha256(canonical({relative_envelope, envelope_content_id}))
```

consumer 必须独立重算，并要求 wrapper `source.scope_id == payload.source.scope_id`。

### 7.2 Filter identity — 可重算

```text
filter_id = sha256(canonical(filter))
```

要求：

- filter 字段集合严格；
- task/request 至少一个；
- canonical ASCII exact id；
- wrapper `source.filter_id == payload.source.filter_id == recomputed filter_id`。

### 7.3 View identity — 可重算

```text
view_id = sha256(canonical(filtered_payload_without_view_id))
```

要求：

```text
representation.view_id
  == payload.view_id
  == recomputed view_id
```

### 7.4 Base snapshot identity — 只关联，不伪造重算

输入不包含 Stage 24 完整 base snapshot payload，因此 consumer 不能重算 base snapshot id。只允许检查：

- `representation.base_snapshot_id` 为 canonical content-id shape；
- `representation.base_snapshot_id == payload.source.base_snapshot_id`。

base snapshot 的真实 schema/source/hash 校验仍由 Stage 24/27 reader 链负责。

### 7.5 其他 identity

- `envelope_content_id`：只检查 canonical content-id shape，不读文件重算；
- `handoff.source_handoff_id`：只检查 shape 与 pass status，不重跑 handoff producer；
- 任何 finding 不得声称这些不可重算 identity 已被重新证明。

## 8. Guarantees

ready v3 guarantees 使用严格字段集合与固定值。必须确认：

- explicit user action / one-shot / read-only 为 true；
- reads snapshot JSON、reads envelope scope、filters safe summaries、bounded output、secret scan 为 true；
- reads HTML、writes files/ledgers、network、service、candidate command、adapter、descriptor argv、auto retry、arbitrary path/query、filtered view persistence 为 false。

unknown guarantee 或值漂移均为 unsafe contract。若结构有效但安全值变为 true，返回 `blocked`；字段缺失/类型错误返回 `validation_failed`。

## 9. Safe section 与 filter semantics

filtered payload 字段集合固定为：

```text
status
schema_version
source
filter
summary
sections
view_id
```

只接受 section：

- runs；
- approvals；
- artifacts；
- reports。

拒绝 project overview、tasks、adapter registry、automation、raw envelope、descriptor、argv、input、payload refs、raw refs 或 unknown section。

consumer 还必须独立检查：

- `summary.run_count/approval_count/artifact_count` 与数组长度一致；
- `summary.matched` 等于三个数组是否至少一个非空；
- `summary.section_statuses` 与各 section status 一致；
- request-only：所有行 `request_id` exact match；
- task-only：run 的 `task_id` exact match，approval/artifact 必须直接 task match或其 request 属于 selected run requests；
- task+request：run 同时匹配，approval/artifact request 必须属于 selected run requests；
- reports 继续为 request-scoped unavailable，不伪造持久 report collection；
- row 只接受 Stage 27 已公开的安全字段和标量类型，不接受 unknown/raw nested object。

consumer 不重新排序、不分页、不扩展 lineage，也不尝试从缺失数据推断额外关系。

## 10. 固定检查顺序

未来 consumer 检查 id 冻结为：

```text
document_shape
schema_version
reader_status
lifecycle
guarantees
source_scope_identity
filter_identity
representation_links
view_identity
safe_sections
filter_semantics
```

结果按此顺序输出；未执行检查标记为 `not_run`，不得因 dict/set 顺序改变输出。

## 11. 输出契约

未来 validation result：

```text
control-plane/filtered-snapshot-host-consumer-validation/v1
```

consumer id：

```text
codex-desktop-filtered-snapshot-consumer/v1
```

固定顶层字段：

```text
status
schema_version
consumer
source
checks
findings
guarantees
next_action
```

输出 `source` 只允许：

```text
base_snapshot_id
scope_id
filter_id
view_id
```

不回显：

- task/request filter value；
- relative envelope path；
- runs/approvals/artifacts rows；
- summary、target、message 或原始输入；
- absolute root、argv、secret 或任意未知值。

最终 stdout 最大 64 KiB；超限视为 consumer `error`，不得截断后伪装为完整结果。

## 12. 状态与退出码

| 条件 | consumer status | exit code |
|:---|:---|:---:|
| valid ready v3 | `pass` | 0 |
| stdin/internal error | `error` | 1 |
| unsupported schema/reader、reader 非 ready、unsafe guarantee | `blocked` | 2 |
| malformed/duplicate/shape/identity/section/filter mismatch | `validation_failed` | 5 |

规则：

- `validation_failed` 优先于同一 document 中的 unsafe-value `blocked`；
- 非 ready reader 在基础 schema 可识别后立即 blocked，不读取/回显 payload；
- 不自动重试，不把 blocked/validation_failed/error 降级为 pass。

## 13. 实现边界

Stage 29 若启动，候选工具必须：

- Python 标准库-only；
- 不导入 `agent_runtime`、Stage 18 consumer、Stage 27 reader 或 producer tests；
- 不执行 subprocess、descriptor argv、candidate command 或 adapter；
- 不读取 project root、envelope、ledger、registry、config、`.env`、credential 或 keyring；
- 不访问网络、不启动 service、不写文件；
- 只对 stdin bytes 做 bounded parse/validation，再向 stdout 输出最小结果。

Stage 18 consumer 保持 byte/field/behavior compatibility，不增加 v3 分支。

## 14. Stage 28 前置契约测试

新增：

```text
tests/test_filtered_snapshot_host_consumer_contract.py
```

它通过真实固定 reader stdout 独立验证：

- v3 wrapper、reader、ready lifecycle 与 exact guarantees；
- scope/filter/view 可重算 identity；
- base/filter/scope/view cross-field links；
- 仅 runs/approvals/artifacts/reports；
- 1 MiB 内、strict JSON、deterministic bytes；
- 无 absolute root、argv、input、payload refs、raw refs、project/registry sections。

该测试只冻结 Stage 29 输入前置，不是 consumer 实现，也不让现有 reader 导入未来 consumer。

## 15. Stage 29 TDD 进入条件

Stage 29 开始前必须先写 RED tests，至少覆盖：

1. valid real v3 stdin；
2. unsupported schema/reader 与 non-ready result；
3. lifecycle/handoff/representation/findings drift；
4. guarantee missing/wrong type/unsafe value；
5. scope/filter/view identity mismatch；
6. base snapshot cross-link mismatch，且不声称重算；
7. section/row unknown field 与 summary count mismatch；
8. request-only、task-only、AND relation semantics；
9. duplicate key、非 UTF-8、空输入、非 object、1 MiB 超限；
10. deterministic/minimal output、64 KiB 上限、value-safe findings；
11. no import producer、no file read/write、no network、no subprocess；
12. reader stdout → consumer stdin one-shot smoke；
13. Stage 18 consumer 全量回归不变。

## 16. 明确延期

Stage 28/29 继续不允许：

- payload-only 或 arbitrary JSON consumer；
- 文件/URL/socket 输入；
- query、wildcard、regex、sort/page、lineage expansion；
- 保存/cache/export filtered view；
- HTML/browser、live refresh、polling、server、DB、auth/session；
- UI 写操作、approval resolve、真实 adapter 或 candidate command execution；
- Codex Desktop 专有插件 API 或 QwenPaw bridge。

## 17. Design Gate 结论

**Stage 28 已通过并收口。**

已冻结：

- Codex Desktop 本地任务进程这一具体宿主；
- full v3 result、stdin-only、1 MiB 输入；
- 专用 consumer，不扩展 Stage 18 handoff consumer；
- strict ready/schema/lifecycle/guarantees/section validation；
- scope/filter/view 可重算，base snapshot 只关联；
- filter semantics、最小 value-safe result、64 KiB 输出；
- no import/read/write/network/service/subprocess/execute；
- Stage 29 RED/GREEN 验收矩阵。

Stage 29 已按本设计门实现并收口，事实源为 `docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md` 与 `docs/archive/release-notes/91-release-notes-stage29-codex-desktop-filtered-snapshot-consumer.md`。下一阶段为 **Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate（条件启动）**。

<!-- gate-status: passed -->
<!-- implementation-status: stage29-complete -->

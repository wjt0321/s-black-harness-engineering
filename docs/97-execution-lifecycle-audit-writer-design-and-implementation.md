<!-- parents: archive/96-fixed-git-status-executor-design-gate.md, 56-orchestration-controlled-write-boundary.md -->
<!-- relates: 60-orchestration-run-lifecycle-events-design.md, archive/95-single-user-real-execution-readiness-gate-and-milestone.md -->

# 97 — Execution Lifecycle Audit Writer Design and Implementation

> 状态：**Stage 47 design gate 与 Stage 48 TDD implementation 已收口**
> 日期：2026-07-17
> 前置提交：`dd73d4f`（Stage 46 fixed Git status executor design-only gate）
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`
> 本能力包不新增 subprocess、executor、network、service 或通用 execution CLI

## 1. 目标

Stage 47–48 为第一次真实 spawn 之前补齐专用 execution lifecycle audit writer。它只负责受控写入以下 reserved event：

```text
execution_attempt_started
execution_succeeded
execution_failed
execution_cancelled
```

其中 `execution_attempt_started` 只表示“执行尝试已通过门禁并受控提交”，不表示 child 已创建。terminal event 才记录 outcome 与 phase。writer 必须保证：

1. reserved event 不能由 `runtime event append/import` 伪造；
2. metadata 使用独立 schema、固定 provenance 和严格 allowlist；
3. started 与 terminal 各自按原始 byte size 原子追加，并仅在文件 identity 与 suffix ownership 校验通过时回滚本次写入；
4. terminal 失败不得删除已成功写入的 started；
5. started 唯一、terminal 唯一、terminal 必须引用 matching started；
6. reader 能区分 open attempt、closed attempt 与 invalid audit chain；
7. 不保存 raw stdout/stderr、path、branch、cwd、environment 或 config value。

## 2. 方案比较

### 方案 A：只扩展 `tasks/event.schema.json`

拒绝。共享 enum 放行后，现有通用 append/import 也会接受 execution event，无法证明来源是专用 writer。

### 方案 B：扩展通用 append/import，增加 `writer_origin` 参数

拒绝。通用入口仍由调用方提供完整 event 和 provenance，来源字段只是自报，不能构成隔离。

### 方案 C：独立 schema + 内部专用 writer + 通用入口负向门禁

采用。共享 event schema 只负责 ledger 基础兼容；独立 `tasks/execution-audit-event.schema.json` 冻结 provenance、phase、safe metadata 与 outcome-specific shape。production writer 在模块内部构造 event，不接受 event dict、actor、message、event type 或 arbitrary metadata 覆盖。通用 append/import 在共享 schema 校验之外显式拒绝全部 reserved type。

## 3. Public surface 与调用边界

新增内部 Python API，不新增 CLI：

```text
record_execution_attempt_started(...)
record_execution_terminal(...)
inspect_execution_attempt(...)
validate_execution_audit_ledger(...)
```

Stage 49 fixed executor 只能调用这组 API。v1 writer 固定：

- actor：`local-operator`；
- writer origin：`agent_runtime.execution_audit_writer`；
- writer schema：`execution-audit/v1`；
- event ledger 默认：`tasks/events.jsonl`；
- task ledger 默认：`tasks/tasks.jsonl`；
- event id 与 attempt id 由 writer 生成；
- message 由 event type 固定映射；
- 不接受 file/stdin/URL、event dict、raw output、path、branch、cwd 或 environment。

没有 CLI 是有意边界：Stage 48 交付的是 executor 可复用的内部受控 writer，不是允许 operator 任意制造 execution lifecycle 的新入口。

## 4. Reserved schema 与 provenance

共享 `tasks/event.schema.json` 增加四个 reserved type，使持久 ledger 可被基础 validator 读取。独立 schema 对 execution event 施加更严格约束：

- top-level 复用 event id、task id、timestamp、actor、event type、message；
- `actor` 必须为 `local-operator`；
- `metadata.additionalProperties=false`；
- common metadata 必须包含 `writer_origin`、`writer_schema_version`、`attempt_id`、`request_id`、`plan_hash`、`adapter_id`、`capability`、`operation`、`phase`；
- terminal 必须包含 `started_event_id`；
- succeeded phase 固定为 `post_run_validated`；
- failed phase 只允许 `pre_spawn_recheck`、`spawn`、`child`、`output_validation`、`post_run_guard`、`audit`；
- cancelled phase 固定为 `cancelled`；
- optional evidence 仅允许 exit code、duration bucket、output digest/byte counts、truncation flags、guard status 与 fixed failure code。

`plan_hash` 与 output digest 使用 `sha256:<64 lowercase hex>`。id 字段、adapter/capability/operation/failure code 使用长度受限的 ASCII token。每条 event 还包含 writer-only `append_token`，由 dedicated writer 生成，不接受 caller supplied value，也不进入公开 projection。schema 和 writer 都不得接受额外 metadata。

## 5. Started append contract

`record_execution_attempt_started` 的顺序固定：

1. resolve project-local task/event ledger；
2. 验证 task 存在、输入 identity 与 plan hash shape；
3. 读取并验证现有 execution audit chain；
4. 由 writer 生成唯一 event id 与 attempt id；
5. 构造、共享 schema 校验、独立 schema 校验与 secret/public scan；
6. 在同一个打开的 ledger file descriptor 上获取 dedicated writer lock，记录原始 byte size 与文件 identity；
7. 生成 writer-only `append_token`，在同一 file descriptor 追加一行、flush 与 fsync；write helper 只返回当前调用实际完成的 `owned_bytes`；
8. 对真实 ledger 运行 event schema、task/event consistency 与 execution audit consistency；
9. 成功提交与失败回滚都重新验证 preflight identity/size、path/file identity、原始 boundary 与精确最终 size；
10. post-check 失败时只有 suffix 精确等于 `expected_line[:owned_bytes]` 才 truncate；未知 write 异常按 `owned_bytes=0` 处理，不从公共 JSON prefix 推测所有权；
11. 成功后返回只含 safe ids/status 的 result。

started append 失败时 caller 不得 spawn。成功 result 的语义仍是 `child_created=false`。

若成功提交前或 rollback 前发现 preflight identity/size 漂移、文件被替换/缩短、原始 boundary 与 `owned_bytes` 不一致，或 expected line 后出现额外字节，writer 必须拒绝宣称 committed 或执行 truncate，返回 `error`、`rollback_error=concurrent-ledger-change` 并保留 ledger 供人工审计。不得以“字节内容相同”或任意短 JSON prefix 代替当前 write helper 报告的所有权，也不得为了恢复本次 append 而删除并发 writer 已提交的行。

## 6. Terminal append contract

`record_execution_terminal` 必须先定位唯一 matching started，并验证：

- attempt id 存在且只对应一个 started；
- 尚无 terminal；
- task/request/plan/adapter/capability/operation 与 started 完全一致；
- started provenance 与 dedicated schema 均有效；
- terminal event type 与 phase 匹配；
- evidence 只含 allowlist 字段。

terminal 也使用相同的 writer lock、同一 file descriptor、`append_token` 与 identity/ownership rollback。若 terminal write 或 post-check 失败，只在能够证明原始边界处的行属于本次 terminal append 时回滚；已提交的 started 保留。result 返回 `audit_incomplete=true`，future executor 必须 withheld execution result，并通过 recovery 路径重试 terminal audit 或人工处置。检测到并发 ledger 漂移时不得 truncate。

## 7. Recovery 与一致性

`validate_execution_audit_ledger` 是只读 validator。它按 `attempt_id` 聚合 reserved event，并检查：

- 每个 attempt 恰好一个 started；
- terminal 最多一个；
- terminal 的 `started_event_id`、task/request/plan/adapter/capability/operation 与 started 一致；
- provenance/schema 正确；
- RFC 3339 `date-time` 与 persisted audit secret/public scan 均通过；
- started 在 terminal 之前；
- 不允许 terminal-only、duplicate started、duplicate terminal 或 cross-attempt reference。

合法 open attempt 不视为 schema corruption。`inspect_execution_attempt` 返回：

```text
awaiting_terminal
closed_succeeded
closed_failed
closed_cancelled
missing
invalid
```

inspection 对同一次 `_load_event_records` 得到的 records 完成 schema、persisted scan、chain validation 与 projection，不允许用第二次 path read 的干净快照为第一次脏快照背书。输出只包含 attempt/event/task/request/plan identity、terminal type、phase 与 safe recovery action，不复制任意 raw metadata value。

## 8. 通用入口拒绝

`runtime event append` 与 `runtime event import` 对四个 reserved type 固定返回：

```text
status = blocked
rule_id = reserved-execution-event-type
```

拒绝发生在 candidate 成为可写对象之后、任何 append 之前，并同时覆盖 dry-run、commit、file、stdin 与内部 candidate 参数。batch import 必须逐行给出 value-safe line number；不得把 reserved type 计入可导入 event counts。

这道门禁独立于 schema。即使 shared enum 包含 reserved type，通用入口仍不能写入。

## 9. Failure mapping

| 条件 | status | 说明 |
|:---|:---|:---|
| append + 全部 post-check 通过 | `pass` | 返回 safe writer result |
| reserved type 经通用入口提交 | `blocked` | 不写 ledger |
| input/schema/audit chain 不合法 | `validation_failed` | 不写或回滚本次 append |
| ledger path/read/write/rollback 内部失败 | `error` | finding 不回显敏感值 |
| rollback ownership 检测到并发 ledger 漂移 | `error` | 不 truncate，返回 `concurrent-ledger-change` |
| attempt 不存在 | `needs_input` | terminal 不写 |
| terminal 已存在 | `blocked` | 防止重复 terminal |

rollback 失败必须返回 `error` 和固定 rule id。异常字符串不得携带 candidate、metadata 或 ledger 内容。

## 10. TDD 验收矩阵

Stage 48 至少覆盖：

1. shared schema 接受四个 reserved type；
2. dedicated schema 拒绝错误 actor/origin/version、额外 metadata 与 raw/path/env 字段；
3. append/import dry-run 和 commit 均拒绝 reserved type；
4. started happy path、safe result、固定 provenance 与 `child_created=false`；
5. unknown task、bad plan hash、unsafe ledger path、missing ledger 与 newline guard；
6. started write/post-check failure byte-size + suffix ownership rollback；
7. terminal success/failed/cancelled outcome 与 phase mapping；
8. terminal-only、missing started、duplicate started、duplicate terminal、plan/request/task mismatch；
9. terminal failure保留 started，且 result 标记 audit incomplete；
10. open/closed/missing/invalid recovery state；
11. deterministic safe projection，不含 raw output、path、branch、cwd、environment 或 secret；
12. doctor 注册独立 schema；
13. Stage 44 readiness v1 保持历史 10 pass / 3 blocked snapshot；
14. known partial write、unknown owned byte count、byte-identical concurrent append、terminal rollback failure、同 payload 不同 append provenance、并发 append 漂移、preflight/append file identity replacement 与 ledger stat failure；
15. post-check exception、post-check 后额外字节与 exact-size commit guard；
16. task/event ledger schema、RFC 3339 timestamp、same-snapshot persisted secret scan 与 value-safe finding；
17. controlled-write regression 覆盖通用入口不可伪造与专用 writer append/rollback；
18. source 不导入 subprocess/socket/requests，不执行外部命令。

## 11. 明确不做

- 不实现 fixed Git status executor；
- 不执行 Git 或任何 subprocess；
- 不新增 execution CLI；
- 不开放任意 event metadata；
- 不实现 approval-required adapter plan binding；
- 不访问网络、credential、`.env`、keyring；
- 不引入 service、DB、queue、background worker 或 UI；
- 不创建 tag、不 push。

## 12. Stage 48 实现结果

已按本设计门落地：

- `tasks/execution-audit-event.schema.json`：固定 actor、writer origin/version、writer-only append token、四类 event/phase 与 safe evidence allowlist；
- `agent_runtime/execution_audit_writer.py`：内部-only started/terminal writer、同一 file descriptor + dedicated lock append、preflight identity/size binding、owned-byte rollback、exact-size commit、same-snapshot persisted scan、audit validator 与 recovery inspection；
- `agent_runtime/task_validation.py`：task/event schema 启用 RFC 3339 format checker，reserved event 在共享 event schema 之外叠加 dedicated schema；
- `runtime event append/import`：四类 reserved event 在 dry-run/commit 均以 `reserved-execution-event-type` 显式拒绝；
- Stage 44 readiness v1 保持历史 `10 pass / 3 blocked`，新增 dedicated event enum 不改写旧快照；
- controlled-write regression 在临时 project root 完成 started → terminal 链并证明真实仓库 ledger 不变。

writer 结果只投影 safe identity/status，不投影 `append_token`。`execution_attempt_started` 成功仍固定 `child_created=false`；terminal 写入或 post-check 失败只在 `owned_bytes`、append provenance、preflight size 与 file identity 校验通过时回滚 terminal 行，保留 started 并返回 `audit_incomplete=true`。post-check 抛出异常也必须结构化返回并先尝试同一 ownership-checked rollback。若检测到并发 append、额外 bytes 或 path identity replacement，则不得宣称 committed，保留全部可见 ledger 字节并要求人工恢复。

本阶段没有新增 CLI、subprocess、network、service、DB、UI、tag 或 push。

## 13. 验证入口

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

Stage 48 收口要求以上命令全部退出 `0`；release notes 107 与 `tasks/handoff-2026-07-17.md` 记录最终验证结论。

## 14. Milestone 结论

Stage 47 设计门冻结后，Stage 48 以同一事实源记录实现与验收。完成条件是 dedicated writer、reserved schema、通用入口负向门禁、recovery validator 和 controlled-write regression 全部通过。

完成后下一阶段仍为 **Stage 49 — Fixed Git Status Executor Implementation and Limited Enablement（条件启动）**。Stage 49 需要用户再次明确授权真实 subprocess，并且 Stage 46 的 trust/image binding、sanitized child PATH、process-tree containment 与 finite porcelain parser 全部能在目标平台闭合。

> 2026-07-17 post-close：用户已明确授权 Stage 49 的唯一 fixed subprocess；Windows limited enablement 已按 `docs/98-fixed-git-status-executor-implementation-and-limited-enablement.md` 完成。该实现复用本文件 writer，但不改变本文件的内部 API、reserved provenance、rollback 或 recovery contract。通用 execution、POSIX 与第二个 operation 仍 unavailable。

<!-- stage47-gate-status: frozen -->
<!-- stage48-implementation-status: complete -->
<!-- execution-status: superseded-by-stage49-windows-limited-enablement -->

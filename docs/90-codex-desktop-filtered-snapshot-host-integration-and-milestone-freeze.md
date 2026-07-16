<!-- parents: 89-codex-desktop-filtered-snapshot-consumer-implementation.md, 87-filtered-envelope-snapshot-json-reader-implementation.md -->
<!-- relates: 64-versioning-governance.md, archive/77-read-only-control-plane-milestone-freeze.md -->

# 90 — Codex Desktop Filtered Snapshot Host Integration 与里程碑冻结

> 状态：**Stage 30 design gate、Stage 31 实现与 Stage 32 milestone freeze 均已收口**
> 日期：2026-07-16
> 冻结里程碑：`v0.14.0-filtered-snapshot-host-integration`

## 1. 决策摘要

Stage 30 选择 Codex Desktop 本地一次性任务进程作为具体宿主边界，冻结一个固定、前台、只读的 filtered snapshot host contract：

```text
codex-desktop-filtered-snapshot-host/v1
```

宿主只执行以下固定链路：

```text
用户显式选择 project root + envelope + exact task/request filter
  -> fixed filtered v3 reader argv
  -> reader stdout bytes
  -> fixed Stage 29 consumer argv / stdin
  -> consumer pass + identity cross-check
  -> one-shot in-memory safe payload
  -> closed
```

本阶段不接入 Codex Desktop 专有插件 API；“Codex Desktop host”仅指可由本地任务宿主调用的独立短进程工具。

## 2. 启动条件与输入

Stage 30 条件已由用户明确要求推进到下一阶段里程碑而成立。v1 只接受：

- 一个受支持的 `agent-runtime` project root；
- 一个由 filtered v3 reader 校验的 project-relative envelope；
- 至少一个 canonical exact `task_id` / `request_id` filter；
- `0 < timeout <= 60` 的可选超时；
- 显式 `--json` 自动化兼容参数。

不接受 URL、任意 query、wildcard、regex、sort/page、文件输出位置、shell 字符串、descriptor argv、candidate command 或 adapter 参数。

## 3. 固定进程所有权

宿主拥有且只能构造两个 argv 数组：

1. `python tools/codex_desktop_snapshot_json_reader.py ... --representation snapshot-json ... --json`；
2. `python tools/codex_desktop_filtered_snapshot_consumer.py`。

规则：

- 使用 `shell=False`，不执行 descriptor 中声明的 argv；
- reader stdout 原样通过本地 stdin 传给 consumer，不落盘；
- 不允许用户替换 executable、script、argv template 或 consumer；
- 每个进程只运行一次，不 retry、不 polling、不 watch；
- cwd 固定为已校验 project root；
- 子进程只获得最小非敏感环境白名单，并设置 `PYTHONDONTWRITEBYTECODE=1`；
- reader stdout 上限 1 MiB，consumer stdout 上限 64 KiB；
- stderr 不进入结构化结果，不回显原始进程输出。

## 4. Validation-before-display

宿主不得因为 reader exit 0 或 JSON 可解析就展示 payload。只有同时满足以下条件才进入 `ready`：

1. Stage 29 consumer 返回 `pass` / exit 0；
2. consumer schema、consumer id、checks、guarantees 和固定 shape 有效；
3. reader stdout 是 strict UTF-8 JSON object，无 duplicate key；
4. consumer 输出的 `base_snapshot_id/scope_id/filter_id/view_id` 与 reader wrapper 和 filtered payload 完全一致；
5. reader process exit 0；
6. 最终 host result 不超过 1 MiB。

consumer 非 pass 时，不解析或复制 filtered payload；只映射安全状态和安全 rule id。宿主自身不重新实现 Stage 29 的 safe section/filter 语义 validator，也不绕过 consumer。

## 5. 输出契约

输出 schema：

```text
control-plane/codex-desktop-filtered-snapshot-host/v1
```

固定顶层字段：

- `status`：`ready/error/blocked/validation_failed`；
- `schema_version`；
- `host`；
- `source`：只输出 `project_root` sentinel，不回显绝对路径或 envelope path；
- `lifecycle`；
- `reader`：只输出状态与 exit code；
- `consumer`：状态、exit code 和四个 content ids；
- `representation`：仅 ready 时包含已验证 filtered payload；
- `findings`：value-safe host findings；
- `guarantees`；
- `next_action`。

ready payload 是 Stage 27 filtered payload 的内存投影，可包含用户显式 filter 值和已验证 safe summaries；它不包含 absolute project root、relative envelope、raw ledger、argv、credential 或未知扩权字段。

## 6. 生命周期与状态映射

```text
created
  -> reading
  -> validating
  -> ready | blocked | validation_failed | error
  -> closed
```

| 条件 | host status | exit |
|:---|:---|:---:|
| consumer pass / 0，reader 0，identity cross-check pass | `ready` | 0 |
| consumer blocked / 2 | `blocked` | 2 |
| consumer validation_failed / 5 | `validation_failed` | 5 |
| timeout、spawn/protocol/output/identity error、consumer error | `error` | 1 |

任何 status/exit mismatch 均为 host `error`。不自动重试，不把失败降级为 ready。

## 7. 安全边界

v1 保证：

- explicit action、one-shot、read-only；
- validation before display；
- no file write、no ledger write、no persistence/cache/export；
- no network、no service、no DB、no auth/session；
- no HTML/browser、no live refresh；
- no descriptor argv、candidate command 或 adapter execution；
- no arbitrary query；
- bounded input/output 与 value-safe failure；
- v1/v2 reader、Stage 18 consumer 与 Stage 29 consumer compatibility 不变。

## 8. Stage 31 TDD 验收矩阵

实现前 RED tests 至少覆盖：

1. 固定 reader/consumer argv、cwd、stdin pipe 与最小环境；
2. valid request-only、task-only、AND filtered payload ready；
3. consumer pass 前绝不释放 payload；
4. blocked/validation_failed/error 和 exit mapping；
5. malformed、duplicate、unknown-field、status/exit drift；
6. content id cross-link mismatch；
7. invalid root/filter/timeout 不 spawn；
8. timeout/output limit 不 retry；
9. determinism、绝对路径/envelope/stderr 不回显；
10. real local stdio pipeline；
11. Stage 18、Stage 27、Stage 29 compatibility regression；
12. no network/service/write/descriptor argv/adapter execution。

## 9. 明确延期

Stage 30–32 不开放：

- Codex Desktop 专有插件或 UI；
- HTML/browser/render；
- live service、polling、watch、network、DB、auth；
- cache、persistence、export 或任意文件写入；
- query language、wildcard、regex、sort/page、lineage expansion；
- approval resolve、UI write、真实 adapter/candidate command execution。

## 10. Stage 30 结论

**Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate 已通过并冻结。** Stage 31 仅可按本合同实现本地 one-shot host；不得借实现扩大到专有 API、UI、服务化或写操作。

<!-- gate-status: passed -->
<!-- implementation-status: stage31-complete -->

## 11. Stage 31 实现

新增独立工具：

```text
tools/codex_desktop_filtered_snapshot_host.py
```

实现固定输出：

```text
control-plane/codex-desktop-filtered-snapshot-host/v1
codex-desktop-filtered-snapshot-host/v1
```

实际行为：

- 校验 project root、至少一个 canonical exact filter、bounded envelope argument 与 `0 < timeout <= 60`；
- 只构造固定 reader argv 和固定 Stage 29 consumer argv，使用 `shell=False`；
- 固定最小环境白名单，不转发任意用户变量，并设置 `PYTHONDONTWRITEBYTECODE=1`；
- reader stdout 最大 1 MiB，consumer stdout/stderr 最大 64 KiB，host stdout 最大 1 MiB；
- consumer output 严格检查 schema/id/shape/status-exit/checks/guarantees/source；
- consumer pass 后才 strict parse reader result，并交叉核对 base/scope/filter/view identity；
- ready 时只释放 Stage 29 已验证的 filtered payload；失败时 payload 固定为 `null`；
- 不回显 absolute project root、relative envelope、stderr 或未验证输入；
- 不 retry、不写文件/ledger、不访问网络、不启动 service、不执行 descriptor argv、candidate command 或 adapter。

## 12. Stage 31 TDD 与真实验收

新增：

```text
tests/test_codex_desktop_filtered_snapshot_host.py
```

TDD 证据：

1. RED：14 项测试中的首批 12 项因 host 工具不存在而失败，失败原因与预期一致；
2. GREEN：最小 host 实现后 15 项专用测试全部通过；
3. 相关回归：Stage 18/20 与 Stage 22–29 的 99 项相关测试全部通过；
4. 全量：857 项测试全部通过；
5. `doctor`、`public_scan.py`、`py_compile` 均通过。

真实 one-shot smoke：

```bash
python tools/codex_desktop_filtered_snapshot_host.py \
  --project-root . \
  --envelope adapters/execution-envelope.examples.json \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --timeout-seconds 30 \
  --json
```

结果为 `ready` / exit 0，lifecycle 为 `created → reading → validating → ready → closed`；consumer 为 `pass`，host 只在 identity cross-check 后返回 AND-filtered safe payload。

## 13. Compatibility freeze

以下既有契约保持不变：

- Stage 18 `tools/control_panel_handoff_consumer.py`；
- Stage 20 `tools/codex_desktop_read_only_adapter.py`；
- Stage 22 v1 project-scoped reader；
- Stage 24 v2 envelope-scoped reader；
- Stage 27 v3 filtered reader；
- Stage 29 stdin-only consumer。

host 是 additive tool；没有修改 CLI 主入口、reader/consumer schema、ledger、schema、registry 或受控写入模块。

## 14. Stage 32 — v0.14.0 里程碑冻结

`v0.13.0-read-only-control-plane` 之后，Stage 17–31 已形成第二个可独立引用的 read-only host capability bundle：

- stdio handoff 与独立 validation consumer；
- Codex Desktop one-shot host process boundary；
- project/envelope scoped snapshot JSON reader；
- canonical task/request exact filter、AND/空视图与 identity；
- 独立 filtered snapshot consumer；
- validation-before-display 的 one-shot filtered snapshot host。

因此按 `docs/64-versioning-governance.md` 冻结本地 annotated tag：

```text
v0.14.0-filtered-snapshot-host-integration
```

本次 tag 只在本地创建，不 push；tag target 以本地 `git rev-parse v0.14.0-filtered-snapshot-host-integration^{commit}` 为准。

冻结不表示以下能力开放：专有 Codex Desktop 插件/UI、HTML/browser、live refresh/service、network/DB/auth、cache/persistence/export、arbitrary query、UI write 或真实 adapter execution。

## 15. 下一阶段上下文

下一阶段为 **Stage 33 — Codex Desktop Filtered Snapshot Display Integration Gate（条件启动）**。只有出现具体宿主展示面与显式用户需求时，才审计：

- host result 到一次性展示组件的数据边界；
- 取消、窗口关闭和内存清理；
- safe summary 呈现与空视图 UX；
- 不引入 HTML/browser、持久缓存、网络服务或写操作的可行性。

没有具体展示面时保持本里程碑冻结，不创建通用 UI/service。

## 16. 收口结论

**Stage 30、Stage 31 与 Stage 32 均已完成收口。** `v0.14.0-filtered-snapshot-host-integration` 是新的本地稳定里程碑；等待用户后续指挥再决定是否条件启动 Stage 33。

<!-- milestone-status: frozen-local -->
<!-- next-stage: stage33-conditional -->

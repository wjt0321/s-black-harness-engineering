<!-- parents: 86-filtered-envelope-snapshot-read-design-gate.md, 84-envelope-scoped-snapshot-read-design-gate.md -->
<!-- relates: 83-codex-desktop-snapshot-json-reader-implementation.md, 79-read-only-host-consumer-validation-boundary.md -->

# 87 — Filtered Envelope Snapshot JSON Reader Implementation

> Stage 27 实现与验收事实源。在既有 `tools/codex_desktop_snapshot_json_reader.py` 上增加结构化 task/request filtered v3，不创建平行 reader；无 filter v2 与无 envelope v1 保持兼容。

## 1. 实现摘要

Stage 27 按 Stage 26 设计门落地：

- 新增 `--task-id` / `--request-id`；
- filter 至少一个，必须与显式 `--envelope` 同时使用；
- task-only、request-only 与 task+request AND；
- task view 使用 runs 的 request→task 映射包含 response artifacts；
- 合法无匹配返回 `ready` 空视图与 `matched=false`；
- 新增 filtered v3 result、payload、filter id 与 view id；
- filter 只作用于完整验证后的安全 summaries，不进入 child argv；
- 不新增通用 query、sort/page、lineage expansion、持久化或 export。

实现继续复用固定链路：

```text
validate filter + envelope scope
  -> fixed handoff producer
  -> Stage 18 reference consumer
  -> fixed snapshot producer
  -> Stage 24 schema/source/identity/hash/content-drift validation
  -> in-memory safe-summary filtering
  -> filter/view identity validation
  -> bounded v3 JSON result
```

## 2. CLI 契约

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --task-id task-20260703-001 \
  --json
```

或：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json
```

两个 filter 同时出现时使用 AND。以下命令面仍不存在：

```text
--filter
--query
--sort
--page
--export
```

## 3. 输入门禁

### 3.1 Filter 与 scope

- filter 无 envelope：`filter-envelope-required`；
- task 形状：`task-[0-9]{8}-[0-9]{3,}`；
- request 形状：`req-[0-9]{8}-[0-9]{3,}`；
- 最大 128 ASCII bytes；
- 不 trim、不大小写折叠，不接受 Unicode、空白、列表、通配符或正则；
- CLI 中同一个 filter flag 重复：`filter-argument-duplicate`；
- invalid/duplicate filter 均在启动 child process 前失败，finding 不回显完整值。

### 3.2 兼容模式

| 输入 | 输出 |
|:---|:---|
| 无 envelope、无 filter | Stage 22 v1 |
| envelope、无 filter | Stage 24 v2 |
| envelope + task/request filter | Stage 27 v3 |
| filter、无 envelope | `validation_failed` |
任何显式提供 task/request filter 的请求（包括 filter/envelope 输入门禁失败）均使用 v3 wrapper；未请求 filter 的既有 v1/v2 失败口径不变。


## 4. 匹配语义

### task-only

1. 过滤 `run.task_id`；
2. 收集 selected request ids；
3. approval/artifact 若直接 task 匹配，或 request 属于 selected requests，则保留。

这保证 adapter response 即使安全摘要中 `task_id=""`，仍能通过 request relation closure 出现在正确 task view。

### request-only

runs、approvals、artifacts 均使用 `request_id` exact match。

### task + request

run 必须同时匹配两个值，再以该 selected request set 过滤 approval/artifact。二者不一致时返回合法空视图，不降级、不猜测。

## 5. v3 输出

版本：

| 内容 | 版本 |
|:---|:---|
| reader result | `control-plane/codex-desktop-snapshot-read/v3` |
| reader id | `codex-desktop-filtered-envelope-snapshot-json-reader/v3` |
| payload | `control-plane/filtered-envelope-snapshot/v1` |
| filter | `control-plane/envelope-snapshot-filter/v1` |

filtered payload 只包含：

- source：base snapshot id、scope id、filter id；
- canonical filter；
- matched 与 run/approval/artifact counts；
- runs / approvals / artifacts；
- request-scoped unavailable reports。

不会返回 project overview/tasks、adapter registry、automation、raw envelope、descriptor 或 argv。

## 6. Identity

```text
filter_id = sha256(canonical(filter))
view_id = sha256(canonical(filtered_payload_without_view_id))
```

reader 在输出前调用独立 `_validate_filtered_payload()` 重算：

- filter schema 与 canonical id；
- base snapshot id / scope id 形状；
- view canonical hash。

过滤后 payload 不复用 Stage 24 base snapshot id。representation 分别输出 `base_snapshot_id` 与 `view_id`。

## 7. 生命周期与执行边界

v3 生命周期：

```text
created → scoping → producing → validating → reading → filtering → ready → closed
```

filter 不传给：

- handoff producer；
- reference consumer；
- snapshot producer；
- descriptor。

新增 guarantees：

```text
filters_safe_summaries = true
allows_arbitrary_queries = false
persists_filtered_views = false
```

其余 no-write、no-network、no-service、no-HTML、no-descriptor-argv、no-adapter-execution 边界保持不变。

## 8. TDD 证据

实现前新增测试并确认 7 个预期失败：

- parser 尚无 task/request flags；
- reader API 尚不接受 filter；
- duplicate filter 由 argparse 拒绝而非结构化 JSON；
- filtered v3 与 real stdio 尚不存在。

最小实现完成后，目标测试覆盖：

- v1/v2 既有契约；
- task relation closure；
- request-only 与 AND；
- ready empty view；
- filter/view identity 与 tamper rejection；
- invalid/no-envelope/duplicate pre-spawn failure；
- fixed argv 无 filter；
- safe summaries、无 raw values；
- filtered real stdio。

## 9. 安全边界

Stage 27 仍然不：

- 读取 HTML 或打开浏览器；
- 保存/cache/export filtered view；
- 访问网络、DB、auth/session；
- 启动 service、轮询、刷新或 retry；
- 执行 descriptor argv、candidate command 或真实 adapter；
- 扩展 parent/retry/fallback lineage；
- 提供 arbitrary query 或任意路径读取。

## 10. 验收结论

**Stage 27 已实现并收口。**

当前 reader 已形成三个显式兼容层：

1. project-scoped v1；
2. envelope-scoped、无 filter v2；
3. envelope-scoped、结构化 exact filter v3。

Stage 28 — Filtered Snapshot Host Consumer Validation Gate 已完成设计冻结，事实源为 `docs/archive/88-filtered-snapshot-host-consumer-validation-gate.md` 与 `docs/archive/release-notes/90-release-notes-stage28-filtered-snapshot-host-consumer-validation-gate.md`。下一阶段为 **Stage 29 — Codex Desktop Filtered Snapshot Consumer Implementation（条件启动）**；Stage 28 没有实现 consumer，继续不增加缓存、export、HTML 或长期进程。

<!-- implementation-status: stage27-complete -->
<!-- compatibility: v1-v2-preserved -->

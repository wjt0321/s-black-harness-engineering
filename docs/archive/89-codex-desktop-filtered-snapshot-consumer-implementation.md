<!-- parents: 88-filtered-snapshot-host-consumer-validation-gate.md -->
<!-- relates: 87-filtered-envelope-snapshot-json-reader-implementation.md, 79-read-only-host-consumer-validation-boundary.md -->

# 89 — Codex Desktop Filtered Snapshot Consumer Implementation

> Stage 29 实现与验收事实源。用户于 2026-07-16 明确要求继续推进到下一阶段收口；本阶段按 Stage 28 冻结契约实现独立标准库-only、stdin-only filtered v3 consumer，并保持 Stage 18 consumer 与 Stage 27 reader 行为不变。

## 1. 阶段结论

Stage 29 已完成实现：

```text
tools/codex_desktop_filtered_snapshot_consumer.py
```

该工具只消费 stdin 中的一份完整：

```text
control-plane/codex-desktop-snapshot-read/v3
```

输出：

```text
control-plane/filtered-snapshot-host-consumer-validation/v1
consumer: codex-desktop-filtered-snapshot-consumer/v1
```

consumer `pass` 只表示输入符合 Stage 28 冻结的结构、identity、safe sections 与只读边界，不证明 producer 真实性，也不授予 execution、approval、export 或写入权限。

## 2. TDD 证据

先新增：

```text
tests/test_codex_desktop_filtered_snapshot_consumer.py
```

首次单独执行 valid v3 用例时按预期失败：

```text
AssertionError: Stage 29 consumer has not been implemented
```

随后实现最小工具并完成 GREEN。实现过程中又先新增 nested payload/filter schema allowlist 用例，确认现有实现错误返回 `validation_failed` 后，再修正为冻结契约要求的 `blocked` / exit 2。

最终专用测试覆盖 29 个用例，包括 valid request/task view、schema/status/lifecycle/guarantees、scope/filter/base/view identity、safe sections、filter semantics、stdin gates、determinism、value-safe output、真实 stdio 与禁止依赖。

## 3. 输入门禁

冻结实现：

- stdin-only；命令行参数被结构化拒绝，不接受文件、URL、环境变量或其他输入参数；
- 每次进程只读取一份 JSON document；
- 最大输入 1 MiB，在 parse 前拒绝超限；
- strict UTF-8；
- 拒绝空输入、非法 JSON、duplicate object key 和非 object；
- 不接受 v1/v2 reader result，也不接受 filtered payload-only；
- stdin 读取异常返回 `error`，不回显异常值或原始输入。

## 4. 固定检查顺序

实现严格按 Stage 28 顺序输出：

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

规则：

- 已完成检查为 `pass`；
- 首个失败检查为 `failed`；
- 后续未执行检查为 `not_run`；
- 结果不依赖 dict/set 遍历顺序；
- 每次只输出一个 value-safe finding，避免聚合未知输入值。

## 5. Schema 与 ready gate

只接受：

| 对象 | 固定版本 |
|:---|:---|
| reader result | `control-plane/codex-desktop-snapshot-read/v3` |
| reader id | `codex-desktop-filtered-envelope-snapshot-json-reader/v3` |
| filtered payload | `control-plane/filtered-envelope-snapshot/v1` |
| filter | `control-plane/envelope-snapshot-filter/v1` |

unsupported top-level、payload 或 filter schema 均返回：

```text
status: blocked
exit: 2
check: schema_version
```

ready gate 还要求：

- reader `status == ready`；
- handoff `pass` / exit 0 / canonical source handoff id；
- representation `pass` / exit 0；
- reader findings 为空；
- `next_action.code == filtered_snapshot_loaded`。

非 ready reader 在 schema 可识别后立即 blocked，不把 payload 当作可展示结果。

## 6. Lifecycle 与 guarantees

lifecycle 必须精确为：

```text
created → scoping → producing → validating → reading → filtering → ready → closed
```

并要求 `state == closed`。

reader guarantees 使用严格字段集合和固定布尔值。字段缺失、unknown 或非布尔值为 `validation_failed`；安全值漂移，例如 `writes_files=true`，为 `blocked`。

consumer 自身输出 guarantees 冻结为：

- stdin-only、read-only、reads filtered snapshot；
- bounded input/output；
- 不写文件、不持久化输入；
- 不访问网络、不启动 service；
- 不执行 reader、command 或 adapter。

## 7. Identity 实现

### 7.1 独立重算

consumer 使用标准库 canonical JSON 独立重算：

```text
scope_id  = sha256(canonical({relative_envelope, envelope_content_id}))
filter_id = sha256(canonical(filter))
view_id   = sha256(canonical(filtered_payload_without_view_id))
```

并检查 wrapper/payload/representation 的 cross-field links。

### 7.2 只关联检查

以下 identity 因原始材料未随 stdin 提供，只检查 canonical hash shape 与 cross-field 一致性：

- base snapshot id；
- envelope content id；
- source handoff id。

consumer 不读取 envelope、不重跑 handoff、不接收或构造 base snapshot payload，因此不会把关联检查描述为真实性证明。

## 8. Safe section 与 filter semantics

只接受：

- runs；
- approvals；
- artifacts；
- request-scoped unavailable reports。

实现严格检查：

- section 和 row 字段集合；
- row 仅使用 Stage 27 已公开的字符串/布尔安全标量；
- 禁止 unknown nested object、raw、input、argv、payload refs 等扩权字段；
- counts 与数组长度一致；
- summary section statuses 与 section status 一致；
- `matched` 与三类数组是否至少一个非空一致；
- request-only 所有行 exact request match；
- task-only run exact task match，approval/artifact 允许直接 task match或 selected run request relation closure；
- task+request run 同时匹配，approval/artifact request 必须属于 selected run requests；
- reports 固定为 request-scoped unavailable，不伪造持久 collection。

consumer 不排序、不分页、不查询、不展开 lineage，也不从缺失数据推断新关系。

## 9. 输出最小化

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

`source` 只允许：

```text
base_snapshot_id
scope_id
filter_id
view_id
```

不回显 task/request id、relative envelope、rows、target、summary、message、原始 input 或未知值。最终 stdout 上限为 64 KiB；若固定结果意外超限，返回最小 `error` result，而不是截断后伪装完整。

## 10. 状态与退出码

| 条件 | status | exit |
|:---|:---|:---:|
| valid ready filtered v3 | `pass` | 0 |
| stdin/internal read failure | `error` | 1 |
| unsupported schema/reader、non-ready、unsafe guarantee | `blocked` | 2 |
| malformed/duplicate/shape/identity/section/filter mismatch | `validation_failed` | 5 |

不自动重试，不把失败状态降级为 pass。

## 11. 独立性与兼容性

生产工具只导入 Python 标准库：

- 未导入项目 package；
- 未导入 Stage 18 consumer；
- 未导入 Stage 27 reader；
- 不创建进程；
- 不打开任何路径；
- 不访问网络、不启动后台服务、不写文件。

Stage 18 `tools/control_panel_handoff_consumer.py` 保持原 contract；Stage 27 `tools/codex_desktop_snapshot_json_reader.py` 的 v1/v2/v3 行为保持不变。

## 12. 真实 stdio 验收

已验证固定本地管道：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json \
| python tools/codex_desktop_filtered_snapshot_consumer.py
```

consumer 返回 `pass` / exit 0，11 个检查均为 pass；输出只包含四个 content ids，不包含 filter value、relative path 或 summary rows。

该 smoke 只验证宿主可采用的 stdio 组合方式；consumer 本身仍不会自动启动 reader。

## 13. 明确延期

Stage 29 未开放：

- Codex Desktop 专有 bridge 或 UI；
- 自动执行 reader 或 descriptor argv；
- 文件/URL 输入；
- cache、persistence、export；
- HTML/browser；
- query、wildcard、regex、sort/page、lineage expansion；
- live service、network、DB、auth；
- UI controlled write 或真实 adapter execution。

## 14. 收口结论

**Stage 29 — Codex Desktop Filtered Snapshot Consumer Implementation 已完成收口。**

下一阶段为 **Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate（条件启动）**。只有具体宿主需要把固定 reader → consumer 管道映射为一次性展示状态时才启动；第一拍仍应是 design gate，不直接引入 UI、service 或持久化。

本阶段不创建 tag；`v0.13.0-read-only-control-plane` / `f401b98` 继续作为稳定 milestone。

<!-- implementation-status: stage29-complete -->
<!-- compatibility: stage18-stage27-preserved -->

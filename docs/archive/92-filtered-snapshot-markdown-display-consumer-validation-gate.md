<!-- archived: Stage 39 started; retained as the Stage 36-38 / v0.16.0 fact source -->
<!-- parents: archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md -->
<!-- relates: 89-codex-desktop-filtered-snapshot-consumer-implementation.md, 79-read-only-host-consumer-validation-boundary.md, 64-versioning-governance.md -->

# 92 — Filtered Snapshot Markdown Display Consumer Validation Gate

> 状态：**Stage 36 design gate、Stage 37 实现与 Stage 38 milestone freeze 均已收口**
> 日期：2026-07-16
> 冻结里程碑：`v0.16.0-filtered-snapshot-display-consumer`（annotated tag 已推送至 `origin`）

## 1. 决策摘要

Stage 36 选择独立、标准库-only、stdin-only consumer 验证 Stage 34 完整 display v1 wrapper。冻结 contract：

```text
control-plane/filtered-snapshot-markdown-display-consumer-validation/v1
codex-desktop-filtered-snapshot-markdown-display-consumer/v1
```

固定数据流：

```text
完整 display v1 JSON bytes on stdin
  -> bounded strict UTF-8 / duplicate-key gate
  -> wrapper/status/lifecycle/guarantees gate
  -> representation identity/content hash gate
  -> deterministic Markdown grammar + safe literal gate
  -> count/filter/identity/empty-view coherence gate
  -> minimal validation result on stdout
```

consumer 不启动 display、host、reader、其他 consumer、command 或 adapter，不接受文件、URL、payload-only 或 raw Markdown。

## 2. 为什么需要独立 consumer

Stage 34 wrapper 已验证 host 并安全投影 Markdown，但未来宿主不能仅因收到 JSON 就信任 content。独立 consumer 提供进程外 contract validation：

- 防止 wrapper schema/status/lifecycle 漂移；
- 独立重算 content UTF-8 SHA-256；
- 确认动态值仍是受限 ASCII JSON inline literal，而不是 raw Markdown/HTML/link；
- 确认固定 headings/section/row field order、identity links、counts 与 empty-view 一致；
- 只输出最小 ids/checks，不复制 Markdown content。

它不重新证明 base snapshot、ledger 或 host payload 的真实性，也不授予 execution/UI write 权限。

## 3. 输入 contract

只从 stdin 读取一份完整 JSON object：

- 最大 64 KiB；
- strict UTF-8；
- 拒绝空输入、非法 JSON、duplicate key、trailing ambiguity 和非 object；
- exact `control-plane/codex-desktop-filtered-snapshot-display/v1`；
- exact `codex-desktop-filtered-snapshot-markdown-display/v1`；
- exact top-level/source/lifecycle/host/representation/findings/guarantees/next_action shape；
- 不接受 file、path、URL、payload-only、content-only 或 raw Markdown mode。

## 4. 状态与 lifecycle 验证

consumer 必须核对 display status 与固定 exit semantics：

```text
ready -> host ready/0 -> representation pass/content present
blocked -> host blocked/2 -> representation withheld
validation_failed -> host not_run/null 或 validation_failed/5 -> withheld
error -> host not_run/null、error/1 或 ready/0 projection failure -> withheld
```

lifecycle 必须 `created ... <status> closed`，只接受 Stage 34 冻结的有界 phase grammar；不得把 non-ready 升级为 pass display。

consumer 自身状态映射：

| 输入结果 | consumer status | exit |
|:---|:---|:---:|
| valid ready display | `pass` | 0 |
| valid blocked display / unsupported schema | `blocked` | 2 |
| valid upstream validation_failed 或 malformed contract | `validation_failed` | 5 |
| valid upstream error 或 consumer I/O/internal error | `error` | 1 |

## 5. Ready representation gate

ready 时必须验证：

- exact markdown metadata；
- base/scope/filter/view/content ids 均为 canonical SHA-256；
- `content_id == sha256(content UTF-8 bytes)`；
- content 非空、无 CR、NUL 或非允许 control characters；
- display findings empty、next action 为 `review_markdown_display`；
- exact display guarantees。

identity 只验证 wrapper link 与 Markdown identity section 一致，不重算 Stage 27 view identity。

## 6. Markdown grammar 与 escaping invariant

consumer 不使用通用 Markdown parser，也不渲染 content。只接受 Stage 34 固定 grammar：

1. `# Filtered Snapshot`；
2. Overview：Matched、Run/Approval/Artifact Count；
3. Filter：Task ID、Request ID；
4. Identity：base/scope/filter/view id；
5. Runs、Approvals、Artifacts，按固定 row heading 与字段顺序；
6. Reports 固定 5 字段。

所有动态值必须是单行 inline code 内的 ASCII JSON scalar literal：string/bool/int/null。literal 内禁止 raw backtick、pipe、`<`、`>`、`&`、brackets/parentheses；这些字符只能以 `\uXXXX` 可见 escape 出现。解析后 ID/filter/count/type 仍需符合约束。

不接受 raw HTML、image/link syntax、fenced code、任意 headings、任意字段、额外文本或 reordered sections。

## 7. Coherence 与空视图

- Overview counts 必须等于对应 row block 数；
- `matched == bool(run_count or approval_count or artifact_count)`；
- count 必须为非负 plain int；
- task/request 至少一个非 null 且为 canonical exact id；
- Identity 四项必须与 wrapper representation ids 一致；
- collection 为零时只能出现固定 `No matching ...` 文案；非零时禁止 no-match 文案；
- row 字段必须与 Stage 34 固定 allowlist/order一致，`safe_to_preview` 必须 bool；
- Reports status/reason 必须保持 `unavailable` / `request_context_required`。

consumer 无原始 filtered payload，因此不重新验证 request→task closure 或 row filter semantics；这些仍由 Stage 29/31/34 链路负责。

## 8. Non-ready withheld gate

blocked/validation_failed/error 时：

- representation status 必须 `withheld`；
- content/content_id 必须 null；
- identity 只能为 null 或 canonical hash；
- 不读取、渲染或复制任何 content；
- consumer 输出不复制上游 finding message，只给 value-safe rule id/action。

## 9. 输出 contract

固定字段：

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

source 仅包含：

```text
base_snapshot_id
scope_id
filter_id
view_id
content_id
```

固定 checks：

```text
document_shape
schema_version
display_status
lifecycle
guarantees
representation_metadata
content_identity
markdown_structure
escaping_invariants
view_coherence
```

stdout 最大 64 KiB，确定性 JSON；不输出 content、绝对路径、envelope、host payload 或上游 finding message。

## 10. Stage 37 TDD 验收矩阵

实现前 RED tests 至少覆盖：

1. valid request/task/AND ready display；
2. valid empty view；
3. valid blocked/validation_failed/error withheld mapping；
4. content hash mismatch、identity link mismatch；
5. malformed/non-UTF8/duplicate/non-object/oversized input；
6. unknown field、schema/display id、status/host/lifecycle/guarantee drift；
7. raw Markdown/HTML/link/backtick/pipe/control injection；
8. heading/section/field reorder、extra/missing text；
9. count/matched/no-match/filter/identity/report coherence drift；
10. deterministic bounded minimal output，content 不泄露；
11. stdin-only/no process/no file/no network/no persistence；
12. real Stage 34 display → consumer pipe；
13. Stage 18/20/22/24/27/29/31/34 compatibility regression。

## 11. 明确延期

Stage 36–38 不开放：

- consumer 自动启动 display/host/reader；
- arbitrary Markdown validation/rendering；
- Codex Desktop 专有插件/UI、HTML/browser；
- file/URL input、cache/export/clipboard/persistence；
- watch/poll/service/network/DB/auth；
- query/sort/page/lineage；
- approval resolve、candidate command、UI write 或真实 adapter execution。

## 12. Stage 36 结论

**Stage 36 — Filtered Snapshot Markdown Display Consumer Validation Gate 已通过并冻结。** Stage 37 只允许实现上述 stdin-only validator；不得形成第二条 display/reader 管线。

## 13. Stage 37 实现事实

Stage 37 按 TDD 新增：

- `tools/codex_desktop_filtered_snapshot_display_consumer.py`；
- `tests/test_codex_desktop_filtered_snapshot_display_consumer.py`。

实现保持标准库-only、stdin-only，固定输出：

```text
control-plane/filtered-snapshot-markdown-display-consumer-validation/v1
codex-desktop-filtered-snapshot-markdown-display-consumer/v1
```

冻结的十项检查为：

```text
document_shape
schema_version
display_status
lifecycle
guarantees
representation_metadata
content_identity
markdown_structure
escaping_invariants
view_coherence
```

实现只读取一份最大 64 KiB 的 strict UTF-8 JSON object，拒绝 duplicate key、未知字段、file/path/URL/payload-only/raw Markdown 和命令行参数。ready 时独立重算 Markdown UTF-8 content SHA-256，并以固定状态机解析 Stage 34 grammar、安全 ASCII JSON inline literal、identity/count/filter/empty-view/report coherence；non-ready 只接受 withheld contract。输出只保留 value-safe ids、checks、rule id 与 action，不复制 content 或上游 finding message。

## 14. Stage 37 验收证据

- RED：首个有效 display 用例因 Stage 37 工具不存在而按预期失败；
- 专用测试：16 项通过；
- Stage 18/20/22/24/27/29/31/34/37 相关回归：124 项通过；
- 全量测试：884 项通过；
- `python -m agent_runtime.cli doctor`：PASS；
- `python tools/public_scan.py`：OK；
- `python -m py_compile tools/codex_desktop_filtered_snapshot_display_consumer.py`：PASS；
- 真实 Stage 34 display → Stage 37 consumer 管道：ready 映射为 `pass/0`，missing-envelope 映射为 `blocked/2`，输出不包含 Markdown content。

最终冻结前必须重新运行全量测试、doctor、public scan、docs hook 与 Git diff checks；release note 只记录实际通过的证据。

## 15. Stage 38 里程碑冻结

Stage 36–37 已形成可独立引用的 display-result validation 能力包，冻结本地 annotated tag：

```text
v0.16.0-filtered-snapshot-display-consumer
```

该 tag 冻结时保持本地，后于 2026-07-16 按用户授权推送至 `origin`。它不扩大 Stage 34 display 的信任边界，不授予 representation render、UI、file/URL、service/network、persistence/export、write 或 adapter execution 权限。

## 16. 下一阶段条件入口

下一阶段为 **Stage 39 — Filtered Snapshot Markdown Display Consumer Host Integration Gate（条件启动）**。第一拍只允许设计 one-shot integration：

```text
fixed Stage 34 display stdout
  -> fixed Stage 37 consumer stdin validation
  -> validation-before-release host result
```

Stage 39 必须冻结固定 argv ownership、bounded stdout/stderr、timeout/cancel/no-retry、consumer pass 前不释放 content、identity cross-check、failure withheld、memory cleanup 与 no-side-effect；不得直接实现专有 Codex Desktop UI、HTML/browser、file/URL、live service、network/DB/auth、cache/export、write 或真实 adapter execution。

<!-- gate-status: passed-stage36 -->
<!-- implementation-status: completed-stage37 -->
<!-- milestone-status: frozen-stage38 -->

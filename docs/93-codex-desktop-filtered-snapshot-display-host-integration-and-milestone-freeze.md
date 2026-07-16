<!-- parents: archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md -->
<!-- relates: archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md, 89-codex-desktop-filtered-snapshot-consumer-implementation.md, 64-versioning-governance.md -->

# 93 — Codex Desktop Filtered Snapshot Display Host Integration and Milestone Freeze

> 状态：**Stage 39 design gate、Stage 40 实现与 Stage 41 milestone freeze 均已收口**
> 日期：2026-07-16
> 冻结里程碑：`v0.17.0-filtered-snapshot-display-host-integration`（本地 annotated tag，未 push）

## 1. 决策摘要

Stage 39 选择 one-shot、validation-before-release host，固定复用 Stage 34 display 与 Stage 37 consumer：

```text
显式 project/envelope/filter/markdown user action
  -> fixed Stage 34 display process
  -> complete display v1 stdout retained in memory
  -> fixed Stage 37 consumer process via stdin
  -> consumer pass/0 + five-id cross-check
  -> release validated Markdown representation
```

冻结 contract：

```text
control-plane/codex-desktop-filtered-snapshot-display-host/v1
codex-desktop-filtered-snapshot-display-host/v1
```

候选工具：

```text
tools/codex_desktop_filtered_snapshot_display_host.py
```

host 不导入 Stage 34/37 模块，不新增 reader、Markdown parser 或第二条投影管线。

## 2. 用户动作与输入边界

仅接受显式 CLI 参数：

- `--project-root`：默认 cwd，必须是项目根；
- `--envelope`：交给 Stage 34 的显式 project-relative envelope；host 自身只做 ASCII/长度/绝对路径与 `..` 前置拒绝，不读取 envelope；
- `--task-id` / `--request-id`：至少一个 canonical exact filter，同时提供时保持 AND；
- `--representation markdown`：唯一允许表示；
- `--timeout-seconds`：每个固定子进程默认 30 秒，最大 60 秒；
- `--json`：automation compatibility，输出始终为 JSON。

拒绝 duplicate selector、arbitrary argv、stdin input、file/URL input、raw Markdown、payload-only 与 descriptor argv。

## 3. 固定进程与 argv ownership

host 仅允许依次启动两个固定脚本：

1. `tools/codex_desktop_filtered_snapshot_display.py`；
2. `tools/codex_desktop_filtered_snapshot_display_consumer.py`。

Stage 34 argv 由 host 构造，包含 resolved project root、显式 envelope、canonical task/request filter、`--representation markdown`、相同 timeout 与 `--json`。Stage 37 argv 固定为 Python executable + consumer script，无其他参数；stdin 必须是 Stage 34 stdout 的 exact bytes。

使用最小环境白名单、`shell=False`、one-shot、sequential、no retry。不得执行 display document、consumer result 或 descriptor 中的任何 argv。

## 4. 有界 I/O 与生命周期

固定上限：

| 对象 | 上限 |
|:---|---:|
| Stage 34 stdout | 64 KiB |
| Stage 37 stdin | Stage 34 exact stdout，最大 64 KiB |
| Stage 37 stdout | 64 KiB |
| 每个 child stderr | 64 KiB |
| 最终 host JSON | 128 KiB |

生命周期：

```text
created
  -> displaying
  -> validating
  -> ready | blocked | validation_failed | error
  -> closed
```

超时、用户取消、start failure、oversized/non-UTF-8/invalid/duplicate-key/unknown-shape output 均 fail closed，不自动重试，不释放 content。child stdout/stderr 只在当前 one-shot 内存中保留；不写临时文件、cache、clipboard、ledger 或 artifact，结束后不进入返回对象。

## 5. Stage 34 display gate

host 必须先检查 Stage 34：

- process exit 只允许 `ready/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- strict UTF-8 single JSON object、duplicate-key rejection；
- exact display schema/id/top-level shape；
- source 固定 `project_root` 占位符；
- representation metadata 固定为 Markdown/UTF-8；
- non-ready 必须 withheld，content/content_id 为 null；
- ready 必须 content 为非空 string、五项 identity 为 canonical SHA-256；
- host 不自行解析 Markdown grammar，完整语义验证由 Stage 37 consumer 负责。

Stage 34 raw content 在 Stage 37 `pass/0` 前只能保留于进程内存，不得进入 host result。

## 6. Stage 37 consumer gate

consumer result 必须满足：

- exact validation schema 与 consumer id；
- exact top-level/source/checks/findings/guarantees/next_action shape；
- 10 项 checks 的 exact order、id 与状态；
- status/exit 映射：`pass/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- pass 时全部 checks 为 pass、findings empty、next action 为 `accept_markdown_display`；
- non-pass 不得伪装 pass；finding 只允许安全 rule id/severity/action/message shape，但 host 不复制 message；
- exact Stage 37 guarantees。

host 不相信 process exit 单独成立，也不相信 JSON status 单独成立；两者必须一致。

## 7. Validation-before-release 与 identity cross-check

仅当以下条件同时成立时返回 ready content：

1. Stage 34 `ready/0`；
2. Stage 37 `pass/0`；
3. consumer source 的 `base_snapshot_id`、`scope_id`、`filter_id`、`view_id`、`content_id` 与 Stage 34 representation 完全一致；
4. Stage 34 representation metadata/content shape 通过 host gate；
5. 最终 host JSON 不超过 128 KiB。

host 不重算 content hash或解析 Markdown；Stage 37 已独立完成这些验证。identity mismatch、consumer protocol drift 或 pass/exit mismatch 均为 host `error/1`，content withheld。

## 8. 输出 contract

固定字段：

```text
status
schema_version
host
source
lifecycle
display
consumer
representation
findings
guarantees
next_action
```

`display` 与 `consumer` 只输出 status、exit code 和安全 identity source；不复制 child findings/message、argv、stderr、absolute path 或 envelope。

ready representation：

```text
status=pass
type=markdown
media_type=text/markdown; charset=utf-8
encoding=utf-8
base_snapshot_id
scope_id
filter_id
view_id
content_id
content
```

non-ready representation 保持同 shape，但 `status=withheld`、`content_id/content=null`；可保留已验证 canonical base/scope/filter/view ids。

## 9. 状态与退出码

| 条件 | host status | exit |
|:---|:---|:---:|
| display ready + consumer pass + ids match | `ready` | 0 |
| valid display/consumer blocked | `blocked` | 2 |
| valid upstream validation_failed | `validation_failed` | 5 |
| process/protocol/identity/size/timeout/cancel/internal failure | `error` | 1 |

任何非 ready 结果都不得包含 content。

## 10. 固定 guarantees

Stage 40 host 必须声明并由测试精确冻结：

- explicit user action、one-shot、read-only；
- uses fixed Stage 34 display；
- validates with fixed Stage 37 consumer before release；
- identity cross-check；
- content withheld until pass；
- Markdown 不由 host render；
- no file/ledger/network/service/descriptor argv/candidate command/adapter；
- no retry、no persistence/export、bounded I/O。

## 11. Stage 40 TDD 验收矩阵

实现前 RED tests 至少覆盖：

1. fixed display argv 与 exact stdout → consumer stdin；
2. ready/pass 五项 identity cross-check 后释放 content；
3. task-only、request-only、AND 与合法空视图真实管道；
4. blocked/validation_failed/error mapping 与 withheld；
5. display/consumer status-exit mismatch；
6. display/consumer invalid UTF-8、JSON、duplicate key、non-object、unknown field/schema/id/guarantee/check drift；
7. identity/content_id mismatch；
8. child timeout/start failure/cancel/no retry；
9. stdout/stderr/final output bounds；
10. invalid root/envelope/filter/representation/timeout/duplicate args 在 spawn 前失败；
11. deterministic minimal output，不泄露 stderr、argv、path、envelope、child finding message 或未验证 content；
12. no file/ledger/network/service/persistence/export/adapter execution；
13. Stage 18/20/22/24/27/29/31/34/37 compatibility regression。

## 12. 明确延期

Stage 39–41 不开放：

- 专有 Codex Desktop 插件/API/UI；
- Markdown render、HTML/browser、auto-open、clipboard；
- file/URL/stdin arbitrary input；
- watch/poll/live refresh/service/network/DB/auth；
- cache/export/persistence；
- query/sort/page/lineage；
- approval resolve、candidate command、UI write 或真实 adapter execution。

## 13. Stage 39 结论

**Stage 39 — Filtered Snapshot Markdown Display Consumer Host Integration Gate 已通过并冻结。** Stage 40 只能按上述 contract 实现 one-shot host；不得绕过 Stage 37 consumer 或形成第二条 Markdown validation 管线。

## 14. Stage 40 实现事实

Stage 40 按 TDD 新增：

- `tools/codex_desktop_filtered_snapshot_display_host.py`；
- `tests/test_codex_desktop_filtered_snapshot_display_host.py`。

实现固定输出：

```text
control-plane/codex-desktop-filtered-snapshot-display-host/v1
codex-desktop-filtered-snapshot-display-host/v1
```

host 仅启动 fixed Stage 34 display 与 fixed Stage 37 consumer，使用 minimal environment、`shell=False`、sequential one-shot 与 no retry。Stage 34 stdout 在 64 KiB gate 后以 exact bytes 交给 Stage 37 stdin；只有 display `ready/0`、consumer `pass/0`、十项 checks 通过且 base/scope/filter/view/content 五项 identity 完全一致时才释放 Markdown content。

host 独立验证两份 wrapper 的 exact shape/schema/id/status/exit/lifecycle/guarantees/checks/next-action；不重算 content hash、不解析 Markdown，不复制 child findings/message、stderr、argv、absolute path 或 envelope。任何 process/protocol/identity/size/timeout/cancel failure 都返回 `error/1` 且 content withheld。

## 15. Stage 40 验收证据

- RED：40 个验收用例均因 Stage 40 工具不存在而按预期失败；
- 专用测试：40 项通过；
- Stage 18/20/22/29/31/34/37/40 相关回归：164 项通过；
- 全量测试：924 项通过；
- `python -m agent_runtime.cli doctor`：PASS；
- `python tools/public_scan.py`：OK；
- `python -m py_compile tools/codex_desktop_filtered_snapshot_display_host.py`：PASS；
- 真实 request-only、task-only、AND 与 empty-view 四条完整 CLI 管道通过；
- blocked/validation_failed/error、identity mismatch、protocol drift、timeout/cancel、bounded I/O 与 no-side-effect 均由测试冻结。

最终冻结前重新运行全量测试、doctor、public scan、docs hook 与 Git diff checks。

## 16. Stage 41 里程碑冻结

Stage 39–40 已形成可独立引用的 validated Markdown release host 能力包，冻结本地 annotated tag：

```text
v0.17.0-filtered-snapshot-display-host-integration
```

该 tag 不推送，等待用户后续指令。它不授予 Markdown render、专有 UI、HTML/browser、file/URL、service/network、persistence/export、write 或 adapter execution 权限。

## 17. 下一阶段条件入口

下一阶段为 **Stage 42 — Filtered Snapshot Validated Markdown Presentation Handoff Gate（条件启动）**。第一拍只允许审计一个具体、显式、只读的 presentation handoff 动作：

- 输入只能是 Stage 40 ready host result；
- 必须重新确认 source/content identity 与 ready/pass chain；
- 只允许把已验证 Markdown 交给明确的 stdout/host-task presentation boundary；
- 不默认新增 consumer-of-consumer、第二条 Markdown validation、HTML/browser renderer 或专有插件 API；
- 若不存在具体 presentation consumer 与用户动作，Stage 42 必须保持 design-only 或冻结不启动。

专有 UI、clipboard、auto-open、file export、live refresh/service/network/DB/auth、write 与真实 execution 继续 unavailable。

<!-- gate-status: passed-stage39 -->
<!-- implementation-status: completed-stage40 -->
<!-- milestone-status: frozen-stage41 -->

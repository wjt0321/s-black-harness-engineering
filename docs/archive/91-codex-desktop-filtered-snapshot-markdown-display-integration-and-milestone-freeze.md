<!-- parents: archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md -->
<!-- relates: 89-codex-desktop-filtered-snapshot-consumer-implementation.md, 64-versioning-governance.md -->

> 归档状态：2026-07-16 被 Stage 36 display consumer validation design gate 取代后移入 archive；v0.15.0 commit/tag 已推送至 `origin`。

# 91 — Codex Desktop Filtered Snapshot Markdown Display Integration 与里程碑冻结

> 状态：**Stage 33 design gate、Stage 34 实现与 Stage 35 milestone freeze 均已收口**
> 日期：2026-07-16
> 冻结里程碑：`v0.15.0-filtered-snapshot-display-integration`（annotated tag，已推送）

## 1. 决策摘要

Stage 33 选择 **Codex Desktop 可消费的确定性 Markdown representation** 作为第一个具体展示面，不接入未冻结的专有插件 API，也不打开 HTML/browser。冻结候选 contract：

```text
control-plane/codex-desktop-filtered-snapshot-display/v1
codex-desktop-filtered-snapshot-markdown-display/v1
```

固定数据流：

```text
用户显式选择 project root + envelope + exact filters
  -> fixed Stage 31 host argv
  -> strict host result validation
  -> safe field projection
  -> escaped deterministic Markdown content
  -> versioned display result
  -> closed
```

只有 Stage 31 host `ready` / exit 0 且 display wrapper 完成 shape、identity link 和 safe scalar 检查后，才生成 Markdown content。

## 2. 方案审计

### 2.1 采用：固定 host-owned display wrapper

优点：

- 只运行已冻结的 Stage 31 host，不直接运行 reader/consumer；
- 来源是固定本地子进程，不接受 arbitrary stdin 或文件；
- 可复用 host 的 validation-before-display 结论，同时对展示字段做第二层严格投影；
- 输出仍是一次性 JSON contract，Codex Desktop 或其他宿主只需渲染 `text/markdown` content；
- 无需专有 API、server、browser、cache 或文件写入。

### 2.2 拒绝：stdin-only generic presenter

任意 stdin 会允许外部伪造 host result，要求 presenter 重做完整 Stage 29/31 validation，扩大攻击面并形成平行 validator。Stage 34 不提供文件、URL 或 arbitrary JSON 输入。

### 2.3 拒绝：Codex Desktop 专有插件/UI

当前仓库没有已冻结的插件 SDK、生命周期、授权和版本兼容 contract。直接耦合专有 API 会越过现有 no-service/no-UI-write 边界，继续延期。

## 3. 输入与固定 argv

Stage 34 display wrapper 只接受：

- supported project root；
- Stage 31 host 可接受的 project-relative envelope；
- 至少一个 canonical exact task/request filter；
- `--representation markdown`；
- `0 < timeout <= 60`；
- `--json` 自动化兼容参数。

wrapper 只能构造：

```text
python tools/codex_desktop_filtered_snapshot_host.py ... --json
```

不得直接执行 Stage 27 reader、Stage 29 consumer、descriptor argv、candidate command 或 adapter。使用 argv array、`shell=False`、固定 cwd 与最小环境白名单。

## 4. Host result gate

输入上限为 1 MiB，strict UTF-8 JSON object，拒绝 duplicate key。必须验证：

- exact host schema/id/top-level shape；
- `source.project_root == project_root` sentinel；
- exact Stage 31 guarantees；
- lifecycle closed，status 与 child exit code一致；
- ready 时 reader/consumer pass、findings empty、representation pass；
- consumer source 与 representation base/scope/filter/view ids 完全一致；
- filtered payload schema、source/filter/summary/sections/view links；
- runs/approvals/artifacts/reports exact field allowlist 和 safe scalar types；
- counts、matched 与 section lengths/status 一致。

wrapper 不重算 Stage 27 view identity，不把展示检查描述为 base snapshot 或 ledger 真实性证明；真实性边界仍由 Stage 27/29/31 链路负责。

## 5. Markdown 安全投影

动态值不得作为 raw Markdown 拼接。统一使用 safe inline literal：

1. 只接受 allowlist 中的 string/bool/int/null；
2. 使用 ASCII JSON literal；
3. 将 backtick、pipe、`<`、`>`、`&` 转义为可见 unicode escape；
4. 消除真实 CR/LF/control character；
5. 包裹为 inline code span。

静态模板不包含 raw HTML、图片、链接、脚本、表单或可执行 URI。展示顺序固定：

1. overview / filter / identity；
2. runs；
3. approvals；
4. artifacts；
5. reports unavailable summary。

保持 host row order，不排序、不分页、不查询、不展开 lineage。合法空视图输出固定 no-match 文案，不视为 error。

## 6. 输出 contract

固定顶层字段：

```text
status
schema_version
display
source
lifecycle
host
representation
findings
guarantees
next_action
```

ready representation：

```text
status = pass
type = markdown
media_type = text/markdown; charset=utf-8
encoding = utf-8
content_id = sha256:<content bytes>
content = deterministic escaped Markdown
```

failure/blocked/validation_failed 时 `content_id/content` 为 null，不复制 host payload 或 finding message。最终 display JSON stdout 上限 64 KiB；超限 fail closed，不截断后伪装完整。

## 7. 状态、生命周期与退出码

```text
created
  -> loading
  -> projecting
  -> ready | blocked | validation_failed | error
  -> closed
```

| 条件 | display status | exit |
|:---|:---|:---:|
| valid host ready + safe projection | `ready` | 0 |
| host blocked / 2 | `blocked` | 2 |
| host validation_failed / 5 | `validation_failed` | 5 |
| timeout、spawn、protocol、shape、identity、projection/output error | `error` | 1 |

不自动 retry，不把 host 非 ready 状态升级为 ready。

## 8. Bounds 与取消

- host stdout：1 MiB；
- host stderr：64 KiB，不回显；
- display stdout：64 KiB；
- timeout：默认 30 秒、最大 60 秒；
- filter：128 bytes；
- envelope argv：512 bytes；
- 每次用户动作只启动一个前台 host child；timeout/cancel 后关闭，不 watch/poll/background。

## 9. Stage 34 TDD 验收矩阵

实现前 RED tests 至少覆盖：

1. fixed host argv、cwd、stdin none、最小环境；
2. valid request-only、task-only、AND display；
3. legal empty view；
4. deterministic content/content id；
5. Markdown/HTML/link/backtick/pipe/control-character injection escaping；
6. host blocked/validation_failed/error mapping，content withheld；
7. malformed/non-UTF8/duplicate/unknown-field/status-exit drift；
8. host/consumer/representation identity mismatch；
9. row unknown field/type/count/matched mismatch；
10. timeout/stdout/stderr/display-size bounds，无 retry；
11. invalid root/filter/representation 不 spawn；
12. no direct reader/consumer/network/file write/service；
13. real Stage 31 host → display smoke；
14. Stage 18/20/22/24/27/29/31 compatibility regression。

## 10. 明确延期

Stage 33–35 不开放：

- Codex Desktop 专有插件/API 或交互式 UI；
- HTML/browser、图片、外部链接、raw Markdown from input；
- live refresh、watch、poll、service、network、DB、auth/session；
- cache、persistence、clipboard/file export；
- query、sort/page、lineage expansion；
- UI controlled write、approval resolve、candidate command 或真实 adapter execution。

## 11. Stage 33 结论

**Stage 33 — Codex Desktop Filtered Snapshot Display Integration Gate 已通过并冻结。** Stage 34 只允许实现固定 Stage 31 host 到 escaped deterministic Markdown 的 one-shot projection。

## 12. Stage 34 实现事实

新增：

```text
tools/codex_desktop_filtered_snapshot_display.py
tests/test_codex_desktop_filtered_snapshot_display.py
```

工具只运行固定 `codex_desktop_filtered_snapshot_host.py --json`，不 import 或直接调用 reader/consumer。实现冻结：

- exact top-level/host schema/id/source/lifecycle/guarantees/status-exit gate；
- ready 时验证 reader/consumer pass、identity links、filtered payload、safe row allowlist、count/matched/status 与 exact filter semantics；
- non-ready 时 `content/content_id` 固定 withheld，不复制 host payload、stderr 或 finding message；
- 动态值统一转为 ASCII JSON inline literal，并对 Markdown/HTML/link/backtick/pipe/control characters 做可见转义；
- 固定 overview/filter/identity → runs → approvals → artifacts → reports 顺序；合法空视图输出固定 no-match 文案；
- Markdown `content_id` 为 content UTF-8 bytes 的 SHA-256；最终 JSON 超过 64 KiB 时 fail closed；
- fixed argv array、`shell=False`、minimal environment、one-shot、no retry。

## 13. Stage 34 验证证据

- RED：11 项专用测试最初因 display 工具不存在而全部预期失败；
- GREEN：11 项 Stage 34 专用测试通过；
- Stage 22/27/29/31/34 相关 78 项回归通过；
- `python -m pytest tests -q`：868 项通过；
- `python -m agent_runtime.cli doctor`：PASS；
- `python tools/public_scan.py`：OK；
- `python -m py_compile tools/codex_desktop_filtered_snapshot_display.py`：PASS；
- request-only、task-only、task+request AND、合法空视图真实 one-shot smoke 均 `ready/0`；missing envelope 真实 smoke 为 `blocked/2` 且 content withheld。

## 14. Stage 35 里程碑冻结

Stage 33–34 已形成独立、可引用的安全展示能力包，冻结本地 annotated tag：

```text
v0.15.0-filtered-snapshot-display-integration
```

本次里程碑不改变安全边界：不开放专有插件/UI、HTML/browser、service/network/DB/auth、cache/export、任意 query、写操作或真实 adapter execution。commit/tag 随后已按用户授权推送至 `origin`。

## 15. 下一阶段条件入口

下一阶段为 **Stage 36 — Filtered Snapshot Markdown Display Consumer Validation Gate（条件启动）**。第一拍只审计独立 consumer 对 display v1 wrapper、content/content-id、escaping invariant、empty-view 与 non-ready withheld 的验证边界；不得直接信任 arbitrary Markdown、重跑 reader/host、启动 UI/service 或持久化 content。

<!-- gate-status: passed -->
<!-- implementation-status: completed-stage34 -->
<!-- milestone-status: frozen-stage35 -->

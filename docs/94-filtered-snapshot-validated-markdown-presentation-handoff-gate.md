<!-- parents: 93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md -->
<!-- relates: archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md, archive/88-filtered-snapshot-host-consumer-validation-gate.md -->

# 94 — Filtered Snapshot Validated Markdown Presentation Handoff Gate

> 状态：**Stage 42 design-only gate 已收口；presentation implementation 未授权**
> 日期：2026-07-16
> 前置事实源：`docs/93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md`
> 稳定基线：`v0.17.0-filtered-snapshot-display-host-integration`（本地 tag，未 push）

## 1. 决策摘要

Stage 40 已能在 fixed Stage 34 display 与 Stage 37 consumer 均通过后释放一份有界、确定性、已独立验证的 Markdown content。Stage 42 审计的问题不是“Markdown 是否有效”，而是：**是否已经存在一个具体、显式、只读的 presentation consumer / 用户动作，足以冻结下一条 handoff contract。**

本轮用户要求继续推进到下一阶段里程碑，但没有指定 presentation consumer、目标宿主动作或输出去向。依据 Stage 41 停止线，Stage 42 结论为：

> **冻结 design-only presentation handoff gate；不新增 consumer-of-consumer、presentation tool、CLI、schema、renderer 或宿主专有 API。**

这不是回退 Stage 40 能力。`ready` host result 仍是唯一可进入 future presentation boundary 的候选输入；只是当前没有足够需求把它交给新的执行主体。

## 2. 方案审计

### 方案 A：design-only gate（采用）

只冻结 Stage 40 ready result 的前置证据、future handoff 的最小校验职责、明确启动条件与禁止项；新增 characterization contract test，但不实现 presentation process。

优点：遵守条件启动与 YAGNI，不复制 Markdown validation，不引入未经授权的宿主行为。缺点：本阶段不产生新的用户可见 presentation 命令。

### 方案 B：新增 stdout-only presenter（延期）

候选 presenter 可从 stdin 接受完整 Stage 40 result，重新确认 ready/pass chain 与 content identity 后只向 stdout 输出 Markdown。

该方案仍缺少明确 consumer：stdout 的接收者、展示动作、内容保留策略、取消语义和错误映射均未被指定。现在实现会把“可行 transport”误当成“已授权 presentation action”，因此延期。

### 方案 C：Codex Desktop UI / HTML / browser / clipboard / file export（拒绝）

这些方案会新增专有 API、renderer、持久化或外部副作用，明显超出 Stage 42 边界，不进入候选实现。

## 3. 唯一候选输入

future presentation handoff 只能接受完整 Stage 40 host result：

```text
schema_version = control-plane/codex-desktop-filtered-snapshot-display-host/v1
host = codex-desktop-filtered-snapshot-display-host/v1
status = ready
```

禁止接受：

- payload-only、representation-only 或 raw Markdown；
- Stage 34 display result；
- Stage 37 consumer result；
- file/path/URL/clipboard/browser state；
- descriptor argv、shell string 或 candidate command；
- 任意旧 schema、未知 field 或 duplicate-key JSON。

这样 future boundary 不会绕过 validation-before-release host，也不会形成一条平行的 Markdown 来源。

## 4. future handoff 的最小信任重确认

如果后续明确授权实现，presentation boundary 只能做以下 protocol / identity 重确认：

1. bounded strict UTF-8 single JSON object，拒绝 duplicate key 与 trailing non-whitespace；
2. exact Stage 40 schema、host id、top-level shape 与 source placeholder；
3. `status=ready`，lifecycle 精确 closed，phases 为 `created → displaying → validating → ready → closed`；
4. display 为 `ready/0`，consumer 为 `pass/0`；
5. representation 为 `pass/markdown/text/markdown; charset=utf-8/utf-8`；
6. base/scope/filter/view/content 五项 identity 在 display、consumer、representation 三处完全一致；
7. 对 UTF-8 content 重新计算 canonical SHA-256，并与 `content_id` 一致；
8. Stage 40 guarantees 精确匹配，尤其是 validation-before-release、withheld-before-pass、read-only、no persistence/export/network/service/write/adapter；
9. input/output/lifecycle 均有界，任何 mismatch 一律不呈现 content。

这不是第二条 Markdown validation：future boundary **不得**重新解析固定 Markdown grammar、重新验证 safe rows 或复制 Stage 37 的 10 项 checks。它只证明收到的是 Stage 40 已释放且在传输中未发生 identity/content drift 的完整结果。

## 5. presentation 动作启动条件

只有同时给出以下信息，才允许命名并启动下一 implementation stage：

- **consumer identity**：谁消费 Markdown；
- **explicit user action**：用户触发什么动作；
- **transport ownership**：stdin/stdout 或 host-task boundary 由谁创建、谁关闭；
- **presentation destination**：内容显示到哪里，且不得默认为 file/browser/clipboard；
- **retention policy**：是否仅 one-shot 内存展示，何时丢弃；
- **bounds**：输入、输出、stderr、timeout 与 cancel 上限；
- **failure mapping**：invalid/blocked/error 时如何 fail closed；
- **no-side-effect evidence**：不访问网络、不写文件/ledger、不持久化/export、不执行命令或 adapter。

“继续推进项目”“展示 Markdown”或“接入 Codex Desktop”这类泛化描述不足以替代上述具体 contract。

## 6. 输出与状态边界

Stage 42 本身不新增 runtime output schema。当前唯一稳定输出仍是 Stage 40 host v1 JSON。

future implementation 若获授权：

- 只能在完整重确认后把 exact Markdown content 交给指定 presentation boundary；
- 不得返回 child stderr、argv、absolute path、envelope、raw input 或上游 finding message；
- non-ready / protocol drift / identity mismatch / hash mismatch / oversized / timeout / cancel 必须 content withheld；
- 不得自动 retry，不得缓存或导出内容；
- 不得把 presentation success 解释为 approval、execution 或 ledger state 变化。

## 7. 前置契约证据

新增 `tests/test_validated_markdown_presentation_handoff_contract.py`，以真实 Stage 40 CLI stdout 冻结 future presentation candidate 的最低证据：

- exact ready wrapper、schema、host、source 与 closed lifecycle；
- display `ready/0`、consumer `pass/0` 与五项 identity 一致；
- Markdown representation metadata 与独立 content SHA-256 重算；
- validation-before-release / no-side-effect guarantees；
- non-ready content withheld；
- deterministic、128 KiB bounded 与不泄露 path/envelope/argv/stderr。

该测试是现有 Stage 40 行为的 characterization / prerequisite contract，不是 presentation consumer 实现，也不新增生产行为。

## 8. 明确延期

Stage 42 不开放：

- presentation consumer、consumer-of-consumer 或新 CLI；
- 第二条 Markdown grammar / safe-field validation；
- HTML renderer、browser、auto-open、clipboard、file export；
- arbitrary stdin/file/URL/raw Markdown；
- watch/poll/live refresh、service、network、DB、auth；
- cache、artifact、ledger、persistence/export；
- approval resolve、candidate command、UI write 或真实 adapter execution；
- 专有 Codex Desktop plugin/API/UI。

## 9. 验收矩阵

Stage 42 收口必须满足：

1. Stage 40 前置 contract test 通过；
2. Stage 40 host 与 Stage 37/34 相关回归保持通过；
3. 全量 pytest、doctor、public scan、docs hook 与 `git diff --check` 通过；
4. 仓库没有新增 presentation production tool、schema、CLI 或外部依赖；
5. 活跃文档数量不膨胀，旧 Stage 28 gate 完整归档且引用修复；
6. 不创建 tag、不 push。

## 10. Stage 42 结论

**Stage 42 — Filtered Snapshot Validated Markdown Presentation Handoff Gate 已按 design-only 方式收口。**

当前最准确的停止线是：

```text
Stage 40 ready host result
  -> [future explicit presentation boundary: not yet specified]
```

下一 implementation stage 不自动启动，也暂不分配 Stage 43 实现名称。只有用户明确给出具体 consumer 与 presentation action 后，才可在本 gate 内补齐 transport/status/bounds 并按 TDD 实现；否则继续保持 Stage 40 result 可审计、可手工查看但不由项目新增进程呈现。

<!-- gate-status: passed-stage42-design-only -->
<!-- implementation-status: unavailable-pending-concrete-consumer -->

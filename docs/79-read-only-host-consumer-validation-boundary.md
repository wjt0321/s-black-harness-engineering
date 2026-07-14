# 79 — Stage 18 Read-only Host Consumer Validation Boundary

> 状态：**第一拍已按 TDD 实现并收口**
> 前置事实源：`docs/78-control-panel-host-integration-boundary.md`、`docs/archive/release-notes/81-release-notes-stage17-control-panel-host-handoff.md`

## 1. 决策摘要

Stage 18 第一拍选择一个宿主无关的本地 reference consumer：

```text
tools/control_panel_handoff_consumer.py
```

它使用 Python 标准库，从 stdin 读取 `control-plane/control-panel-handoff/v1` descriptor，并向 stdout 输出确定性的结构化校验结果。它不导入 Control Panel producer 的 builder/dataclass，不读取 ledger、envelope、registry 或配置，也绝不执行 descriptor 中声明的 argv。

目标是验证：仅凭 Stage 17 已公开的 handoff contract，一个独立消费者能否安全判断 schema、identity、representation 与 boundary 是否可信。

## 2. 方案对比

### 方案 A — 独立 `tools/` reference consumer（采用）

优点：

- 与 producer 实现解耦，能发现真实 contract drift；
- 无 Codex Desktop / QwenPaw 专有依赖；
- 只需标准库，适合本地、CI 与未来宿主参考；
- 可以明确验证“不执行 argv”而不是默认信任 producer。

代价：

- 它是参考工具，不是长期宿主 API；
- 第一版不负责刷新、展示或调度 representation。

### 方案 B — 新增 `orchestration control-panel consume`

不采用：producer 与 consumer 会重新耦合在同一 CLI/package surface 中，降低独立契约验证价值。

### 方案 C — 直接实现 Codex Desktop 或 QwenPaw bridge

继续延期：尚未冻结专有宿主的输入、生命周期、错误处理和授权模型，过早接入会扩大边界。

## 3. 输入与生命周期

唯一输入是 stdin 中的一份 UTF-8 JSON document：

```bash
python -m agent_runtime.cli orchestration control-panel handoff --json | \
python tools/control_panel_handoff_consumer.py
```

第一版规则：

- 不接受任意文件路径、URL、socket、环境变量或 credential 参数；
- stdin 最大 1 MiB，超限在 JSON parse 前拒绝；
- 空输入、非 UTF-8、非法 JSON 与重复 object key 均结构化失败；
- 每次进程只消费一份 descriptor，完成后退出；
- 不启动 daemon、watch、polling、background process 或 server；
- stdout 只输出 validation result，stderr 仅保留 argparse/不可恢复启动错误；正常门禁失败仍输出 JSON。

## 4. 校验范围

Reference consumer 必须独立检查：

1. 顶层字段集合、字段类型与 `control-plane/control-panel-handoff/v1`。
2. `handoff_id`：移除自身后对 canonical JSON 做 SHA-256。
3. `render_id`：对 `{snapshot_id, renderer_version}` 做 canonical SHA-256。
4. snapshot/render media type、UTF-8 encoding 与 `working_directory=project_root`。
5. argv 是非空字符串数组；只作为 opaque data 校验，永不执行。
6. boundaries 必须保持 read-only，所有 write/network/service/command/adapter execution 标志必须为 false。
7. `scoped_unavailable` 是有限、结构化列表，不读取对应资源。
8. producer `status` 非 pass 时，consumer 返回 blocked，不把 error descriptor 伪装为可信 representation。

V1 使用严格字段集合。出现未知字段时返回 contract drift finding；未来扩展必须升级 schema/version，而不是静默接受。

## 5. 输出契约

实现 schema：

```text
control-plane/control-panel-host-consumer-validation/v1
```

固定顶层字段：

| 字段 | 语义 |
|:---|:---|
| `status` | `pass` / `blocked` / `validation_failed` / `error` |
| `schema_version` | consumer validation v1 |
| `consumer` | 固定 `local-reference-consumer/v1` |
| `source_handoff_id` | 仅在格式安全时返回 handoff id，否则为 `null` |
| `checks` | 按固定顺序输出各检查项及状态 |
| `findings` | consumer 自己生成的安全 finding，不复制原始 descriptor |
| `guarantees` | stdin-only、no-write、no-network、no-execution 等 |
| `next_action` | 结构化下一步 |

不新增 validation content hash；第一拍的目标是契约校验，不建立新的持久 identity。

## 6. 状态与退出码

沿用项目退出码语义，但 consumer 保持标准库独立实现：

- `pass` → `0`；
- 不安全 boundary、producer 非 pass、unsupported schema → `blocked` / `2`；
- malformed JSON、重复 key、shape/identity mismatch → `validation_failed` / `5`；
- stdin 读取或不可恢复内部错误 → `error` / `1`。

所有 finding 只包含 rule id、固定安全消息和可选字段位置，不回显原始 descriptor、secret、argv 内容或绝对路径。多个问题按固定检查顺序输出，结果必须确定性。

## 7. 组件边界

实现保持单文件、小函数：

- bounded UTF-8 stdin reader；
- duplicate-key rejecting JSON loader；
- canonical SHA-256 helper；
- strict shape/type validators；
- ordered check aggregator；
- deterministic result renderer；
- `main()` 只做 I/O 和 exit code 映射。

不得从 `agent_runtime.orchestration_control_panel`、`agent_runtime.cli` 或 producer tests 导入实现。测试可以使用 producer 生成合法 fixture，但 consumer 校验逻辑必须独立。

## 8. TDD 验收矩阵

至少覆盖：

- 合法无 envelope / 合法 envelope；
- byte-equivalent determinism；
- 空输入、超限、非 UTF-8、非法 JSON、duplicate key；
- unknown schema / unknown field / missing field / wrong type；
- handoff id mismatch / render id mismatch；
- unsafe boundary；
- argv 不是数组、数组元素不是字符串；
- producer error descriptor；
- sentinel secret、绝对路径与原始 argv 不出现在 consumer finding/output；
- no file write、no network、no subprocess/argv execution；
- CLI exit code 与 JSON status 一致。

## 9. 明确延期

- 自动调用 descriptor argv；
- 自动读取 snapshot 或 HTML representation；
- 文件输入、URL、HTTP、WebSocket、watch/polling；
- browser open、UI 展示或刷新；
- Codex Desktop / QwenPaw 专有 bridge；
- controlled artifact export；
- auth/session/DB；
- 任何真实 adapter 或外部命令执行。

## 10. 第一拍实施顺序

1. 在 `tests/test_control_panel_handoff_consumer.py` 写最小失败测试并确认 RED。
2. 新增标准库-only `tools/control_panel_handoff_consumer.py`，逐项完成 RED/GREEN。
3. 增加真实 producer descriptor 兼容测试，但不让 consumer 导入 producer 实现。
4. 更新 CLI 使用文档、stage digest、roadmap、README、AGENTS 与 handoff。
5. 跑全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、pre-commit 与 diff check。
6. 通过后新增 Stage 18 release notes；不自动创建 tag，不 push。


## 11. 实现与收口结果

Stage 18 第一拍已完成：

- 新增 `tools/control_panel_handoff_consumer.py`，仅使用 Python 标准库，且不导入 `agent_runtime`；
- 固定检查顺序为 `document_shape`、`schema_version`、`producer_status`、`handoff_identity`、`render_identity`、`representations`、`argv`、`boundaries`；
- stdin 读取上限为 1 MiB，并在解析前拒绝空输入、非 UTF-8 与超限输入；JSON loader 拒绝重复 object key；
- project-relative source 同时按 POSIX 与 Windows 语义检查，拒绝绝对路径、盘符路径、Windows 根相对路径与 `..` 穿越；
- 输出固定为 `control-plane/control-panel-host-consumer-validation/v1`，状态与退出码遵守第 6 节；
- consumer 不读取 snapshot/HTML representation、不执行 argv、不访问网络、不启动服务、不写文件或 ledger；
- 测试覆盖合法 descriptor、producer error、shape/schema/identity/representation/argv/boundary drift、输入门禁、确定性、脱敏和 no-side-effect。

真实 stdio 管道已通过：

```bash
python -m agent_runtime.cli orchestration control-panel handoff \
  --envelope adapters/execution-envelope.examples.json \
  --json | python tools/control_panel_handoff_consumer.py
```

收口事实源：`docs/archive/release-notes/82-release-notes-stage18-read-only-host-consumer-validation.md`。本阶段不创建 tag，不 push。

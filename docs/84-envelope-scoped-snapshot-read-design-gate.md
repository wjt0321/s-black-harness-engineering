<!-- parents: 83-codex-desktop-snapshot-json-reader-implementation.md -->
<!-- relates: 82-read-only-representation-read-design-gate.md, 81-codex-desktop-read-only-adapter-implementation.md, 79-read-only-host-consumer-validation-boundary.md -->

# 84 — Envelope-scoped Snapshot Read Design Gate

> Stage 23 条件启动设计门。本文冻结“是否允许把现有 envelope-scoped runs / approvals / artifacts read model 接入 Codex Desktop snapshot reader”的边界；不等同于已实现 `--envelope`，也不开放任何执行能力。

## 1. 启动判定

用户已明确要求继续推进 Stage 23，因此本设计门启动。当前请求没有指定某一个 envelope 文件、具体 request/task 消费者或 UI 事件来源，所以本轮只冻结设计门与验收条件，不直接修改 Stage 22 reader 的命令面。

### 当前结论

- Stage 22 `snapshot-json` reader 继续只读 project-scoped snapshot；不接受 `--envelope`。
- 无 envelope 时，Control Panel 的 `runs`、`approvals`、`artifacts` 继续返回 `status=unavailable`、`reason=envelope_required`。
- `reports` 继续保持 request-scoped，不因 envelope 存在而伪装成持久 collection。
- Stage 23 的目标是复用既有 `list_runs` / `list_approvals` / `list_artifacts` 与 Stage 17 → Stage 18 → Stage 22 identity 链路，不创建平行读取管线。

## 2. 目标与非目标

### 目标

在未来满足全部进入条件后，允许用户显式请求一个 project-relative envelope-scoped snapshot，并在同一个有界 JSON representation 中投影：

1. envelope 内的 run summary；
2. envelope 内的 approval summary；
3. envelope 内的 artifact summary；
4. 对应的 scope reference、schema/source/guarantees 与 identity/hash 校验结果。

### 非目标

- 不执行 descriptor argv、candidate command 或真实 adapter；
- 不打开浏览器、不读取 HTML、不启动 service、不访问网络；
- 不写 envelope、ledger、artifact export 或任何持久化文件；
- 不接受 URL、socket、任意文件系统路径或由 UI 事件推导出的路径；
- 不建立独立 Run / Approval / Artifact collection；
- 不把 `report generate` 变成 collection read；
- 不通过“设计门已启动”推导“功能已可用”。

## 3. 现有能力与复用边界

现有 Control Panel 已有如下只读能力：

- `build_control_panel_snapshot(root, envelope_file=...)` 可以把 envelope-scoped sections 投影为 snapshot；
- `build_control_panel_handoff(root, envelope_file=...)` 可以把 project-relative envelope reference 放入 descriptor；
- envelope read models 已复用 `validate_envelope_file` 做 schema 与 consistency 校验；
- Stage 18 reference consumer 已校验 handoff schema、source identity、representation metadata、argv shape 与 boundary；
- Stage 22 reader 已校验 handoff identity、snapshot schema/source/guarantees、snapshot identity 与 canonical hash。

Stage 23 只能在这些既有能力之上增加“显式 scope 输入与 scope identity 关联”，不能让 reader 消费 descriptor 中的任意 argv。

## 4. 拟冻结的输入契约

### 4.1 用户动作

未来实现必须同时要求：

```text
--representation snapshot-json
--envelope <project-relative-path>
```

约束：

- `--representation` 仍然必填；没有默认 representation；
- `--envelope` 只接受用户直接提供的 project-relative path；
- 不从 handoff descriptor、snapshot payload、HTML、UI event 或环境变量推导 envelope path；
- 未提供 envelope 时保持现有 `envelope_required` / unavailable，不自动选择样例或最近文件；
- `--envelope` 不能改变固定三段生命周期：handoff producer → reference consumer → snapshot producer。

### 4.2 project-relative path allowlist

v1 候选 allowlist 冻结为：

- `adapters/` 下的 `.json` envelope 文件（包括现有 `execution-envelope.examples.json`）；
- `drafts/runtime/` 下以 `.envelope.json` 结尾的受控 draft 文件。

以下输入必须拒绝：

- Windows drive path、UNC path、Unix absolute path；
- 含 `..`、空路径、根目录自身或规范化后越过 project root 的路径；
- `tasks/`、`.git/`、`.env`、credential/key/certificate 文件及其他 allowlist 外路径；
- 解析后位于 project root 外的 symlink；
- 非 `.json`、目录、特殊文件、不可读文件或不存在的文件。

展示与比较一律使用 root-relative、`/` 分隔的 normalized path；结果不得回显 project root 的绝对路径。

### 4.3 文件与内容门禁

在进入 snapshot producer 前，reader 必须先完成：

1. `stat` / byte-size 检查，输入上限为 1 MiB；
2. strict UTF-8 解码；
3. duplicate-key 拒绝；
4. JSON object shape 校验；
5. 既有 envelope schema + cross-artifact consistency 校验；
6. secret scan 只输出 rule id、位置和提示，不回显匹配原文；
7. 仅向下游传递已验证的 scope reference，不传递 raw payload、`input`、`raw_ref` 或未脱敏 evidence 内容。

任何一步失败都不得启动 snapshot producer。

## 5. Scope identity 设计

Envelope-scoped read 不能只凭一个 path 字符串建立信任。未来 v2 representation 必须关联三类 identity：

```text
handoff_id
consumer source_handoff_id
snapshot_id
```

并额外携带一个不暴露绝对路径的 scope identity：

```text
scope_id = sha256(canonical_json({
  "relative_envelope": normalized_project_relative_path,
  "envelope_content_id": sha256(validated_envelope_bytes)
}))
```

要求：

- handoff 的 `source.envelope_file`、consumer 的 `source_envelope_file`、snapshot 的 `source.envelope_file` 必须完全一致；
- handoff、consumer、snapshot 的 `scope_id` 必须完全一致；
- `snapshot_id` 必须在 reader 内对完整 snapshot payload 重新计算；
- 任意 identity 或 scope mismatch 都是 `validation_failed`，不得降级为 `ready`；
- 输出只保留 normalized relative path 与 content/scope id，不保留绝对路径、raw envelope bytes 或 descriptor argv。

由于新增 scope identity 会改变 representation contract，不能偷偷复用 Stage 22 `v1` 并赋予新语义；实现时应新增明确的版本化 schema/reader id。

## 6. 状态与生命周期

| 情况 | 预期状态 | 是否启动 snapshot producer |
|:---|:---|:---:|
| 未选择 `snapshot-json` | `blocked` | 否 |
| 未提供 envelope | 维持现有 snapshot；scoped sections 为 `unavailable/envelope_required` | 是（仅 project-scoped snapshot） |
| path 不在 allowlist / 越界 / 含 `..` | `validation_failed` | 否 |
| 文件不存在或不可读 | `error` | 否 |
| 文件超限、非 UTF-8、重复 key、secret scan 命中 | `validation_failed` | 否 |
| envelope schema/consistency 失败 | `validation_failed` | 否 |
| handoff / consumer / snapshot identity 不一致 | `validation_failed` | 否 |
| 全部校验通过 | `ready` | 是（固定 snapshot producer） |

生命周期仍为一次性：`created → scoping → producing → validating → reading → ready/closed`。禁止 retry、fallback、后台刷新和长期驻留。

## 7. 输出与脱敏

未来 scoped representation 只允许输出既有 read models 的安全摘要：

- run：request/task/adapter/operation/mode/status 等摘要；
- approval：approval/request/status/scope 摘要；
- artifact：artifact id/type/request/producer/timestamp/summary/safe metadata；
- findings：rule id、severity、action、value-free message；
- source：`relative_envelope`、`envelope_content_id`、`scope_id`。

禁止输出：

- adapter request 的 `input`、payload refs、raw refs；
- response raw content、完整 evidence description 或任意 secret match；
- project root、绝对文件路径、环境变量、descriptor 原文、argv；
- 任何可被解释为“已执行”的字段。

## 8. 进入 Stage 23 实现的必要条件

实现前必须补齐并由测试冻结：

1. 一个明确的用户消费者场景：需要哪些 sections，是否需要特定 task/request filter；
2. 一个明确的 envelope 来源与生命周期：样例、draft，还是用户提供的 project-local 文件；
3. `--envelope` 的 CLI / reader schema / reader id 版本号；
4. allowlist、path normalization、symlink、大小、UTF-8、duplicate-key、secret scan 的逐项测试；
5. handoff → consumer → snapshot 的 scope identity 传递与 mismatch 测试；
6. no-write/no-network/no-service/no-execute 回归证据；
7. full pytest、doctor、public scan、controlled-write regression 与 docs hook 证据。

在这些条件未全部满足前，不把 `--envelope` 加入 Stage 22 reader，不把 handoff 中已有的 envelope argv 当作可执行授权。

## 9. 当前验收结论

本轮结论为：**Stage 23 design gate 已启动，设计边界已冻结；Envelope-scoped Snapshot Read Implementation 尚未启动。**

保留的安全基线：

- `snapshot-json` 仍需显式选择；
- reader 不接受 `--envelope`；
- descriptor argv 不被执行；
- 无 envelope 时 runs/approvals/artifacts honest unavailable；
- no-write、no-network、no-service、no-adapter-execution 保持不变。

<!-- gate-status: started-not-implementation -->

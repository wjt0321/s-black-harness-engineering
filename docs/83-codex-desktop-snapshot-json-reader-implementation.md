<!-- parents: 82-read-only-representation-read-design-gate.md, 81-codex-desktop-read-only-adapter-implementation.md -->
<!-- relates: 79-read-only-host-consumer-validation-boundary.md, 78-control-panel-host-integration-boundary.md -->

# 83 — Codex Desktop Snapshot JSON Reader Implementation

> 状态：**Stage 22 已按 TDD 实现并收口**
> 日期：2026-07-15
> 前置事实源：`docs/82-read-only-representation-read-design-gate.md`

## 1. 真实消费者与用户动作

Stage 22 的首个真实消费者固定为 **Codex Desktop 本地任务进程**。用户动作固定为显式运行 snapshot JSON reader，并且必须显式选择：

```text
--representation snapshot-json
```

v1 不提供默认 representation，不支持 HTML、浏览器打开、文件 export、URL、socket 或任意路径输入。调用结束后只向 stdout 返回一个有界、版本化 JSON 对象。

## 2. 固定读取链路

```text
explicit snapshot-json action
  -> fixed handoff producer
  -> Stage 18 reference consumer validation
  -> fixed snapshot producer
  -> identity / schema / hash validation
  -> bounded in-memory JSON result
```

reader 不执行 descriptor 中的 `snapshot.argv`。descriptor argv 仍是 opaque metadata；实际 snapshot 命令由 reader 自身的固定 allowlist 常量定义。

## 3. v1 固定命令

handoff producer 与 consumer 继续复用 Stage 20 固定 argv。新增的 snapshot producer 只允许：

```text
python -m agent_runtime.cli orchestration control-panel snapshot --json
```

- `shell=False`；
- cwd 固定为已校验 project root；
- 使用 Stage 20 最小环境白名单，并固定 `PYTHONDONTWRITEBYTECODE=1` 禁止 bytecode cache 写入；
- 每个子进程默认 30 秒、最大 60 秒；
- stdout/stderr 各自最大 1 MiB；
- 不自动重试。

v1 不接受 envelope 参数。envelope-scoped sections 诚实保持 unavailable。

## 4. 输出与 identity

输出 schema 固定为：

```text
control-plane/codex-desktop-snapshot-read/v1
```

`ready` 之前必须同时满足：

1. handoff consumer 返回 `pass`；
2. handoff descriptor 可按严格 JSON object 解析；
3. snapshot 输出为严格、无 duplicate key 的 UTF-8 JSON object；
4. snapshot schema 为 `control-plane/control-panel-snapshot/v1`；
5. snapshot status 为 `pass`；
6. snapshot id 是安全的 `sha256:<64 hex>`；
7. snapshot id 等于 handoff 声明的 snapshot id；
8. 移除 `snapshot_id` 后重新 canonical hash，结果仍等于 snapshot id；
9. snapshot source 与 handoff source 一致；
10. snapshot guarantees 继续证明 no-write、no-network、no-service、no-command、no-adapter-execution。

输出可以包含已验证 snapshot payload，但不得包含绝对 project root、raw stderr、handoff descriptor、descriptor argv 或环境变量。

## 5. 状态与退出码

- `ready` → `0`
- `blocked` → `2`
- `validation_failed` → `5`
- `error` → `1`

handoff 未通过时绝不启动 snapshot producer。snapshot identity/schema/hash/source/guarantee 任一漂移都返回 `validation_failed` 或 `error`，不回显原始输入。

## 6. 安全保证

v1 必须声明并用测试证明：

- 用户显式选择 `snapshot-json`；
- one-shot；
- read-only；
- reads snapshot representation；
- 不读取 HTML；
- 不执行 descriptor argv；
- 不写文件、ledger、draft 或 artifact；
- 不访问网络；
- 不启动 service/background process；
- 不执行真实 adapter；
- 不自动重试；
- 输出有界且确定性。

## 7. TDD 验收矩阵

至少覆盖：

- fixed producer / consumer / snapshot argv；
- descriptor argv sentinel 不执行；
- 显式 representation 选择；
- handoff blocked / validation_failed 时 snapshot 不启动；
- snapshot schema、status、identity、canonical hash、source 与 guarantees 漂移；
- malformed / duplicate JSON、非 UTF-8、输出过大与 timeout；
- 非 project root 不启动子进程；
- determinism、绝对路径不回显和 no-write；
- 真实 Windows 本地三段 stdio smoke。

## 8. 明确延期

Stage 22 v1 不实现：HTML reader、浏览器展示、临时文件、controlled export、refresh/polling、live server、API/auth/session、DB、网络访问、UI action bridge 或真实 external adapter execution。


## 9. 实际实现

新增：

- `tools/codex_desktop_snapshot_json_reader.py`
- `tests/test_codex_desktop_snapshot_json_reader.py`

reader 输出 `control-plane/codex-desktop-snapshot-read/v1`，固定执行三段只读链路：handoff producer、Stage 18 consumer、snapshot producer。只有 consumer `pass` 后才进入 snapshot read；输出前独立校验 schema、source、guarantees、descriptor identity 与 canonical content hash。

显式调用：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --timeout-seconds 30 \
  --json
```

真实本地 smoke 返回 `ready`，lifecycle 为：

```text
created -> producing -> validating -> reading -> ready -> closed
```

## 10. Stage 22 验收结论

- 已按 TDD 先确认 9 个测试因 reader 模块不存在而失败；
- 已实现用户显式 `snapshot-json` 选择和固定三段 argv；
- descriptor argv sentinel 不执行；
- 已校验 snapshot strict JSON、UTF-8、duplicate key、1 MiB 上限、schema、source、guarantees、identity 与 canonical hash；
- handoff blocked / validation_failed 时不启动 snapshot producer；
- timeout、非 project root、malformed output 与协议漂移安全失败，不自动重试；
- 输出确定性、无绝对 project root，不写文件、不访问网络、不启动 service、不执行 candidate command 或真实 adapter；
- 已通过真实 Windows stdio smoke、全量测试与仓库安全门禁。

下一阶段为 **Stage 23 — Envelope-scoped Snapshot Read Design Gate（条件启动）**。v1 不接受 envelope；只有明确用户需要 run/approval/artifact scoped representation，并冻结 project-relative path、授权和 no-write 边界后才启动。HTML、浏览器和 export 继续延期。

## 11. Post-close 文档沉淀

Stage 22 收口后，`docs/` 根目录达到 51 个 Markdown 文件。按 `docs/MAINTENANCE.md` 的 SHOULD 归档规则完成无损整理：

- 完整移动 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 到 `docs/archive/68-orchestration-foundation-milestone-freeze-checklist.md`；
- 完整移动 `docs/69-orchestration-foundation-freeze-execution-plan.md` 到 `docs/archive/69-orchestration-foundation-freeze-execution-plan.md`；
- 两份文档均属于已完成的 `v0.12.0-orchestration-foundation` 历史冻结记录，当前冻结事实已由 `docs/77-read-only-control-plane-milestone-freeze.md` 取代；
- 文档正文与历史命令示例全部保留，没有删除独特约束、证据或操作记录；
- README、中英文入口、roadmap、index、历史 handoff 与 progress 中的当前路径引用已同步；同时修复 55/57/59/61/65/67/71 release notes 的既有归档路径；
- 活跃根目录 Markdown 数量从 51 降至 49，低于维护提示阈值 50。

Stage 23 的进入条件保持不变：没有明确 envelope-scoped consumer 需求时，不新增 `--envelope`。

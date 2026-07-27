# 133 — Stage 84 Bounded Atomic Snapshot Reader Implementation

> 状态：已实现并验证；仅授权固定 snapshot 的只读 inspection，不授权 producer、probe、ACP 连接、session 或 dispatch。

## 1. 目标与结论

Stage 84 将 Stage 83 冻结的 design contract 落地为一个 bounded、deterministic、fail-closed reader。它只读取：

```text
.runtime/external-agent-status/omp-acp.v1.json
```

实现入口：

- Python：`agent_runtime.orchestration_external_agent_live_status.inspect_external_agent_live_status(...)`
- CLI：`python -m agent_runtime.cli orchestration external-agent status inspect ...`
- reviewed read binding：`adapters/external-agent-live-status-binding.json`
- normalized evidence schema：`adapters/external-agent-live-status-evidence.schema.json`

Stage 84 没有创建 production snapshot。仓库中的 snapshot 仍只是 schema fixture；没有 producer、主动 probe、外部 CLI process、ACP handshake、session mapping、后台刷新、ledger/audit 写入或第三个真实 operation。

## 2. 固定输入与无 override 边界

reader 的 production path、最大尺寸、TTL、producer identity 和 target identity 来自已跟踪的 reviewed read binding：

- path：`.runtime/external-agent-status/omp-acp.v1.json`；
- max bytes：65,536；
- TTL：15 秒；
- target：`omp-pi-acp` / `omp-acp` / `omp-pi` / `1.0.0`；
- transport：`qwenpaw-acp-runner-omp` / `acp` / `acp/v1`；
- producer：`qwenpaw-acp-status-exporter` / `design-unobserved` / 固定 binding id。

CLI 不接受 snapshot path、TTL、adapter id、producer、transport、cwd、env 或 argv override。唯一业务输入是：

- required `--evaluated-at`：显式、带时区的评估时间；
- optional `--expected-after-generation`：非负整数，用于由调用方显式检测 generation 未前进；reader 自身不写 replay state。

## 3. 文件安全读取

固定 snapshot 的读取顺序是：

1. 将固定相对路径绑定到 project root；
2. 对 parent components 执行 lstat-first 检查；
3. 拒绝 symlink、Windows reparse point、hardlink、目录和非普通文件；
4. 在读取前检查 64 KiB 上限；
5. 打开 descriptor 后比较 path stat 与 descriptor identity；
6. 最多读取 64 KiB + 1 byte；
7. 比较读取前、descriptor 读取后和 path 读取后的 identity、size、mtime；
8. 只接受 strict UTF-8、顶层 object、无 duplicate key、无 non-finite number 的 JSON。

任何异常都转为 stable failure code 和固定中文安全提示，不回显文件内容、外部错误、路径细节、session identity 或 producer 内部信息。

## 4. Schema、content identity 与 binding

reader 校验：

- reviewed binding、binding schema、snapshot schema、evidence schema 与 Stage 82 GUI schema 的 canonical SHA-256 必须与代码冻结值一致；
- snapshot schema draft 2020-12；
- `complete=true`；
- `snapshot_id` 等于移除 `snapshot_id` 后 canonical JSON 的 SHA-256；
- producer object 与 reviewed binding 完全相等；
- target object 与 reviewed binding 完全相等；
- observation/evaluation 时间都带时区；
- observation 不得晚于 evaluation；
- expiry 固定为 observation + 15 秒；
- caller 提供 previous generation 时，新 generation 必须严格更大。

read binding 只授权内容校验和只读 projection。它明确保持：

```text
producer_or_probe_authorized = false
dispatch_authorized = false
```

## 5. Normalized evidence

有效读取会生成 `external-agent-live-status-evidence/v1`。`evidence_id` 使用与 snapshot 相同的 canonical JSON SHA-256 规则。固定安全字段包括：

```text
session_binding = null
event_cursor = null
sufficient_for_dispatch = false
execution_authorized = false
stable_read = true
```

状态规则：

| 条件 | observation | readiness | CLI exit |
|:---|:---|:---|:---|
| runner listed，fresh，无 open session | `observed` | `unknown` | 0 |
| runner missing/unknown | `unavailable` | `unknown` | 0 |
| TTL expired | `stale` | `stale` | 0 |
| generation 未前进 | `stale` | `stale` | 0 |
| future/binding/open-session/file/schema failure | `blocked` | `blocked` | 2 |

runner listed 永不映射为 ready。open session 没有 Harness `run_id + attempt_id` mapping 时仍为 blocked，且 GUI `session` 保持 `null`。

## 6. Stage 82 GUI projection

reader 输出单个符合 `external-agent-live-read-model` agent item schema 的 `gui_projection`：

| observation | Agent status | readiness | blocked reason |
|:---|:---|:---|:---|
| `observed` | `unknown` | `unknown` | `null` |
| `unavailable` | `disconnected` | `unknown` | `transport_unavailable` |
| `stale` | `stale` | `stale` | `readiness_expired` |
| `blocked` | `blocked` | `blocked` | `readiness_binding_drift` |

projection 在释放前再次通过 Stage 82 schema 校验；失败固定返回 `status_projection_invalid`，不会释放不合约的投影。

## 7. Stable failure code

Stage 84 实现并测试了 Stage 83 failure matrix：

- `status_source_missing`
- `status_source_not_regular`
- `status_source_indirection_blocked`
- `status_source_too_large`
- `status_source_unreadable`
- `status_source_schema_invalid`
- `status_snapshot_incomplete`
- `status_snapshot_replayed`
- `status_observation_from_future`
- `status_observation_expired`
- `status_identity_binding_mismatch`
- `status_producer_binding_missing`
- `status_producer_binding_drift`
- `status_target_not_observed`
- `status_unbound_session_observed`
- `status_projection_invalid`

其中 unavailable/stale 是成功生成的非授权 observation，因此 CLI exit 0；blocked 为 exit 2。

## 8. CLI

JSON：

```bash
python -m agent_runtime.cli orchestration external-agent status inspect \
  --evaluated-at 2026-07-27T08:00:05Z \
  --json
```

显式 replay check：

```bash
python -m agent_runtime.cli orchestration external-agent status inspect \
  --evaluated-at 2026-07-27T08:00:05Z \
  --expected-after-generation 7 \
  --json
```

在没有 production snapshot 的当前仓库中，命令会稳定返回 `status_source_missing` 与 exit 2。这不是 producer 或 Agent 不可用的主动探测结论，只表示固定 observation 文件不存在。

human output 默认简体中文。JSON 输出包含 schema version、observation status、固定 source、guarantees、可选 evidence、GUI projection、findings 和安全 next action。

## 9. 测试与无副作用证明

专项测试覆盖：

- binding/evidence schema 与 canonical digest；
- valid observed projection；
- missing、directory、symlink（平台允许时）、reparse、hardlink；
- oversize、invalid UTF-8、invalid/duplicate-key JSON；
- incomplete、schema/content digest drift；
- stable-stat drift；
- future、expiry、generation replay；
- producer/target drift；
- runner missing/unknown；
- unbound open session；
- projection schema failure；
- CLI fixed inputs、override rejection、中文 human output；
- orchestration discovery contract。

测试只使用仓库 fixture 与 pytest 临时目录，不写 production `.runtime`，不调用 Agent、不启动 producer/process、不连接 ACP、不创建 session、不发送 prompt、不调用模型、不读取凭据、不访问网络、不写 ledger/audit。

## 10. Stage 84 停止线

Stage 84 到此停止：

- 不实现 snapshot producer；
- 不调用 `qwenpaw`、`omp`、`pi` 或其他外部 CLI；
- 不执行 ACP handshake 或 runner list；
- 不创建、认领或关闭外部 session；
- 不实现 run/attempt session mapping；
- 不增加后台 poll/refresh 服务；
- 不将 evidence 绑定为 dispatch authority；
- 不新增第三个真实 operation；
- 不写 ledger、audit 或 production snapshot。

## 11. 下一阶段入口

下一候选是 **Stage 85：external Agent status producer/probe design gate**。该阶段只能比较 producer 获取 observation 的方案、进程/连接/凭据/网络副作用、atomic publication、trust binding、lease、audit、回收和测试边界；在独立设计与再次授权前，不得实现 producer 或主动 probe。

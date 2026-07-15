<!-- parents: archive/80-codex-desktop-read-only-adapter-design-gate.md -->
<!-- relates: 79-read-only-host-consumer-validation-boundary.md, 78-control-panel-host-integration-boundary.md -->

# 81 — Codex Desktop Read-only Adapter Implementation

> 状态：**Stage 20 已实现并收口**
> 日期：2026-07-15
> 设计事实源：`docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`

## 1. 实现摘要

Stage 20 将 Stage 19 冻结的 host contract 落地为一个标准库-only、一次性、本地只读 adapter：

```text
tools/codex_desktop_read_only_adapter.py
```

调用入口：

```bash
python tools/codex_desktop_read_only_adapter.py \
  --project-root . \
  --timeout-seconds 30 \
  --json
```

adapter 只执行两条固定 argv：

1. `python -m agent_runtime.cli orchestration control-panel handoff --json`
2. `python tools/control_panel_handoff_consumer.py`

第二条命令只接收第一条命令的 stdout。adapter 永远不读取或执行 descriptor 中声明的 `snapshot.argv` / `render.argv`，也不打开 representation。

## 2. 输出契约

输出 schema：

```text
control-plane/codex-desktop-read-only-adapter/v1
```

固定顶层字段：

| 字段 | 语义 |
|:---|:---|
| `status` | `ready` / `blocked` / `validation_failed` / `error` |
| `schema_version` | adapter v1 |
| `adapter` | 固定 `codex-desktop-read-only-adapter/v1` |
| `source` | 只输出 `project_root` 的安全摘要，不回显绝对路径 |
| `lifecycle` | 固定生命周期阶段和最终 `closed` 状态 |
| `producer` | producer 安全状态和退出码 |
| `consumer` | reference consumer 状态、退出码和安全 `source_handoff_id` |
| `findings` | adapter 自身生成的安全 finding；不复制原始 stderr、descriptor 或 argv |
| `guarantees` | one-shot、no-write、no-network、no-service、no-representation-read、no-descriptor-argv-execution、no-auto-retry |
| `next_action` | 固定安全下一步 |

退出码沿用项目语义：

- `ready` → `0`
- `error` → `1`
- `blocked` → `2`
- `validation_failed` → `5`

同一 project root、同一输入和同一版本重复调用时，结果保持确定性；不包含时间戳、PID、绝对路径或原始命令输出。

## 3. 进程与环境边界

- 每次调用只启动一轮 producer → consumer，最终关闭所有句柄；
- 每个固定子进程默认 30 秒超时，允许值为 `0 < timeout <= 60`；
- 超时、启动失败、空 stdout、非 UTF-8、非法 JSON、duplicate key、shape drift 或 status/exit-code 不一致均 fail closed；
- descriptor 和 consumer result 的 stdout 上限均为 1 MiB；
- 使用 argv 数组和 `shell=False`，不接受 shell 字符串；
- cwd 固定为用户选择的 project root；
- 子进程只获得最小运行环境白名单，不转发 credential、token、keyring 或任意用户环境变量；
- 固定设置 `PYTHONDONTWRITEBYTECODE=1`，禁止只读子进程生成 Python bytecode cache；
- 为兼容 Python user-site 依赖，保留 Windows 用户运行时所需的非敏感路径变量，但不将其写入结果；
- stderr 只用于本地诊断，绝不复制到 stdout 结果。

## 4. project root 边界

adapter 只接受同时满足以下条件的目录：

- 是目录；
- 包含 `pyproject.toml`；
- 包含 `agent_runtime/` 包目录。

不满足条件时不启动任何子进程，并返回固定的 `adapter-project-root-invalid` finding。结果始终只显示 `project_root`，不回显用户输入的绝对路径。

## 5. 状态映射

| 条件 | adapter 状态 | 行为 |
|:---|:---|:---|
| producer exit `0` 且 consumer `pass` / exit `0` | `ready` | 只表示 handoff validation 通过；不表示 representation 已加载 |
| consumer `blocked` / exit `2` | `blocked` | 保留安全 rule id，停止本次动作 |
| consumer `validation_failed` / exit `5` | `validation_failed` | 视为 contract/identity drift，停止本次动作 |
| producer/consumer 启动失败、超时、空输出、非法协议或 producer 非零但 consumer pass | `error` | 不自动重试，不执行任何 descriptor argv |

consumer 非 `pass` 时不会被升级为 `ready`。consumer status 与退出码不一致时，adapter 返回 `error`。

## 6. 测试与验收

新增：

```text
tests/test_codex_desktop_read_only_adapter.py
```

覆盖：

- 合法 producer → consumer one-shot pipeline；
- 固定 argv 与 cwd；
- descriptor argv sentinel 不被执行；
- determinism 和绝对路径不回显；
- blocked / validation_failed / error 状态映射；
- malformed consumer JSON、duplicate/protocol drift；
- 非 project root 不启动子进程；
- timeout 不自动重试；
- 真实 Windows 本地 stdio pipeline smoke test。

Stage 20 实际 smoke command：

```bash
python tools/codex_desktop_read_only_adapter.py \
  --project-root . \
  --timeout-seconds 30 \
  --json
```

结果为 `ready`，且：

- producer / consumer 均为 exit `0`；
- lifecycle 为 `created → producing → validating → ready → closed`；
- 未输出绝对 project root；
- 未读取或执行 snapshot/render representation；
- 未写入文件、ledger、draft 或 artifact；
- 未访问网络、启动 service 或执行真实 adapter。

## 7. Stage 20 收口结论

Stage 19 的设计 contract 已被一个独立、可测试、可回放的本地 adapter 实现承接。Stage 20 只开放“一次只读 handoff validation”这一项宿主动作，未扩大到 representation read、文件 export、UI write 或真实 execution。

Stage 21 已完成需求审计并冻结 validation-only；结论见 `docs/archive/82-read-only-representation-read-design-gate.md`。下一阶段 Stage 22 仅在出现明确 representation consumer、用户显式授权以及完整 no-write/no-network/no-service 设计后条件启动；当前 adapter 不扩展。

# 17 — Runtime Planning Bridge 闭环

## 这份文档解决什么问题

Runtime planning bridge 把 task ledger、adapter envelope draft、runtime gate 和 runtime ledger audit 串成一个只读闭环。它的目标不是执行 adapter，也不是写入真实 ledger，而是在真正执行之前，把“下一步动作”变成可验证、可审计、可交接的机器草案。

## 闭环链路

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> adapter validate / adapter inspect
  -> runtime gate check
  -> runtime check-ledger
```

每一步都只读：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger 或 envelope、不读取 credential 文件。

## 各命令职责

| 命令 | 职责 |
|:---|:---|
| `runtime plan` | 给定 task + adapter action，生成 compact 草案摘要 |
| `runtime plan --draft-json` | 输出 schema-valid 的 envelope draft 到 stdout |
| `runtime draft validate` | 从文件或 stdin 读取 draft，只读校验 schema 与 envelope consistency |
| `runtime draft inspect` | 从文件或 stdin 读取 draft，输出不含 payload 的摘要 |
| `runtime gate check` | 聚合 task 状态与 adapter approval/response gate |
| `runtime check-ledger` | 审计 task/event ledger 与 adapter envelope 的跨系统一致性 |

## Draft 输入格式

`runtime draft validate` 与 `runtime draft inspect` 支持两种 JSON 输入。

直接 envelope：

```json
{
  "version": 1,
  "description": "Runtime plan envelope draft",
  "artifacts": []
}
```

`runtime plan --draft-json` 外层包装：

```json
{
  "status": "pass",
  "task_id": "task-20260703-001",
  "task_status": "running",
  "envelope_draft": {
    "version": 1,
    "artifacts": []
  }
}
```

## CLI 用法

校验 draft 文件：

```bash
python -m agent_runtime.cli runtime draft validate --file draft.json
```

校验 stdin：

```bash
python -m agent_runtime.cli runtime draft validate --stdin
```

检查 draft 摘要：

```bash
python -m agent_runtime.cli runtime draft inspect --file draft.json
```

JSON 摘要：

```bash
python -m agent_runtime.cli runtime draft inspect --file draft.json --json
```

## 输出边界

`runtime draft inspect` 只输出：

- artifact counts
- request id / adapter / operation / preflight status / requires approval
- approval id / request id / status
- response status / evidence count / raw_ref 是否存在
- execution event type counts
- overall counters

它不输出完整 `target`、`input`、`evidence`、`raw_ref`、`decision_ref` 或 secret match。

## 安全边界

- `--file` 必须指向项目根目录内的安全 `.json` 文件。
- `--stdin` 只读 stdin，不落盘。
- draft validate / inspect 不执行外部命令。
- draft validate / inspect 不访问网络。
- draft validate / inspect 不写真实 task ledger、event ledger 或 adapter envelope。
- pending `approval_record` 不包含 `decision_ref` 字段。

## 与 Adapter 命令的关系

`runtime draft validate` 面向 runtime plan 的 draft 输入，支持外层 wrapper，并强调 draft 语义。

`adapter validate` 面向已经存在的 adapter envelope 文件。

两者最终使用同一套 envelope schema 与 consistency 规则，因此 draft 一旦通过，就可以进入后续 adapter / runtime gate 检查链路。

## 下一阶段候选

- 明确授权后实现真实 draft export 写文件接口。
- 明确授权后实现 event ledger append 接口。
- 将 runtime planning bridge 阶段冻结为 release tag。

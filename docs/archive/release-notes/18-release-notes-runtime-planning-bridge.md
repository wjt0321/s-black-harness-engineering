# 18 — Runtime Planning Bridge 阶段收口说明

## 阶段定位

本阶段冻结 Runtime read-only planning bridge：从 task 出发，生成 adapter envelope draft，校验 draft，检查 gate，并审计 ledger/envelope 一致性。

这一阶段仍然是只读 POC，不执行真实 adapter，不写真实 ledger，也不保存 draft 文件。

## 新增能力

### `runtime plan`

给定 `task_id`、adapter、operation 和 target，先检查 task 是否存在且非终态，再生成 adapter action 草案摘要。

终态 task（`finished` / `failed`）直接返回 `blocked`，不生成草案。

### `runtime plan --draft-json`

输出 schema-valid 的 `envelope_draft` 机器草案，适合交给后续 draft / adapter / gate 检查链路。

普通 `runtime plan --json` 保持 compact 摘要，不输出完整 envelope。

### `runtime draft validate`

从项目内安全 `.json` 文件或 stdin 读取 draft，支持直接 envelope 与 `runtime plan --draft-json` 外层 wrapper。

校验内容包括：

- JSON 结构
- envelope schema
- envelope artifact consistency

### `runtime draft inspect`

在 validate 通过后输出 draft 摘要，包括 artifact counts、request 摘要、approval 摘要、response/evidence 计数、execution event type counts 与 overall counters。

inspect 不输出完整 `target`、`input`、`evidence`、`raw_ref`、`decision_ref` 或 secret match。

### `runtime gate check`

聚合 task 状态与 adapter gate 状态，判断一个 `task_id + request_id` 是否可继续。

### `runtime check-ledger`

审计 task/event ledger 与 adapter envelope 的跨系统一致性，包括 task 引用、request 引用、ledger event 线索和终态 task 上的未完成 request。

## 安全边界

- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写真实 task ledger、event ledger 或 adapter envelope。
- 不读取 `.env` / credential 文件。
- 不回显完整 secret match、input payload、evidence description、raw_ref 或 decision_ref。
- `--file` 输入限制为项目根目录内安全 `.json` 文件。
- `--stdin` 输入不落盘。

## Schema 调整

为满足 draft 输出的最小披露原则，pending `approval_record` 不再强制包含 `decision_ref` 字段。历史 envelope 若带有 `decision_ref: null` 仍然兼容。

## 验证结果

本阶段收口前验证：

```text
python -m pytest -> 207 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

## 当前限制

- draft 只输出到 stdout，不写文件。
- gate check 仍依赖已有 envelope 文件输入。
- ledger audit 仍只审计，不写修复事件。
- 真实执行、真实 ledger append、真实 draft export 都需要后续显式授权和单独设计。

## 后续建议

下一阶段可以进入两条路线之一：

- 继续只读：新增 runtime handoff / report，用一条命令汇总 plan、draft、gate、ledger audit 状态。
- 进入受控写入：在显式授权机制下实现 draft export 或 event append。

# 84 — Stage 21 Read-only Representation Read Design Gate

> 日期：2026-07-15
> 状态：验收完成
> 前置事实源：`docs/81-codex-desktop-read-only-adapter-implementation.md`
> 设计事实源：`docs/82-read-only-representation-read-design-gate.md`

## 1. 决策

Stage 21 审计了 Stage 17 descriptor、Stage 18 reference consumer 和 Stage 20 host adapter 的 representation 边界，结论为：

> 当前没有已冻结的 representation consumer、用户动作或授权需求，因此保持 validation-only，不开放 representation read。

## 2. 冻结内容

- `ready` 只表示 handoff validation 通过；
- 不执行 `snapshot.argv` / `render.argv`；
- 不读取 HTML/JSON representation，不打开浏览器，不写临时文件或 artifact；
- 不新增 `control-panel consume` 命令、reader schema、identity、ledger event 或 service；
- 不接受 URL、socket、任意文件路径或 shell 字符串；
- future representation read 必须先完成真实消费者、用户显式授权、argv allowlist、输出脱敏、超时/取消与 no-write design gate。

## 3. 验收

本阶段为设计文档收口，不修改生产代码；现有 Stage 20 adapter smoke、全量测试与安全检查继续作为基线。

下一阶段为条件启动的 Stage 22，不因设计 gate 完成而自动开启 representation 执行。

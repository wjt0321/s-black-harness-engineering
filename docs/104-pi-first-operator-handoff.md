<!-- parents: 103-pi-postflight-audit-projection.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 102-pi-interactive-approval-roundtrip.md -->

# 104 - Pi-first Operator Handoff Gate (Stage 55)

> 状态：Stage 55 design gate 已收口
> 日期：2026-07-25
> 用户方向：Pi-first；OMP 太重，仅保留为兼容验证/备选

## 1. 决策

后续主线改为 **Pi-first, layer-by-layer**：先把最小 Pi 原生 extension 体验跑稳，再逐层启用 preflight、approval、postflight projection 和未来持久 audit。OMP 不再作为日常主推进路径；它只作为同源 ExtensionAPI 的兼容验证工具或临时备选。

该阶段不执行安装、不写 `~/.pi`、不修改 OMP/Pi 持久配置、不访问网络、不推送远端。

## 2. 分层路线

1. **Layer 0 - Pi native baseline**：确认独立 Pi CLI 可用，能在目标项目目录启动，并能加载一个空 extension。
2. **Layer 1 - Preflight only**：启用 `AGENT_RUNTIME_ROOT`，加载 `integrations/pi/extension.ts` 或复制为 `index.ts`；默认工具进入 Stage 52 preflight gate。
3. **Layer 2 - Approval optional**：按需设置 `AGENT_RUNTIME_APPROVAL_MODE=interactive`；仅固定 `git push origin main` 可进入一次确认。
4. **Layer 3 - Postflight projection optional**：按需设置 `AGENT_RUNTIME_POSTFLIGHT_MODE=summary`；只追加脱敏 summary，不写 ledger。
5. **Layer 4 - Durable audit future**：若需要持久审计，另起 design gate 设计 writer、schema、rollback 与 post-check。
6. **Layer 5 - OMP compatibility future**：只有在 Pi 原生路径跑稳后，才考虑把同一 extension 验证到 OMP，不把 OMP 作为基础依赖。

## 3. 推荐默认环境

默认只启用 Layer 1：

```text
AGENT_RUNTIME_ROOT=D:\Mydev\agent-runtime
```

审批和 postflight 投影默认不启用：

```text
# optional later
AGENT_RUNTIME_APPROVAL_MODE=interactive
AGENT_RUNTIME_POSTFLIGHT_MODE=summary
```

原因：先证明 Pi 原生加载与 preflight gate 稳定，再逐层打开交互和结果投影，避免一次性引入过多变量。

## 4. 安装交接边界

建议的持久安装目标为：

```text
%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\index.ts
```

安装动作应是显式的、可回滚的文件复制：

- 源：`D:\Mydev\agent-runtime\integrations\pi\extension.ts`
- 目标：`%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\index.ts`
- 回滚：删除目标目录或移回备份；不得改动现有 Orca extension 文件。

现有 `~/.pi/agent/extensions` 内有 Orca 扩展；Stage 55 不覆盖、不重命名、不排序它们。若未来 Pi 支持目录 discovery，新增目录应与现有扩展并列。

## 5. Smoke 顺序

每层只验证一个变量：

1. `pi --version` 或等价独立 Pi CLI 版本输出。
2. Pi 启动时能发现 extension，且未设置 `AGENT_RUNTIME_ROOT` 时默认工具 fail closed。
3. 设置 `AGENT_RUNTIME_ROOT` 后，普通 read 放行。
4. 读取 `.env` 在执行前阻断。
5. `git push origin main` 返回 `needs_approval` 阻断；不执行真实 push。
6. 可选开启 approval，验证拒绝/超时阻断；真实批准 smoke 仍不得连接远端。
7. 可选开启 postflight projection，验证 result 追加摘要且不回显输出。

## 6. 下一阶段停止线

Stage 56 才能考虑真实 Pi 原生安装 smoke。启动前必须先明确：

- 是否允许安装独立 Pi CLI；
- 是否允许写入 `%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\`；
- 是否只做 preflight layer，不启用 approval/postflight；
- 是否允许创建备份目录；
- smoke 使用的测试仓库和命令。

未经该授权，不得安装 package、写入 `~/.pi`、改现有 extension、启动真实工作流或执行 `git push`。

<!-- stage55-status: design-gate-complete -->
<!-- route: pi-first-layered -->
<!-- next-stage: stage56-pi-native-install-smoke -->

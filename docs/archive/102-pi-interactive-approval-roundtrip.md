<!-- parents: 101-pi-coding-agent-preflight-bridge.md -->
<!-- relates: 03-policy-schema.md, 06-adapter-layer.md, 98-fixed-git-status-executor-implementation-and-limited-enablement.md -->

# 102 - Pi Interactive Approval Roundtrip v1 (Stage 53)

> 状态：Stage 53 v1 已实现并完成本地验证
> 日期：2026-07-25
> 里程碑：本地 commit-level；不创建 tag，不自动 push

## 1. 阶段结论

Stage 53 在 Stage 52 host-side preflight 之上增加一个默认关闭、一次性、交互式批准路径。它只处理 bridge 返回的 `needs_approval`，不改变 `blocked` / `invalid` 的永久阻断语义，也不让 Harness 执行 Pi/OMP 工具。

v1 只支持一个固定候选：在 Harness root 与 host cwd 相同的前提下，对精确命令 `git push origin main` 请求一次用户确认。其他命令、其他 cwd、无 UI、print/json 模式、超时、拒绝、输入漂移或 bridge 身份漂移均 fail closed。

## 2. 启用方式

默认未设置时保持 Stage 52 行为，所有 `needs_approval` 均阻断。只有显式设置以下值才启用交互批准：

```text
AGENT_RUNTIME_APPROVAL_MODE=interactive
```

同时仍必须设置：

```text
AGENT_RUNTIME_ROOT=<Harness repository root>
AGENT_RUNTIME_PYTHON=<optional Python launcher>
```

## 3. 批准绑定

一次批准绑定以下完整身份：

- Pi/OMP `toolCallId` 清洗后的 `request_id`；
- bridge canonical `request_hash`；
- `tool`；
- `target_hash`；
- host `ctx.cwd` 与 `AGENT_RUNTIME_ROOT` 的规范化路径相等；
- 固定命令字面量 `git push origin main`；
- finding action 仅允许 `require_user_approval` / `require_secret_scan`。

确认前运行第一次 bridge preflight；用户确认后，从当前 `event.input` 重新归一化并再次运行 bridge。两次身份必须完全一致，且第二次仍为 `needs_approval`，否则阻断。批准不写磁盘、不缓存、不跨 tool call 复用。

## 4. 交互与失败语义

- 只允许 `ctx.hasUI=true` 且 mode 为 `tui` 或 `rpc`；
- 使用 `ctx.ui.confirm()`，超时 60 秒；
- 用户拒绝、关闭或超时均阻断；
- `blocked` / `invalid` 永不弹批准框；
- 批准后深冻结当前 input，阻止常规后续原地改参；
- 任一 bridge transport/policy failure 继续 fail closed。

## 5. 已知安全边界

Pi/OMP 的 `tool_call` handler 按扩展顺序执行，官方 API 允许后续 handler 修改 `event.input`，且修改后不会自动重新校验。当前 v1 会深冻结已批准 input，但宿主 API 没有提供“本 handler 必为最后一个”或“最终执行参数再次回调”的证明。因此：

- v1 是有限本地交互批准，不是通用强隔离 approval authority；
- 不应与会替换整个 `event.input` 的后续扩展组合使用；
- 后续若要扩大候选范围，必须先获得 final-arguments binding 或由 Harness 接管执行；
- 本阶段不写 approval ledger，不提供跨进程、跨会话或远程批准。

## 6. 真实 smoke

本机没有独立 Pi CLI，但安装了 OMP `17.0.8`；OMP 内含同源 `@earendil-works/pi-coding-agent` ExtensionAPI，并支持显式 `--extension`。使用 Stage 52 extension 完成三条真实 host smoke：

- 普通 `read docs/00-index.md` 放行；
- `read .env` 在执行前阻断；
- `bash git push origin main` 在执行前以 `needs_approval` 阻断。

Stage 53 交互批准由 18 项 Node 行为测试覆盖；无 UI 的 print 模式仍保持阻断。没有执行真实 `git push`，没有修改 Pi/OMP 持久配置。

## 7. 下一候选

下一候选为 Stage 54 - Pi Postflight Audit Design Gate。启动前必须先决定：最终参数可信来源、结果脱敏投影、tool result identity、失败/取消映射、是否写 ledger，以及如何避免把 host 结果误当 Harness execution authority。

<!-- stage53-status: implemented-local -->
<!-- authority: limited-host-interactive-approval-only -->
<!-- next-stage: stage54-pi-postflight-audit-design-gate -->

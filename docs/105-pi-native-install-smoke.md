<!-- parents: 104-pi-first-operator-handoff.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 102-pi-interactive-approval-roundtrip.md, 103-pi-postflight-audit-projection.md -->

# 105 - Pi Native Install Smoke (Stage 56)

> 状态：Stage 56 已完成并收口
> 日期：2026-07-25
> 授权范围：安装独立 Pi、写入可回滚的全局 extension、只启用 Layer 1 preflight

## 1. 完成结果

Stage 56 已把 Pi-first 路线推进到真实本机安装层：

- 独立 Pi CLI 已安装为 `@earendil-works/pi-coding-agent@0.82.0`。
- `pi --version` 返回 `0.82.0`。
- 全局 extension 已安装到 `%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\`。
- 只部署两份运行文件：`index.ts` 与 `preflight-bridge.ts`。
- 用户级 `AGENT_RUNTIME_ROOT` 已设置为 `D:\Mydev\agent-runtime`。
- 用户级 `AGENT_RUNTIME_APPROVAL_MODE` 与 `AGENT_RUNTIME_POSTFLIGHT_MODE` 未设置；approval 与 postflight 仍默认关闭。

## 2. 备份与回滚

写入前已备份原有全局 extension 目录：

```text
%USERPROFILE%\.pi\agent\backups\stage56-before-pi-preflight-20260725-164539
```

备份内包含 `extensions/` 快照与 `SHA256SUMS.txt`。原有 Orca 扩展保持原样：

```text
orca-agent-status.ts
orca-prefill.ts
orca-titlebar-spinner.ts
```

回滚方式：

1. 删除 `%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\`。
2. 如需恢复全局 extension 目录到安装前状态，用备份目录中的 `extensions/` 覆盖当前 `extensions/`。
3. 如需关闭 Harness preflight，删除用户级 `AGENT_RUNTIME_ROOT`。

## 3. 有效 smoke

有效验收使用 Pi 官方 `DefaultResourceLoader` 从真实全局目录自动发现 extension，然后调用该已加载实例注册的真实 `tool_call` handler。该 smoke 不调用模型、不执行工具、不访问网络。

结果：

```json
{
  "auto_discovered": true,
  "extension_path": "C:\\Users\\wxb\\.pi\\agent\\extensions\\pi-preflight-bridge\\index.ts",
  "handler_count": 1,
  "results": [
    {"tool":"read","id":"stage56-pass","allowed":true,"blocked":false,"reason":null},
    {"tool":"read","id":"stage56-secret","allowed":false,"blocked":true,"reason":"Harness preflight blocked: Policy blocks this tool call; do not execute it."},
    {"tool":"bash","id":"stage56-push","allowed":false,"blocked":true,"reason":"Harness preflight needs_approval: Policy requires explicit user approval before this tool call may proceed."}
  ]
}
```

该结果证明：

- Pi 能自动发现持久安装的 extension。
- 普通 `read docs/00-index.md` 通过 preflight。
- `read .env` 在执行前阻断。
- `bash git push origin main` 在执行前进入 `needs_approval` 阻断。

## 4. 非有效 smoke 记录

曾尝试用 Pi RPC `bash` 命令做 smoke，结论是该路径不适合验证 `tool_call` extension：RPC `bash` 是用户侧直接命令，绕过 LLM 默认工具调用链，因此不会触发 `tool_call` handler。

该尝试在隔离临时仓库 `tool_results/stage56-pi-smoke` 内执行，仓库没有 `origin`，`git push origin main` 在解析远端前失败为 `fatal: 'origin' does not appear to be a git repository`。未连接远端、未推送内容、未读取真实 `.env`。

## 5. 当前边界

Stage 56 不做以下事项：

- 不开启 `AGENT_RUNTIME_APPROVAL_MODE`。
- 不开启 `AGENT_RUNTIME_POSTFLIGHT_MODE`。
- 不写 Harness ledger。
- 不开放第二个 command。
- 不把 RPC `bash` 当作 tool-call gate 证明。
- 不把 OMP 重新设为主线。
- 不执行真实 `git push`。

## 6. 下一候选

Stage 57 建议为 **Pi First Real Session Gate**：在真实 Pi 会话里使用最小提示触发默认工具，并确认 agent-facing 工具路径与 Stage 56 handler smoke 一致。启动前需另行决定是否允许模型调用、是否允许只读真实仓库、是否继续禁用 approval/postflight。

<!-- stage56-status: native-install-smoke-complete -->
<!-- route: pi-first-layered -->
<!-- next-stage: stage57-pi-first-real-session-gate -->

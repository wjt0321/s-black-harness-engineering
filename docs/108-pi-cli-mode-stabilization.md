<!-- parents: 107-pi-project-local-runtime-integration.md -->
<!-- relates: 106-pi-first-real-session-gate.md, 101-pi-coding-agent-preflight-bridge.md -->

# 108 - Pi CLI/TUI Mode Stabilization Gate (Stage 59)

> 状态：Stage 59 已完成并收口
> 日期：2026-07-25
> 授权范围：诊断并稳定 `pi --print` / `--mode json` / TUI 入口；preflight 保持启用；不启用 approval/postflight；不执行真实 push 或写操作；不修改 Pi 上游

## 1. 诊断结论

在项目本地 `PI_CODING_AGENT_DIR=<project-root>\.runtime\pi-agent` 与 `deepseek-compat` provider 下，Stage 57 记录的 0 stdout / 0 stderr 长等待**当前不再现**：7 次以上受控 `--print` / `--mode json` 运行全部在 2–6 秒内返回，退出码 0。

根因分析（基于 Pi 0.82.0 安装源码与受控实验）：

- **历史失败主因是 API 侧不稳定 + 默认模型解析漂移的组合**。`findInitialModel`（`dist/core/model-resolver.js`）的优先级为：CLI 参数 → scoped models → session 恢复 → settings 默认 → 第一个有 auth 的可用模型（按内置 provider 顺序）。未钉住默认模型时，本机默认解析落到**内置 `deepseek` / `deepseek-v4-pro`**（实测 json mode 输出确认），而 Stage 57 记录的 0 输出超时集中在内置 deepseek provider / `deepseek-v4-flash` 组合；解析结果随 auth 环境漂移，入口行为不确定。
- **已排除的候选**：CLI print 路径 `ModelRuntime.create` 未传 `allowModelNetwork`，启动期没有 awaited 的远程模型目录刷新；版本检查（`pi.dev`，10 秒超时）只在 interactive 模式触发且为 fire-and-forget，不会阻塞 print 输出。
- **TUI 非 TTY 行为是 fail-fast**：重定向/管道下 `pi` 立即以 rc=1 输出 `stdin is not a tty`，不会 0 输出挂起。真正的 TUI 必须在真实终端中运行。
- 间歇性 API 侧失败（服务端流式停滞、reasoning-only 空输出）无法在本仓根治；本阶段的缓解是**确定性入口契约 + 钉住已验证 provider + 有界超时 + 可重复 smoke**。

## 2. 最小修复

只做两处改动，均不触碰 Pi 上游与仓库受控写边界：

1. **钉住默认模型**（机器本地运行态，gitignored）：`.runtime/pi-agent/settings.json` 增加
   `defaultProvider=deepseek-compat`、`defaultModel=deepseek-v4-flash`。
   写入前备份：`.runtime/pi-agent/backups/stage59-before-settings-20260725-192154/settings.json`。
   效果：默认解析稳定命中 Stage 57 已验证的 compat provider（`max_tokens=512`，避免 reasoning-only 空输出）。
2. **可重复 smoke**：`integrations/pi/smoke/cli-mode-smoke.sh`（Git Bash，零依赖）。
   固定 argv、`--no-session`、每次运行有界 timeout（默认 60s，`SMOKE_TIMEOUT` 可调）、证据写入 gitignored 的 `.runtime/pi-agent/backups/stage59-cli-smoke-<ts>/`、绝不回显凭据值。

## 3. 人类 CLI/TUI 入口契约

环境（用户级或会话级设置；凭据只从环境解析，永不打印）：

```text
PI_CODING_AGENT_DIR=<project-root>\.runtime\pi-agent
AGENT_RUNTIME_ROOT=<project-root>        # 缺失时 preflight fail-closed（阻断一切 tool_call）
DEEPSEEK_API_KEY=<运行时注入>             # models.json 只引用 $DEEPSEEK_API_KEY
```

非交互入口（脚本化，均会发起**真实 DeepSeek 模型调用**）：

```bash
pi --print --no-session --no-tools "prompt"                 # 纯文本
pi --print --no-session --no-tools --mode json "prompt"     # JSON 事件流
pi --print --no-session --tools read "prompt"               # 仅 read 工具，preflight 门禁生效
```

受控调用建议包 60 秒有界超时 + kill（参考 smoke 脚本的 `run_timed`）。

TUI 入口（人工）：在真实终端（Windows Terminal / PowerShell / cmd）直接运行 `pi`；**不要**重定向或管道 stdin/stdout（非 TTY 会 fail-fast 退出）。TUI 内默认模型即为已钉住的 `deepseek-compat/deepseek-v4-flash`。

## 4. 验证证据

- 提交版 smoke 首次运行 **5/5 PASS**（2026-07-25）：
  - print 文本模式返回 `STAGE59_OK`（2s）；
  - json 模式确认 `"provider":"deepseek-compat"`、`"model":"deepseek-v4-flash"`（钉住生效）；
  - `read stage59-proof.txt` roundtrip：preflight pass，工具执行，模型回传 `STAGE59_OK: STAGE59_TOOL_OK`；
  - `read .env` roundtrip：preflight 阻断，canary 值 `SMOKE_CANARY_SECRET` 未出现在任何输出；
  - 证据目录：`.runtime/pi-agent/backups/stage59-cli-smoke-20260725-192623/`。
- 修复前对照：未设 `AGENT_RUNTIME_ROOT` 时 read roundtrip 被 extension fail-closed 阻断（门禁在 CLI 路径生效的直接证据）。
- 重复性：5 次连续 print 文本运行 + 2 次 json 运行全部 2–6s 返回，rc=0，stderr 为空。
- TUI：非 TTY 启动 rc=1 `stdin is not a tty`（fail-fast 证据：`stage59-cli-mode/tui-launch.*`）；真实终端人工会话未自动化，按第 3 节契约执行。

## 5. 边界

- 不修改 Pi 上游（`node_modules` 未 patch）；不新增 npm 依赖；不改 `integrations/pi/` extension 代码。
- `AGENT_RUNTIME_APPROVAL_MODE` / `AGENT_RUNTIME_POSTFLIGHT_MODE` 保持未设置；不开放 bash/write/edit；不执行真实 push；不写 Harness ledger。
- `settings.json` / `models.json` 位于 gitignored `.runtime/`，不含明文凭据。
- smoke 脚本仅在 operator 显式运行时执行，且会发起真实模型调用；它不是 CI 测试。
- 间歇性 API 侧失败未被根治；若复现 0 输出超时，按契约以 60s 有界 kill 收集证据后再诊断。

## 6. 下一候选

- 真实终端人工 TUI 会话验收（operator 执行，按第 3 节契约），以及间歇失败再观察。
- 任何 Layer 2 approval / Layer 3 postflight 启用、bash/write/edit 开放或第二个 command 都必须独立设计并由用户明确授权。

<!-- stage59-status: cli-mode-stabilized-pinned-default -->
<!-- route: pi-first-layered -->
<!-- next-stage: pi-tui-operator-acceptance -->

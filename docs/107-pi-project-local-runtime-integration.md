<!-- parents: 106-pi-first-real-session-gate.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 105-pi-native-install-smoke.md -->

# 107 - Pi Project-local Runtime Integration (Stage 58)

> 状态：Stage 58 已完成并收口
> 日期：2026-07-25
> 目标：将 Pi agent dir 纳入 `<project-root>` 的本地运行目录，统一管理且不进入 Git

## 1. 当前有效路径

用户级环境变量已设置为：

```text
PI_CODING_AGENT_DIR=<project-root>\.runtime\pi-agent
```

项目 `.gitignore` 已忽略：

```text
.runtime/
```

该目录包含 Pi 的 extensions、models、settings、sessions 与 backups。它是本机运行态，不是仓库源代码或可发布配置。

## 2. 迁移方式

从历史默认目录复制：

```text
%USERPROFILE%\.pi\agent
```

到项目本地目录：

```text
<project-root>\.runtime\pi-agent
```

原目录未删除、未改写，保留为回滚副本。若需回滚，清除或改回用户级 `PI_CODING_AGENT_DIR` 即可重新使用默认目录。

## 3. 验证

在新目录下完成：

- `pi --list-models deepseek-compat` 成功识别 `deepseek-v4-flash`。
- Pi `DefaultResourceLoader` 自动发现 `.runtime\pi-agent\extensions\pi-preflight-bridge\index.ts`。
- extension 加载无错误。
- handler smoke：普通 read 放行、`.env` read 阻断、`git push origin main` 返回 needs_approval。

验证脚本保存在被忽略的本地运行目录：

```text
.runtime\pi-agent\backups\verify-project-pi-agent.mjs
```

## 4. 边界

- `.runtime` 不进入 Git，避免提交 auth、session、backup 或未来凭据。
- `auth.json`、模型配置与 session 数据不写入项目文档。
- `AGENT_RUNTIME_APPROVAL_MODE` 与 `AGENT_RUNTIME_POSTFLIGHT_MODE` 仍未启用。
- 未执行真实 push，未开放新的工具权限。
- Stage 57 的历史证据路径仍指向旧默认目录；该历史记录不改写。

## 5. 下一候选

下一候选仍是 **Pi CLI Mode Stabilization Gate**：排查 `pi --print` / `--mode json` / TUI 在项目本地 agent dir 与 DeepSeek compat provider 下的稳定性。

<!-- stage58-status: project-local-pi-runtime-complete -->
<!-- route: pi-first-layered -->
<!-- next-stage: pi-cli-mode-stabilization -->

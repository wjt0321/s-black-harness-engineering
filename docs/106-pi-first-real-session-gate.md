<!-- parents: 105-pi-native-install-smoke.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 104-pi-first-operator-handoff.md -->

# 106 - Pi First Real Session Gate (Stage 57)

> 状态：Stage 57 已完成并收口（SDK-host real session proof）
> 日期：2026-07-25
> 授权范围：一次受控模型调用；隔离目录；只启用内置 `read`；不启用 approval/postflight

## 1. 完成结果

Stage 57 证明了 Pi-first 路线的第一条真实 agent 会话链路：

- 独立 Pi `0.82.0` 保持可用。
- 全局 `pi-preflight-bridge` 从 `%USERPROFILE%\.pi\agent\extensions\pi-preflight-bridge\index.ts` 被加载。
- SDK 直连 `createAgentSession` 成功加载 4 个全局 extension：三份 Orca extension 与 `pi-preflight-bridge`。
- 仅启用内置 `read` 工具。
- 模型发起一次 `read stage57-proof.txt` 工具调用。
- `read` 工具执行完成。
- 第二轮模型返回固定文本：`STAGE57_OK:PI_LAYER1_REAL_SESSION_OK`。

该验收使用隔离目录：

```text
%USERPROFILE%\.pi\agent\backups\stage57-sdk-real-read
```

隔离文件：

```text
stage57-proof.txt = PI_LAYER1_REAL_SESSION_OK
```

## 2. 模型配置

Pi 内置 DeepSeek provider 在 CLI / JSON mode 中表现不稳定：`deepseek-v4-flash` 请求曾出现 0 stdout / 0 stderr 长时间等待。Node `fetch` 直连 DeepSeek API 可正常返回，说明基础网络与 API key 可用。

为完成受控验收，Stage 57 写入可回滚的自定义 provider：

```text
%USERPROFILE%\.pi\agent\models.json
```

备份位置：

```text
%USERPROFILE%\.pi\agent\backups\stage57-before-models-json-20260725-175734
```

当前自定义 provider 使用：

- provider: `deepseek-compat`
- model: `deepseek-v4-flash`
- api: `openai-completions`
- baseUrl: `https://api.deepseek.com/v1`
- apiKey: `$DEEPSEEK_API_KEY`
- `maxTokensField`: `max_tokens`
- model maxTokens: `512`

`models.json` 不含明文密钥；运行时仅从 `.env.local` 临时注入 `DEEPSEEK_API_KEY`。

## 3. 验收事件

SDK real-read 输出显示：

- extension 加载成功，`extensionErrors=0`。
- extension paths 包含 `pi-preflight-bridge\index.ts`。
- 第一轮模型生成 `read` 工具调用：`{"path":"stage57-proof.txt"}`。
- 事件流出现 `tool_execution_start` / `tool_execution_end`，toolName 均为 `read`。
- 第二轮 text delta 合成为：`STAGE57_OK:PI_LAYER1_REAL_SESSION_OK`。
- agent 以 `agent_end` / `agent_settled` 完成。

完整事件证据写在：

```text
%USERPROFILE%\.pi\agent\backups\stage57-sdk-real-read\sdk-real-read-events.json
```

## 4. 失败路径与限制

以下路径不作为 Stage 57 成功证据：

- Pi RPC `bash`：这是用户侧直接命令，绕过 LLM default-tool `tool_call` chain。
- Pi CLI `--mode json` / `--print`：在本机当前组合下仍可能 0 stdout / 0 stderr 超时；需要另起 Stage 排查 CLI mode 启动/参数/runner 行为。
- DeepSeek `deepseek-chat`：当前 API 已拒绝该模型名，只接受 `deepseek-v4-pro` / `deepseek-v4-flash`。
- `deepseek-v4-flash` 小 token 上限：32 tokens 会只产出 reasoning，无 text；512 tokens 可得到文本。

## 5. 当前边界

Stage 57 不开放：

- 不启用 `AGENT_RUNTIME_APPROVAL_MODE`。
- 不启用 `AGENT_RUNTIME_POSTFLIGHT_MODE`。
- 不执行真实 `git push`。
- 不开放 `bash` / `write` / `edit`。
- 不写 Harness ledger。
- 不声明 Pi CLI print/json mode 已稳定。
- 不把 OMP 重新设为主线。

## 6. 下一候选

Stage 58 建议为 **Pi CLI Mode Stabilization Gate**：专门排查并稳定 `pi --print` / `--mode json` 在当前 DeepSeek compat provider 与全局 extension 下的启动与输出行为。只有 CLI mode 稳定后，才把日常操作入口从 SDK proof 推进到可人工使用的 Pi CLI/TUI 流程。

<!-- stage57-status: sdk-real-session-proof-complete -->
<!-- route: pi-first-layered -->
<!-- next-stage: stage58-pi-cli-mode-stabilization -->

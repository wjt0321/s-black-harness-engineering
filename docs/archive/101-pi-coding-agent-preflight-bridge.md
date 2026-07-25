<!-- parents: 100-fixed-execution-operational-recovery-implementation.md -->
<!-- relates: 98-fixed-git-status-executor-implementation-and-limited-enablement.md, 06-adapter-layer.md, 03-policy-schema.md -->

# 101 — Pi Coding Agent Preflight Bridge（Stage 52）

> 状态：**Stage 52 v1 已完成并收口（host-side preflight only）**
> 日期：2026-07-25
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`（已推送至 `origin`）
> 里程碑策略：Stage 52 形成 commit-level milestone；按用户授权推送到 `origin/main`，不创建 tag

## 1. 阶段结论

Stage 52 按用户明确授权，将原候选「Fixed Execution Next-decision Design Gate」替换为
**Pi Coding Agent Preflight Bridge v1**：一个供 Pi TypeScript Extension 调用的一次性
stdin/stdout JSON 预检桥。第一版只做**规范化与门禁判断**，输出稳定 decision：
`pass` / `needs_approval` / `blocked` / `invalid`。

本阶段**不是** Harness real adapter execution authority：

- bridge 绝不执行 read/write/edit/bash 中的任何一个工具；
- 不写 task/event ledger、不创建 envelope draft、不执行任何受控写入；
- 不访问网络、不启动服务、不修改 Pi 上游项目；
- 不读取 `.env` / credential / token / keyring，响应不回显任何输入值；
- Stage 49 Windows fixed Git status 权限边界没有任何变化。

## 2. 架构与落点

```text
Pi Extension (integrations/pi/extension.ts)
  -> tool_call 拦截（read/write/edit/bash）
  -> 归一化为 pi-bridge/preflight-request/v1
  -> 固定 argv 子进程：python -m agent_runtime.cli pi-bridge preflight
       shell=false、bounded timeout/stdout/stderr、最小环境白名单、无重试
  -> agent_runtime/pi_preflight_bridge.py
       input gate（64 KiB / UTF-8 / duplicate key / depth / 严格字段）
       -> policy.check_path / check_text / check_action（pi-host adapter）
  -> pi-bridge/preflight-response/v1：pass / needs_approval / blocked / invalid
  -> pass 放行；needs_approval / blocked / invalid 一律 block
```

新增/修改：

- `agent_runtime/pi_preflight_bridge.py`：bridge 模块（纯函数 + IO 包装）。
- `agent_runtime/cli.py`：新增顶层命令组 `pi-bridge preflight`（只读 stdin、只写 stdout、始终 JSON）。
- `adapters/adapters.sample.json`：新增独立 registry 条目 `pi-host`（`kind=cli_tool`、`risk_level=local`、`requires_approval=false`、capabilities `tool_call_preflight` / `host_gate`）。**不复用 omp-acp**；omp-acp 是 ACP 委托 adapter，pi-host 是 Pi 宿主侧门禁边界。
- `integrations/pi/`：`preflight-bridge.ts`（stdio client）、`extension.ts`（最小 Extension 示例）、request/response JSON schema、`test/preflight-bridge.test.ts`（`node:test` 行为测试）、`README.md`、`package.json`（零依赖）。
- `tests/test_pi_preflight_bridge.py`：44 项 Python 单元/CLI 测试。

## 3. 请求契约（v1）

stdin 接收单个 bounded JSON 文档：

- 上限 64 KiB；必须 UTF-8、非空、单 JSON object；
- duplicate key、depth > 16、未知顶层字段、未知 tool、未知 input 字段、缺失字段、非字符串字段、空值/NUL/超长字段一律 `decision=invalid`；
- `schema_version` 固定 `pi-bridge/preflight-request/v1`；
- `tool` ∈ `read` / `write` / `edit` / `bash`；
- 每个 tool 只接受安全最小字段：read `{path}`；write `{path, content}`；edit `{path, edits: [{old_string, new_string}]}`（与 Pi 官方 edit schema `{path, edits:[{oldText, newText}]}` 对齐，1–16 项）；bash `{command}`；path/command ≤ 4096 字符，content/单条 edit 文本 ≤ 48 KiB；
- `request_id` 可选，限定 `[A-Za-z0-9._:-]`、≤ 128 字符。

## 4. 门禁评估

- `read`：`check_path(read=True)` + `check_action(pi-host, "read")`；
- `write`：`check_path(write=True)` + `check_text(content)` + `check_action(pi-host, "write")`；
- `edit`：`check_path(write=True)` + `check_text(全部 edits 的 old_string/new_string)` + `check_action(pi-host, "edit")`；
- `bash`：`check_text(command)` + `check_action(pi-host, "bash", target=command)`；
- 所有文件类 tool 先做 sensitive-target 检查：目标 basename 命中 `.env`/`.key`/`.pem`/`.p12`/`.pfx`/`.crt`/`.der` 等 credential 类别直接 `blocked`（`pi-bridge-sensitive-target`），不进入 policy 评估。

decision 归并（确定性、fail closed）：

- 全部 `pass`/`warn` → `pass`；
- 任一 `needs_approval` 或 `needs_input`（如 `require_secret_scan`）→ `needs_approval`；
- 任一 `blocked` / `validation_failed` → `blocked`；
- policy 后端 `error` 或任何内部异常 → `blocked`（fail closed，不泄露内部细节）；
- 输入门禁或形状校验失败 → `invalid`。

退出码：`pass=0`、`blocked=2`、`needs_approval=3`、`invalid=5`，复用既有 CLI 退出码语义。

## 5. 响应契约与 secret-safe 输出

响应为单个确定性 JSON 文档（`pi-bridge/preflight-response/v1`）：

- `decision`、`checks[]`（`input_gate` / `sensitive_target` / `path_policy` / `secret_scan` / `action_policy`）、
  `findings[]`（仅 `rule_id` / `severity` / `action` / `message`，跨 policy 去重、≤ 64 条）、
  `next_action`（`proceed` / `request_user_approval` / `do_not_execute` / `fix_request`）；
- request identity：`request_id`（回显）、`request_hash`（规范化请求 canonical JSON 的 SHA-256）、
  `target_hash`（目标 path/command 的 SHA-256）；
- `guarantees`：`executes_tools / writes_files / writes_ledgers / accesses_network / reads_target_files / echoes_input_values` 全为 `false`；
- **不输出**完整 target、命令、文件内容；findings message 只来自 policy 静态文本；
- invalid 时 `request_hash` / `tool` / `target_hash` 为 `null`；
- 相同输入产生 byte-equivalent 输出，无时间戳、无随机数、无进程状态。

## 6. TypeScript 侧（integrations/pi/）

- 真实可安装 Pi extension：`extension.ts` default export `(pi: ExtensionAPI)`，注册 `pi.on("tool_call", handler)`；handler 使用 `event.toolName` / `event.toolCallId` / `event.input`，非 `pass` 返回 `{block:true, reason}`；`ExtensionAPI` 仅 type import，运行时零 npm 依赖。
- 官方字段已核对 Pi 当前源码（`src/core/tools/{bash,read,write,edit}.ts`，2026-07-25）：bash `{command}`、read `{path, offset?, limit?}`、write `{path, content}`、edit `{path, edits:[{oldText, newText}]}`（legacy 顶层 `oldText`/`newText` 兼容）；`request_id` 来自 `toolCallId`（按 bridge 字母表清洗，≤ 128 字符）。
- 配置：`AGENT_RUNTIME_ROOT`（必需，指向 Harness 仓库根；未设置则 fail-closed block）、`AGENT_RUNTIME_PYTHON`（可选 launcher 覆盖）。安装：目录复制为 `~/.pi/agent/extensions/pi-preflight-bridge/` 并将 `extension.ts` 重命名为 `index.ts`，或在 `settings.json` 的 `extensions` 中引用。
- 固定 argv `python -m agent_runtime.cli pi-bridge preflight`，`shell=false`；
- timeout 默认 10s、clamp 至 [1s, 30s]；stdout ≤ 64 KiB、stderr ≤ 16 KiB；超限即 kill；
- 子进程环境白名单（PATH/SystemRoot/WINDIR/PATHEXT/TEMP/TMP/APPDATA/USERPROFILE/HOME 等 Python 定位用户 site-packages 所需），不转发凭据变量；不读取任何 secret 文件；
- 无重试；任何 spawn/timeout/overflow/解析失败都返回本地合成的 `blocked` 响应（`pi-extension-local-fallback/v1`），fail closed；
- 四个默认工具之外的工具一律 block（fail-closed 默认）；纯函数（`toBridgeRequest` / `extractEditEntries` / `sanitizeRequestId` / `decisionToGateResult` / `resolveBridgeOptions`）可独立测试。

## 7. 验证

- `tests/test_pi_preflight_bridge.py`：44 项，覆盖四工具 pass（含多 edit entries）、`needs_approval`（git push / rm -rf）、`blocked`（.env/.pem、只读路径、内容/命令/edit 含动态拼接 secret、registry 缺失 fail-closed）、`invalid`（空/超大/非 UTF-8/坏 JSON/duplicate key/未知字段/未知 tool/缺字段/错误类型/NUL/坏 request_id/错误 schema_version/edits 形状）、输出确定性、secret/path/command 不回显、guarantees、无文件系统副作用、CLI 退出码与单 JSON 文档输出、`pi-host` registry 条目独立性。
- `integrations/pi/test/preflight-bridge.test.ts`：12 项 `node:test` 行为测试，真实 spawn Python bridge，覆盖 pass/blocked/needs_approval、确定性、未知 python launcher fail-closed、四工具官方字段归一化（含 edit 当前/legacy 双形状）、toolCallId → request_id 清洗、tool_call handler allow/block 映射、`resolveBridgeOptions` 配置门禁。
- 全量 pytest、doctor、public scan、受控写回归、docs hook、`git diff --check` 通过。

本阶段没有运行任何真实工具执行，没有修改仓库真实 ledger；按用户授权推送到 `origin/main`，不创建 tag。

## 8. 明确不做

- 不开放通用 adapter execution；bridge 不执行 read/write/edit/bash；
- 不新增 HTTP/DB/daemon/UI/service；不访问网络；
- 不修改 Stage 49 fixed Git status 权限；不新增第二个真实 operation；
- 不写 task/event ledger、不做任何受控写入；
- 不读取或输出任何凭据；不修改 Pi 上游项目；
- 不创建 tag；本阶段提交与推送仅按用户本轮明确授权执行。

## 9. 已知限制与后续候选

- bridge 是策略门禁而非沙箱：`bash` 命令的间接行为（如 `cat .env`、命令拼接绕过）不在 v1 阻断范围内；host 侧仍需把 `needs_approval` 当作人工审查入口。
- Pi 官方字段已按当前源码核对（2026-07-25）；Pi 上游若变更 edit/bash 等 schema，extension 需同步复核。
- policy `command_rules` 基于正则，存在固有漏判/误判空间；rule 演进属于 policy 治理，不属于 bridge 变更。
- v1 不覆盖 Pi 非默认工具；自定义工具默认 block，放行需独立设计。
- 后续候选：approval roundtrip 接入、更多工具的字段契约、bridge 与 orchestration approval read model 的关联；均需独立阶段与用户明确授权。

<!-- stage52-implementation-status: closed -->
<!-- milestone-kind: commit-level-only -->
<!-- stable-tag: v0.17.0-filtered-snapshot-display-host-integration -->
<!-- authority: host-side-preflight-only -->

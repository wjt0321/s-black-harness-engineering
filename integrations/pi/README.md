# Pi Coding Agent Preflight Bridge（Stage 52 可安装 Extension）

本目录是一个**真实可安装**的 Pi TypeScript Extension：在 Pi 执行默认工具
（`read` / `write` / `edit` / `bash`）之前，通过固定 argv 的一次性 Python CLI
子进程调用 Harness preflight bridge，按返回 decision 放行或阻断。

**v1 边界**：这只是 host-side preflight enforcement，不是 Harness real adapter
execution authority。bridge 只做规范化与门禁判断，绝不执行 read/write/edit/bash，
不写 ledger，不访问网络，不启动服务，不读取 secret。

## 文件

| 文件 | 用途 |
|:---|:---|
| `extension.ts` | 可安装 Pi extension：default export `(pi: ExtensionAPI)`，`pi.on("tool_call")` 拦截，非 pass 返回 `{block:true, reason}` |
| `preflight-bridge.ts` | 一次性 stdio 子进程 client：固定 argv、`shell=false`、bounded timeout/stdout/stderr、最小环境白名单、无重试 |
| `pi-preflight-bridge-request.schema.json` | 请求契约（与 Python 实现一致） |
| `pi-preflight-bridge-response.schema.json` | 响应契约 |
| `test/preflight-bridge.test.ts` | `node:test` 行为测试（真实调用 Python bridge） |

## 运行前提

- Pi（`@earendil-works/pi-coding-agent`）；extension 类型仅 type import，运行时零 npm 依赖。
- Node >= 22.18（本仓库内直接以 type stripping 运行 `.ts` 做测试；Pi 侧由 jiti 加载，无需构建）。
- `python` 在 PATH 上，且 Harness 仓库已 `pip install -e .`。

## 安装

1. 把本目录复制为 `~/.pi/agent/extensions/pi-preflight-bridge/`，并将 `extension.ts`
   重命名为 `index.ts`（目录型 extension 的入口），或在 `settings.json` 的
   `extensions` 中显式引用 `extension.ts` 路径。
2. 设置环境变量：
   - `AGENT_RUNTIME_ROOT`（必需）：Harness 仓库根目录，内含 `policies/` 与
     `adapters/`；bridge 子进程以此为 cwd / `--root`。**未设置时 extension 对所有
     默认工具调用 fail-closed block。**
   - `AGENT_RUNTIME_PYTHON`（可选）：python launcher 覆盖；其后的 argv 固定不变。
   - `AGENT_RUNTIME_APPROVAL_MODE=interactive`（可选，默认关闭）：启用 Stage 53 一次性交互批准。v1 只支持 host cwd 等于 Harness root 时的精确命令 `git push origin main`；其他 `needs_approval` 仍阻断。

## Stage 53 一次性交互批准

- 仅在 `ctx.hasUI=true` 且 mode 为 `tui` / `rpc` 时弹出确认；print/json、超时、拒绝均阻断。
- 确认后从当前 `event.input` 重新归一化并重跑 bridge；request id/hash、tool、target hash 必须与确认前完全一致。
- 批准不写磁盘、不缓存、不跨调用复用；`blocked` / `invalid` 永不弹确认。
- v1 只允许 `git push origin main`，并深冻结已批准 input。Pi/OMP API 仍允许排序更后的扩展替换整个 input，因此该模式是有限本地 host approval，不是通用强隔离 approval authority。

## 工作方式

- default export 工厂注册 `pi.on("tool_call", handler)`；handler 读取
  `event.toolName` / `event.toolCallId` / `event.input`。
- 归一化为 bridge request（`request_id` 来自 `toolCallId`，按 bridge 字母表清洗）：
  - `read {path, offset?, limit?}` → `{path}`（offset/limit 不参与门禁）；
  - `write {path, content}` → `{path, content}`；
  - `edit {path, edits:[{oldText, newText}]}` → `{path, edits:[{old_string, new_string}]}`
    （兼容 legacy 顶层 `oldText`/`newText`；多 edit 逐项映射）；
  - `bash {command, timeout?}` → `{command}`。
- decision 映射（固定契约）：`pass` → 放行（返回 `undefined`）；
  `needs_approval` / `blocked` / `invalid` → `{block:true, reason}`。
- 四个默认工具之外的工具一律 block（fail-closed）；放行需显式设计决策。

## 安全性质

- 子进程 argv 固定为 `python -m agent_runtime.cli pi-bridge preflight`，不接受调用方传入参数。
- 子进程环境只保留 `PATH/SystemRoot/WINDIR/PATHEXT/TEMP/TMP/APPDATA/USERPROFILE/HOME` 等最小白名单（Python 定位用户 site-packages 所需），不转发任何凭据变量。
- timeout 默认 10s、上限 30s；stdout 上限 64 KiB、stderr 上限 16 KiB；超限即 kill 并 fail-closed。
- 任何传输/解析失败都返回本地合成的 `blocked` 响应（`pi-extension-local-fallback/v1`），绝不放行。
- bridge 响应不含路径、命令或文件内容，只有 hash 与安全 findings。

## 验证

```bash
# 静态语法检查
node --check integrations/pi/preflight-bridge.ts
node --check integrations/pi/extension.ts

# 行为测试（真实 spawn Python bridge；从仓库根目录运行）
node --test integrations/pi/test/preflight-bridge.test.ts
```

## 已知限制

- bridge 是策略门禁而非沙箱：`bash -c "cat .env"` 这类间接读取不在 v1 阻断范围内。
- policy `command_rules` 基于正则，存在固有漏判/误判空间；rule 演进属于 policy 治理。
- 非四个默认工具的自定义工具一律 block（fail-closed），如需放行需独立设计。
- 官方字段核对来源：`packages/coding-agent/docs/extensions.md` 与
  `src/core/tools/{bash,read,write,edit}.ts`（earendil-works/pi，2026-07-25）。

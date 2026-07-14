# 78 — Stage 17 Control Panel Host Integration Boundary

> 状态：**第一拍已实现并收口**
> 基线：`v0.13.0-read-only-control-plane` / `f401b98`  
> 前置事实源：`docs/76-read-only-control-panel-mvp.md`、`docs/77-read-only-control-plane-milestone-freeze.md`

## 1. 决策摘要

Stage 17 不直接启动 live service，也不把静态 Control Panel 扩成可写 UI。第一拍选择：

> 为本地宿主定义一个**版本化、只读、stdio-first 的 Control Panel handoff contract**，让 Codex Desktop、QwenPaw 或其他受控宿主可以发现并消费现有 snapshot / HTML 表示，同时保持无网络、无后台服务、无文件写入、无真实 adapter execution。

推荐先新增：

```bash
python -m agent_runtime.cli orchestration control-panel handoff [--envelope PATH] --json
```

该命令只返回机器可读 descriptor，不内嵌 HTML、不写 artifact、不打开浏览器，也不执行 descriptor 中声明的命令。

## 2. 为什么是这一阶段

Stage 16 已经提供：

- `control-panel snapshot`：确定性、内容寻址的 JSON read model；
- `control-panel render`：从同一 snapshot 投影出的自包含静态 HTML；
- `orchestration contract inspect`：CLI capability discovery；
- 明确的 unavailable/request-scoped boundary。

目前缺口不在“再做一个 UI”，而在于宿主消费语义仍是隐式的：

- 宿主如何知道 snapshot 与 HTML 属于同一份输入；
- 如何声明 media type、encoding、renderer version 与只读保证；
- 如何在不依赖临时文件或 HTTP server 的前提下选择表示；
- 如何避免宿主把 descriptor 或页面中的候选命令误当成已授权执行计划。

Stage 17 先冻结这个边界，能够继续复用 Stage 13–16 的 read models，而不突破当前安全模型。

## 3. 方案对比

### 方案 A — 本地 stdio handoff descriptor（推荐）

宿主通过现有 CLI 子进程读取 JSON descriptor，再按需调用现有 snapshot 或 render 命令。

优点：

- 不新增 daemon、端口、会话或鉴权面；
- 不新增默认文件写入；
- 与现有 CLI automation contract/profile/workflow 边界一致；
- 适合桌面宿主、CI 和本地归档工具；
- 最容易做 deterministic、no-write、no-network 验证。

代价：

- 宿主仍需管理一次或两次短进程调用；
- 不提供实时刷新与长连接。

### 方案 B — 受控 artifact export（后续候选）

显式 `--commit` 创建新的 HTML + manifest 文件，禁止覆盖，并做写前/写后校验与失败回滚。

优点：适合离线分发和审计留档。  
代价：引入新的受控写入事务，需要独立设计、回归和路径边界；不应与第一拍混在一起。

### 方案 C — live HTTP service（继续延期）

引入本地 server、端口、session、auth、刷新和生命周期管理。

当前不选：它会显著扩大攻击面和维护面，且现阶段没有必须依赖实时服务的消费者需求。

## 4. V1 handoff descriptor 建议契约

建议 schema：

```text
control-plane/control-panel-handoff/v1
```

建议顶层字段：

| 字段 | 语义 |
|:---|:---|
| `status` | 复用现有状态语义；不以异常表达正常门禁结果 |
| `schema_version` | 固定为 handoff v1 |
| `handoff_id` | 对不含自身的 canonical safe payload 做 SHA-256 |
| `source` | 复用 snapshot 的安全 source 摘要；不得回显敏感输入 |
| `snapshot` | `snapshot_id`、snapshot schema、media type、encoding、命令入口 |
| `render` | `render_id`、renderer version、media type、encoding、自包含保证、命令入口 |
| `boundaries` | read-only / no-write / no-network / no-service / no-execution |
| `findings` | 复用并去重安全 finding；不得回显完整 secret |
| `next_action` | 结构化说明宿主可读取表示，但不得自动执行候选操作 |

### 4.1 identity 规则

- `snapshot_id` 必须直接复用 `build_control_panel_snapshot()` 的现有结果，不重算第二套 snapshot。
- `renderer_version` 建议固定为 `control-plane/control-panel-html/v1`。
- `render_id` 是**表示身份**而不是原始 stdout byte hash；建议对 `{snapshot_id, renderer_version}` 的 canonical JSON 做 SHA-256。
- `handoff_id` 对完整 descriptor（去掉 `handoff_id`）做 canonical SHA-256。
- 相同仓库输入与相同 envelope 重复调用必须 byte-equivalent。

### 4.2 representation 规则

- snapshot：`application/json; charset=utf-8`。
- render：`text/html; charset=utf-8`。
- descriptor 只声明命令入口与输入透传规则，不嵌入 HTML，也不执行命令。
- `--envelope` 若提供，snapshot、render 与 handoff 必须使用同一 source；未提供时继续诚实输出 scoped unavailable。
- 命令入口使用 argv 数组或等价结构，不输出 shell 拼接字符串，避免 quoting 与 command injection 歧义。

## 5. 第一拍实现范围

下一窗口按 TDD 完成以下最小切片：

1. 在 `tests/test_orchestration_control_panel.py` 先写失败测试，冻结 handoff schema、identity、determinism、source reuse、no-write 与无 HTML 内嵌。
2. 优先在 `agent_runtime/orchestration_control_panel.py` 复用现有 snapshot builder / renderer identity；除非模块职责明显失控，不新建平行聚合管线。
3. 在 `agent_runtime/cli.py` 新增 `orchestration control-panel handoff [--envelope ...] --json` 与紧凑 human output。
4. 将新命令加入现有 `control_panel_read` contract entry；默认 snapshot/render 输出保持兼容。
5. 同步 CLI surface / key flag 契约测试、`docs/10-cli-poc-usage.md`、digest、roadmap、README、AGENTS 与阶段 handoff。
6. 完成全量验证后新增 Stage 17 release notes；设计开始时不创建 tag。

建议不要在第一拍新增独立 JSON schema 文件；先沿用现有 dataclass + contract tests 的轻量 read-model 模式。若出现第二个独立消费者或 controlled export，再评估正式 schema 文件。

## 5.1 第一拍实现结果（2026-07-14）

当前工作区已按上述边界落地：

- 新增 `build_control_panel_handoff()` 与 `ControlPanelHandoff`，直接复用一次 `build_control_panel_snapshot()` 结果；
- 新增 `orchestration control-panel handoff [--envelope ...] --json` 与紧凑 human output；
- `snapshot_id` 直接复用 snapshot，`render_id` 固定由 `snapshot_id + control-plane/control-panel-html/v1` 生成；
- descriptor 使用 argv 数组并声明 `working_directory=project_root`，不内嵌 HTML，显式列出 scoped unavailable 与 no-write/no-network/no-service/no-execution 边界；
- project-local 绝对 envelope 路径在公开 source/argv 中归一化为 root-relative 路径，越界路径不回显；
- 新命令并入既有 `control_panel_read` contract entry，没有新增平行 capability；
- 单元与 CLI/manifest 契约测试已覆盖 identity、determinism、缺失/合法/非法 envelope、no-write、路径脱敏和 human/JSON 输出。

全量仓库验证证据与最终边界记录见 `docs/archive/release-notes/81-release-notes-stage17-control-panel-host-handoff.md`。

## 6. 验收标准

### 功能与契约

- `handoff --json` 返回固定 v1 shape 和稳定排序。
- `snapshot.snapshot_id` 与同输入的 `control-panel snapshot --json` 完全一致。
- `render.render_id` 只由 `snapshot_id + renderer_version` 决定。
- descriptor 不包含原始 HTML、ledger 原文、secret、credential 或绝对敏感路径。
- 未提供 envelope 时仍明确 `envelope_required` / request-scoped boundary。
- 非法 envelope 安全失败，无 traceback，无部分输出伪装为 pass。

### 安全与副作用

- 不写文件、draft 或 ledger。
- 不启动 server/background process。
- 不访问网络，不加载外部资源。
- 不执行 descriptor 中声明的命令或任何 adapter。
- 不引入 UI 写操作、approval resolve、commit、retry 或 fallback 按钮。

### 兼容性与验证

- 现有 `snapshot` / `render` 默认输出不变。
- 相同输入重复运行 byte-equivalent。
- 全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、pre-commit 与 `git diff --check` 全部通过。
- 若改动任何受控写模块，必须额外确认没有扩大写入面；本阶段正常情况下不应改动这些模块。

## 7. 明确延期

- HTML/manifest 文件 export 与 `--commit`；
- 自动打开系统浏览器；
- live HTTP/API、WebSocket、polling、watch mode；
- auth/session、DB、持久 Run/Report/Artifact collection；
- 在线 availability probe；
- UI controlled write；
- 真实 adapter 或外部命令执行；
- QwenPaw/Codex 专有耦合实现。

## 8. Tag 策略

- Stage 17 design gate 启动时不创建 tag。
- 第一拍仅新增 additive read-only handoff descriptor 时，优先用 Stage release notes 收口，不为单个小切片追补 tag。
- 只有当 host integration contract 与至少一个可验收消费者形成新的稳定能力包时，再按 `docs/64-versioning-governance.md` 评估下一里程碑 tag。

## 9. 下一窗口启动清单

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
git status --short --branch
```

阅读顺序：

1. `docs/000-stage-digest.md`
2. 本文
3. `tasks/handoff-2026-07-14.md`
4. `docs/77-read-only-control-plane-milestone-freeze.md`
5. `docs/76-read-only-control-panel-mvp.md`
6. `docs/75-cli-automation-contract-discovery.md`

然后先写 handoff 失败测试，不要先改 CLI 实现。

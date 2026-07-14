# Stage 17 Release Notes — Control Panel Host Handoff

- 日期：2026-07-14
- 阶段：Stage 17 — Control Panel Host Integration Boundary
- 基线：`v0.13.0-read-only-control-plane` / `f401b98`
- Tag：本阶段不创建新 tag

## 1. 收口摘要

Stage 17 在不引入 service、网络、文件 export 或 UI 写操作的前提下，为 Stage 16 Control Panel 增加了版本化、stdio-first 的宿主 handoff descriptor：

```bash
python -m agent_runtime.cli orchestration control-panel handoff [--envelope PATH] --json
```

输出 schema 固定为 `control-plane/control-panel-handoff/v1`。descriptor 只描述现有 snapshot 与 HTML representation，不内嵌 HTML，也不执行所声明的 argv。

## 2. 契约与身份

- `snapshot.snapshot_id` 直接复用 `build_control_panel_snapshot()`，不建立第二套聚合或 identity。
- renderer version 固定为 `control-plane/control-panel-html/v1`。
- `render.render_id` 对 `{snapshot_id, renderer_version}` 的 canonical JSON 做 SHA-256。
- `handoff_id` 对不含自身的完整 descriptor 做 canonical SHA-256。
- snapshot representation 声明 `application/json; charset=utf-8` 与 `utf-8`。
- render representation 声明 `text/html; charset=utf-8`、`utf-8` 与 `self_contained=true`。
- 命令入口使用 argv 数组并声明 `working_directory=project_root`，不输出 shell 拼接字符串或绝对工作区路径。

## 3. Scoped boundary

- 未提供 `--envelope` 时，runs、approvals、artifacts 显式列出 `envelope_required`。
- reports 始终保持 request-scoped，并列出 `request_context_required`。
- 合法 envelope 复用同一个 safe source；snapshot、render 与 handoff identity 保持跨入口一致。
- project-local 绝对 envelope 路径归一化为 root-relative 路径；越界绝对路径不会出现在公开 source 或 argv。
- 非法 envelope 返回结构化 error descriptor 与安全 finding，不输出 traceback 或完整敏感值。

## 4. CLI 与 contract discovery

- 新增 `orchestration control-panel handoff` 的 JSON 与紧凑 human output。
- 新命令加入既有 `control_panel_read` contract entry。
- contract entry 仍为 `preview` / `read_only`，`--envelope` 仍是唯一关键业务 flag。
- argparse surface 与 machine-readable manifest 的一致性由契约测试冻结。

## 5. 安全保证

本阶段保持：

- deterministic；
- read-only；
- no file/ledger write；
- no network；
- no service/background process；
- no command execution；
- no adapter execution；
- no browser open；
- no controlled-write UI action。

## 6. 兼容性

- 现有 `control-panel snapshot` 与 `control-panel render` 的默认命令和 representation 不变。
- 相同 root 与 envelope 重复调用 handoff 产生 byte-equivalent JSON。
- Stage 17 只增加 additive descriptor，不改变 `v0.13.0` 已冻结的受控写入边界。

## 7. 验证证据

收口使用以下 fresh commands：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

验收结果：全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check 与 pre-commit 均通过。

## 8. 明确未做

- 未启动 HTTP/API/WebSocket/watch service；
- 未创建 HTML/manifest 文件 export；
- 未自动打开浏览器；
- 未新增 auth/session/DB 或持久 Run/Report/Artifact collection；
- 未新增 UI commit/resolve/retry/fallback；
- 未执行真实 adapter；
- 未实现 Codex Desktop 或 QwenPaw 专有消费者。

## 9. 下一步

下一阶段先进入 **Stage 18 — Read-only Host Consumer Validation** design gate：选择一个真实、可验收的本地消费者，冻结 schema/identity 校验、error handling、刷新模型与“不自动执行 argv”门禁，再决定是否进入实现。

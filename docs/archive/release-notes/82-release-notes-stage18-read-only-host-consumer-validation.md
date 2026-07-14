# Stage 18 Release Notes — Read-only Host Consumer Validation

- 日期：2026-07-14
- 阶段：Stage 18 — Read-only Host Consumer Validation
- 稳定基线：`v0.13.0-read-only-control-plane` / `f401b98`
- Tag：本阶段不创建新 tag

## 1. 收口摘要

Stage 18 在 Stage 17 handoff descriptor 之外增加了一个真正与 producer 解耦的本地 reference consumer：

```bash
python -m agent_runtime.cli orchestration control-panel handoff --json | \
  python tools/control_panel_handoff_consumer.py
```

consumer 仅使用 Python 标准库，从 stdin 读取 `control-plane/control-panel-handoff/v1`，输出确定性的 `control-plane/control-panel-host-consumer-validation/v1`。它不导入 `agent_runtime`，不读取 representation，也不执行 descriptor argv。

## 2. 输入门禁

- 每个进程只读取一份 stdin document；
- 最大输入为 1 MiB，超限在 JSON parse 前拒绝；
- 空输入、非 UTF-8、非法 JSON、重复 object key 均结构化失败；
- 不接受文件、URL、socket、环境变量或 credential 参数；
- finding 不回显原始 descriptor、绝对路径、argv 或潜在 secret。

## 3. 独立契约校验

检查顺序固定为：

1. `document_shape`
2. `schema_version`
3. `producer_status`
4. `handoff_identity`
5. `render_identity`
6. `representations`
7. `argv`
8. `boundaries`

consumer 独立重算 canonical SHA-256 identity，严格检查 snapshot/render metadata、argv 字符串数组与只读安全边界。source path 同时按 POSIX 与 Windows 语义检查，拒绝绝对路径、盘符路径、Windows 根相对路径和 `..` 穿越。

## 4. 状态与退出码

- `pass` → `0`；
- producer 非 pass、unsupported schema、unsafe boundary → `blocked` / `2`；
- 输入、shape、identity 或 representation mismatch → `validation_failed` / `5`；
- stdin I/O 或不可恢复内部错误 → `error` / `1`。

输出包含固定 consumer id、source handoff id、ordered checks、safe findings、guarantees 与结构化 next action；不增加新的持久 identity。

## 5. 安全保证

本阶段保持：

- stdin-only；
- deterministic；
- read-only；
- no file/ledger write；
- no representation read；
- no network；
- no service/background process；
- no command/argv execution；
- no adapter execution；
- no producer implementation import。

## 6. 测试与验证

新增 `tests/test_control_panel_handoff_consumer.py`，覆盖合法 handoff、producer error、strict shape/schema、handoff/render identity、representation metadata、POSIX/Windows path boundary、argv、unsafe boundary、输入限制、duplicate key、确定性、脱敏和 no-side-effect。

真实 producer → consumer stdin 管道返回 `pass` / `0`。收口使用 fresh commands：

```bash
python -m pytest -p no:cacheprovider tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest -p no:cacheprovider tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

验收结果：全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check、pre-commit 与真实 stdin 管道均通过。

## 7. 明确未做

- 未实现 Codex Desktop、QwenPaw 或其他专有宿主 bridge；
- 未自动读取 snapshot/HTML representation；
- 未执行 descriptor argv；
- 未增加文件输入、export、browser open、watch/polling；
- 未启动 live HTTP/API/WebSocket service；
- 未增加 auth/session/DB、UI controlled write 或真实 adapter execution。

## 8. 下一步

Stage 19 先进入 **Host-specific Read-only Adapter Design Gate**：选择一个真实宿主，冻结 descriptor/validation result 的接入方式、生命周期、错误映射、刷新策略和授权边界。design gate 未冻结前不直接实现专有 bridge。

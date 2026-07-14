# 79 — Release Notes：Stage 16 Read-only Control Panel MVP

## 阶段结论

Stage 16 第一拍已完成并收口：项目现在可以在不服务化、不联网、不写入、不执行 adapter 的前提下，把既有 orchestration read models 聚合成确定性 snapshot，并渲染为单文件、自包含的本地只读 Control Panel。

本阶段收口提交：`b46c013`（`Complete Stage 16 read-only control panel`）。

## 新增能力

### Control Panel Snapshot

```bash
python -m agent_runtime.cli orchestration control-panel snapshot --json
python -m agent_runtime.cli orchestration control-panel snapshot \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

- schema：`control-plane/control-panel-snapshot/v1`；
- `snapshot_id`：对规范化安全 payload 计算 SHA-256；
- 固定 section 顺序：overview、tasks、adapters、automation、runs、approvals、artifacts、reports；
- findings 去重，并保留结构化 `next_action`；
- 不传 envelope 时 scoped 区段诚实标记 unavailable。

### Self-contained HTML Render

```bash
python -m agent_runtime.cli orchestration control-panel render \
  --envelope adapters/execution-envelope.examples.json \
  > control-panel.html
```

- HTML 从 `<!doctype html>` 开始，只写 stdout；
- 无外部资源、网络请求或服务依赖；
- 所有 read-model 字符串转义；
- CSP meta、skip link、语义 heading、table caption、focus-visible、reduced-motion、响应式布局；
- 全局过滤完全在本地执行；
- 不包含写入或执行控件。

## 复用与契约

- 直接复用 `check_overview()`、`list_tasks()`、`list_adapters()`、`build_contract_manifest()`、`list_automation_profiles()`、`list_runs()`、`list_approvals()`、`list_artifacts()`。
- contract manifest 新增 `control_panel_read`（preview/read_only）。
- argparse surface 新增 `control-panel snapshot/render`，`--envelope` 与 manifest key flag 由契约测试冻结。
- 既有命令默认输出未改变。

## 安全边界

本阶段没有引入：

- live HTTP/API/server/background process；
- auth/session、DB、持久 collection；
- 网络访问或外部资源；
- UI controlled write；
- 真实 adapter/command execution；
- 独立 Report collection。

## 测试与验证

新增 `tests/test_orchestration_control_panel.py`，覆盖：

- no-envelope / explicit-envelope；
- invalid envelope 安全 failure；
- schema、section order、summary 与内容寻址 id；
- determinism 与 no-write；
- HTML escaping、CSP、无外链资源；
- CLI snapshot/render 确定性与 human output。

同时更新 orchestration boundary/contract tests，冻结新增 command path、subcommand 与 `--envelope`。真实 headless Chromium 已验证 8 个 section、过滤交互、无 console/page error，并生成 screenshot。

收口命令：

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

## 后续边界

Stage 16 MVP 收口后不自动扩张。live service、auth、DB、实时刷新、在线 availability、UI controlled write 与真实 adapter execution 必须由明确消费者需求和新的设计 gate 驱动。

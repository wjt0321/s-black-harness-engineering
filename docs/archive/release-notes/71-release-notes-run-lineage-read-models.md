# 71 — Release Notes：Run Lineage / Recovery Read Models

## 阶段定位

本阶段承接：

- `docs/70-orchestration-run-retry-fallback-commit-design.md`
- 已落地的 retry / fallback commit 第一版

在上一阶段完成 retry/fallback 的 lineage-aware 受控写入之后，本阶段补的是**只读侧的可见性闭环**：让现有 orchestration read models 能稳定、脱敏地读出 recovery lineage，而不只是把 lineage 写进 envelope / event metadata 后无人消费。

本阶段仍然不放开真实 adapter execution，不访问网络，不发送消息，不引入独立 Run storage、DB、service 或 UI。

## 已实现能力

### 1. `orchestration run inspect` 可见 lineage

当 envelope 中的 `adapter_request.context` 含有 recovery lineage 时，`orchestration run inspect` 现在会输出：

- `lineage_type`
- `retry_of`
- `fallback_from`
- `fallback_to`

输出原则：

- 仅在字段存在且非空时输出
- 普通 run 不会带空 lineage 字段
- 不回显完整 payload / target / raw refs

### 2. `orchestration run list` 可见 lineage

`orchestration run list` 现在会在每条 run 摘要中带出紧凑 lineage 标识：

- 普通 run：保持原有摘要，不误标
- retry run：显示 `lineage_type=retry` 与 `retry_of`
- fallback run：显示 `lineage_type=fallback` 与 `fallback_from` / `fallback_to`

这让恢复性 run 在 list 视图中第一次具备可区分性。

### 3. `orchestration report generate` 补 lineage 安全摘要

report 路径现在也能看见 lineage 安全摘要：

- 结果对象带出 lineage 字段
- `status_summary` 能紧凑提示当前 run 是否属于 retry / fallback
- 仍保持不暴露 target 原文、payload、raw refs

### 4. 复用既有 envelope summary 逻辑

本阶段没有为 lineage 另起一套读取管线，而是把字段下沉到现有 envelope / artifact summary 逻辑中：

- `runtime_draft` 负责从 `adapter_request.context` 提取安全 lineage 字段
- `run inspect` / `run list` / `report generate` 复用这份安全摘要

这样做的好处是：

- 不需要新存储
- 不需要额外扫 event ledger 才能看见 lineage
- 避免在多个 read model 中复制 lineage 解析逻辑

## 修改范围

核心代码：

- `agent_runtime/runtime_draft.py`
- `agent_runtime/orchestration_run.py`
- `agent_runtime/orchestration_report.py`
- `agent_runtime/cli.py`

测试：

- `tests/test_orchestration_run_inspect.py`
- `tests/test_orchestration_run_list.py`
- `tests/test_orchestration_report.py`

文档：

- `docs/10-cli-poc-usage.md`
- `docs/71-release-notes-run-lineage-read-models.md`

## 保持不变的边界

本阶段仍然不开放：

- 真实 adapter execution
- 网络访问
- 消息发送
- 独立 Run storage
- 新 event type / schema enum 扩张
- approval 自动复用
- payload / target 原文输出

lineage 只是读模型增强，不改变任何写入语义。

## 验证

本阶段已完成并复核以下验证：

```bash
python -m pytest tests/test_orchestration_run_inspect.py tests/test_orchestration_run_list.py tests/test_orchestration_report.py -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

验证结果：

- lineage read model 相关测试：通过
- `doctor`：PASS
- `public_scan`：OK public scan
- `git diff --check`：通过（LF/CRLF 提示不属于空白错误）

## 当前结论

到这一阶段为止，项目已经形成了一个更完整的 recovery 闭环：

- retry / fallback lineage 可以被写入
- retry / fallback lineage 可以被 inspect/list/report 读取
- 读写两侧都维持脱敏和受控边界

也就是说，recovery lineage 现在已经不再只是 ledger/envelope 里的“暗数据”，而成为 control-plane read model 的第一等信息。

## 下一步建议

本阶段完成后，下一步更自然的方向是二选一：

1. 设计更细的 recovery state / lineage read model 聚合（例如 attempt chain、source/descendant 关系）
2. 继续收紧 report / run list 的 recovery 摘要规则，但仍不进入真实执行

默认建议先继续做 recovery lineage 的聚合视图设计，再决定是否需要新的 event 语义。
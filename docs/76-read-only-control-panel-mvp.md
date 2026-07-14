# 76 — Stage 16 Read-only Control Panel MVP

<!-- parents: 47-orchestration-hub-vision.md, 51-backend-first-api-boundary.md -->
<!-- relates: 54-backend-preparation-before-ui.md, 75-cli-automation-contract-discovery.md -->

## 1. 结论

Stage 16 第一版选择 **local static read-only control panel**：复用现有 Python read models 生成确定性 snapshot，再渲染为单文件、自包含 HTML。CLI 只把 HTML 写到 stdout；用户可自行重定向到文件并用浏览器打开。

本阶段不选择：

- live HTTP server：会引入长期 service、端口、生命周期和 auth 问题；
- React/Vue SPA + API：会新增构建栈与协议面，倒逼后端临时补洞；
- DB-backed dashboard：会把现有 ledger/read model 升级为新存储；
- UI 内 commit / approval resolve：会扩大放权面，首版没有必要。

## 2. 用户与场景

目标用户是本地维护者、审计者和未来宿主集成开发者。首版回答：

1. 当前 task/event 总体状态是什么；
2. 有哪些 adapter 与自动化 profile；
3. 指定 envelope 中有哪些 run、approval 和 artifact；
4. 哪些页面因为 envelope/request scope 尚不可用；
5. 当前展示是否来自确定性、只读、无网络的 projection。

## 3. CLI

```bash
python -m agent_runtime.cli orchestration control-panel snapshot --json
python -m agent_runtime.cli orchestration control-panel snapshot \
  --envelope adapters/execution-envelope.examples.json \
  --json
python -m agent_runtime.cli orchestration control-panel render \
  --envelope adapters/execution-envelope.examples.json \
  > control-panel.html
```

- `snapshot` 输出 `control-plane/control-panel-snapshot/v1`；
- `render` 只向 stdout 输出 `<!doctype html>` 开头的完整 HTML；
- 两个入口都接受可选 `--envelope`；不传时 runs/approvals/artifacts 标记为 `unavailable`，但 overview/tasks/adapters/automation 仍可用；
- 不提供 `--output`、`--commit`、server、watch 或 background 参数。

## 4. Snapshot v1

顶层字段：

- `status`；
- `schema_version`；
- `snapshot_id`：canonical safe payload 的 SHA-256；
- `source.envelope_file`：显式传入时记录路径，未传时为 `null`；
- `summary`：task、blocked、adapter、run、pending approval、artifact、profile 数量，以及 section status；
- `sections`：固定顺序的 overview、tasks、adapters、automation、runs、approvals、artifacts、reports；
- `findings` / `next_action`：源 read model 失败时的去重安全诊断；
- `guarantees`：deterministic、read_only、no writes/network/commands/adapters/service。

数据复用：

- overview：`check_overview()`；
- tasks：`list_tasks()`；
- adapters：`list_adapters()`；
- automation：`build_contract_manifest()` + `list_automation_profiles()` 的摘要；
- runs：`list_runs()`；
- approvals：`list_approvals()`；
- artifacts：`list_artifacts()`；
- reports：保持 request-scoped boundary callout，不伪造 collection。

## 5. UI 方向

视觉采用 **industrial audit console**：深墨色背景、暖琥珀主强调、冷青状态线、密集但清晰的审计表格。重点不是“漂亮卡片”，而是让来源、状态、scope 与不可用边界一眼可见。

HTML 必须：

- 自包含 CSS/JS，无外链字体、图片、脚本或网络请求；
- 提供 skip link、语义 heading、table caption、focus-visible 和 reduced-motion；
- 支持全局本地过滤，不发送数据；
- 对所有 read-model 字符串做 HTML escaping；
- 使用 CSP meta 限制默认资源，只允许 inline style/script；
- 响应式支持窄屏；
- 不包含编辑、批准、commit、重试或执行按钮。

## 6. 状态与错误

- 未传 envelope：envelope-scoped sections 为 `unavailable`，顶层仍可 `pass`；
- 显式 envelope 校验失败：对应 sections 保留结构化 failure，顶层提升为最严重状态；
- 重复 envelope finding 去重；
- reports 固定显示 stable_limited/request-scoped boundary，不影响顶层 pass；
- HTML 即使展示 failure 也只渲染安全 finding，不回显 raw payload、input、secret 或 evidence 正文。

## 7. 验收标准

1. snapshot/schema/id/section order/summary 冻结；
2. no-envelope 与 explicit-envelope 两条路径均测试；
3. invalid envelope、determinism、no-write、escaping、no-external-resource 测试；
4. argparse surface 与 manifest command/flag 契约同步；
5. HTML 在真实 headless Chromium 中通过 DOM、搜索交互、console error 和 screenshot 验证；
6. 全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check、pre-commit 全通过；
7. release notes、digest、roadmap、README、AGENTS 与 handoff 标记 Stage 16 Read-only Control Panel MVP 已收口。

## 8. 明确延期

- live server/API/auth/session；
- DB 与独立 Run/Report/Artifact collection；
- UI 内 controlled write；
- 实时刷新、WebSocket、轮询和在线 availability probe；
- 真实 adapter execution；
- report collection 页面与字段级旧 plan diff。

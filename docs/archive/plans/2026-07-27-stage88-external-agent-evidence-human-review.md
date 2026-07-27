# 真实执行证据回收与人工审阅闭环实施计划

> 状态：已执行并归档（2026-07-27）。所有实现、真实验收和验证项均已完成。

**Goal:** 为 Pi/OMP 单工作项执行增加真实宿主事件、不可变文本/JSON产物、可恢复证据归档和人工审阅结果闭环。

**Architecture:** 宿主扩展只返回固定有界事件和最终文本；Python 侧重新校验、扫描并写入 `.runtime/external-agent-evidence/v1` 不可变证据包。人工审阅使用绑定证据摘要的预览/确认写入，读取模型与中文控制面板从不可变记录派生状态。

**Tech Stack:** Python 3.11+ 标准库、jsonschema、pytest、Node/CommonJS 宿主扩展、现有 argparse CLI 与只读控制面板。

## Global Constraints

- 用户可见 UI/UX 默认使用简体中文。
- 只允许已打开、空闲、空工具的 `pi-local` 与 `omp-local`。
- 不读取或回显 `.env`、令牌、密钥环、私钥或敏感匹配原文。
- 不开放任意文件路径、工具、命令、网络、重试、并发、服务或数据库。
- 所有路径必须 containment 校验；所有输入输出有界并失败关闭。
- 真实执行保持 started audit 先写和唯一 terminal audit。
- 受控写入执行写前校验、写后校验、失败清理或可恢复 pending。
- 未获得用户明确授权前不提交、不推送。

---

### Task 1: 版本化宿主结果与真实事件链

**Files:**
- Create: `adapters/external-agent-single-work-item-result.schema.json`
- Modify: `integrations/pi_omp_live_status/controlled_dispatch.cjs`
- Modify: `tests/test_single_work_item_dispatch_execution.py`

**Interfaces:**
- Produces: `external-agent-single-work-item-result/v2`，含 `events`、`output`、宿主状态与固定失败码。
- Consumes: 现有邮箱请求 v1、请求身份摘要、结果大小上限。

- [x] 增加失败测试：成功、忙碌、工具活动、超时和宿主关闭产生合法固定事件链。
- [x] 运行定向测试并确认因缺少事件协议失败。
- [x] 实现宿主事件记录器，限制事件类型、数量、字段和递增序号。
- [x] 增加结果 JSON Schema 和 Python 侧 schema 加载入口。
- [x] 运行定向测试，确认事件链和旧阶段87安全拒绝行为通过。

### Task 2: 不可变证据存储与恢复事务

**Files:**
- Create: `adapters/external-agent-evidence-manifest.schema.json`
- Create: `adapters/external-agent-review-record.schema.json`
- Create: `agent_runtime/external_agent_evidence_store.py`
- Create: `tests/test_external_agent_evidence_store.py`

**Interfaces:**
- Produces: `prepare_evidence(...)`、`finalize_evidence(...)`、`recover_pending_evidence(...)`、`inspect_evidence(...)`。
- Consumes: 已验证执行结果、执行尝试编号、协作工作项和计划摘要。

- [x] 先写路径逃逸、符号链接、硬链接、超限、摘要冲突和重复归档失败测试。
- [x] 运行测试并确认尚无存储实现。
- [x] 实现固定目录、原子临时写、独占创建、内容寻址和写后校验。
- [x] 实现 pending 事务与无需重跑 Agent 的固定恢复。
- [x] 实现证据读取和确定性事件投影。
- [x] 运行存储测试并确认全部通过。

### Task 3: 将证据归档接入单工作项执行

**Files:**
- Modify: `agent_runtime/orchestration_single_work_item_execution.py`
- Modify: `adapters/single-work-item-execution-request.schema.json`（仅在需要兼容声明产物类别时做向后兼容扩展）
- Modify: `tests/test_single_work_item_dispatch_execution.py`
- Modify: `tests/test_controlled_write_regression.py`

**Interfaces:**
- Produces: 成功结果中的 `evidence` 摘要、不可变产物、待审阅状态或已完成状态。
- Consumes: Task 1 的宿主结果和 Task 2 的存储接口。

- [x] 增加执行成功归档、审阅门禁缺失/歧义、秘密扫描失败不归档、终态失败保留 pending 的测试。
- [x] 运行定向测试并确认失败。
- [x] 在预览中绑定预期产物类别和唯一审阅门禁。
- [x] 在输出扫描后准备 pending，在终态审计后完成证据归档。
- [x] 保持失败终态唯一、租约释放和请求不可重放语义。
- [x] 运行单工作项与受控写入回归测试。

### Task 4: 人工审阅预览与一次性提交

**Files:**
- Create: `agent_runtime/orchestration_external_agent_review.py`
- Create: `tests/test_orchestration_external_agent_review.py`
- Modify: `agent_runtime/cli.py`

**Interfaces:**
- Produces: `build_external_agent_review_plan(...)`、`commit_external_agent_review(...)`，决定仅为 `approve` 或 `request_changes`。
- Consumes: 不可变执行清单、产物摘要、协作计划、审阅门禁和安全扫描服务。

- [x] 增加预览绑定、正确提交、错误摘要、漂移、重复决定、意见超限/秘密和已完成尝试拒绝测试。
- [x] 运行定向测试并确认失败。
- [x] 实现确定性计划摘要和一次性确认摘要。
- [x] 实现不可变审阅记录写入与写后 schema/摘要校验。
- [x] 增加中文 CLI 与 `--json` 输出。
- [x] 运行审阅测试并确认通过。

### Task 5: 证据读取、恢复命令与中文控制面板

**Files:**
- Create: `agent_runtime/orchestration_external_agent_evidence.py`
- Create: `tests/test_orchestration_external_agent_evidence.py`
- Modify: `agent_runtime/cli.py`
- Modify: `agent_runtime/orchestration_control_panel.py`
- Modify: `tests/test_orchestration_control_panel.py`

**Interfaces:**
- Produces: 按尝试编号查看证据、恢复 pending、控制面板中文证据卡片。
- Consumes: Task 2 存储读取结果与 Task 4 审阅记录。

- [x] 增加证据不存在、待恢复、等待审阅、已通过和要求修改的读取测试。
- [x] 增加恢复不会调用 Pi/OMP、不会覆盖已归档证据的测试。
- [x] 实现中文 CLI 摘要和稳定失败码。
- [x] 将真实事件、产物和审阅状态接入控制面板只读投影。
- [x] 运行读取与控制面板测试。

### Task 6: 真实 Pi/OMP 验收、文档治理与完整验证

**Files:**
- Create: `adapters/collaboration-plan.stage88-pi-review-smoke.json`
- Create: `adapters/collaboration-plan.stage88-omp-review-smoke.json`
- Create: `adapters/single-work-item-execution-request.stage88-pi-review-smoke.json`
- Create: `adapters/single-work-item-execution-request.stage88-omp-review-smoke.json`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `docs/10-cli-poc-usage.md`
- Modify: `docs/130-gui-first-external-agent-control-plane-target.md`
- Modify: `AGENTS.md`（仅更新当前能力边界，不写阶段流水）
- Archive with `git mv`: 本设计与实施计划到 `docs/archive/`

**Interfaces:**
- Produces: Pi/OMP 真实证据、人工通过与要求修改记录、下一阶段明确断点。

- [x] 运行所有新增 Python/Node 定向测试。
- [x] 使用已打开的 Pi 完成一次需人工审阅执行并提交“通过”。
- [x] 使用已打开的 OMP 完成一次需人工审阅执行并提交“要求修改”。
- [x] 关闭并重新运行 CLI，确认事件、产物和审阅可恢复读取。
- [x] 更新核心文档并将设计/计划归档，检查索引与活跃文档数。
- [x] 运行 `python -m pytest tests -q`。
- [x] 运行 `python -m pytest tests/test_controlled_write_regression.py -q`。
- [x] 运行 `python -m agent_runtime.cli doctor`。
- [x] 运行 `python tools/public_scan.py`。
- [x] 运行 `git diff --check`。
- [x] 在可用环境运行 `bash .githooks/pre-commit`。
- [x] 检查 `git status` 和完整差异；没有用户明确授权时停止在未提交状态。

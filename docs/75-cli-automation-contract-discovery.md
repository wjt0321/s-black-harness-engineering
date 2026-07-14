<!-- parents: 51-backend-first-api-boundary.md, 52-minimal-orchestration-loop.md -->
<!-- relates: 02-roadmap.md, 10-cli-poc-usage.md -->

# 75 — CLI 自动化契约发现

## 定位

本增量把 Stage 13 已冻结、Stage 14 已验证的 `stable` / `stable_limited` / `preview` / `unavailable` 边界投影为机器可读的本地 CLI manifest，供脚本、CI 和未来宿主在调用 orchestration 命令前做能力发现。

它不是 HTTP discovery endpoint，不新增服务、数据库、鉴权或持久资源，也不改变任何既有命令的默认输出。

## 方案选择

候选方案：

1. 新增显式只读契约发现命令；
2. 给所有既有 JSON 输出追加统一版本字段；
3. 新增自动串联 routing / preflight / run / report 的批处理命令。

选择方案 1。原因是它不破坏默认输出兼容，不复制编排计算，并能以最小增量为 CLI 自动化提供稳定的 capability negotiation 入口。

## CLI 边界

新增：

```bash
python -m agent_runtime.cli orchestration contract inspect --json
```

人类可读模式输出契约版本、条目数量和每个条目的 availability/access/command 摘要；`--json` 输出完整 manifest。

命令只读取代码内冻结的安全元数据，不读取 ledger、adapter registry、环境变量或凭据，不写文件，不访问网络。

## Manifest v1

顶层字段：

- `status`: 固定为 `pass`；
- `schema_version`: `control-plane/orchestration-contract/v1`；
- `consumer`: `cli-automation`；
- `entries`: 按 `contract_id` 确定性排序的契约条目；
- `summary`: 各 availability 分类计数；
- `guarantees`: no-write、no-network、no-adapter-execution 和 deterministic 声明。

每个条目字段：

- `contract_id`: 稳定机器标识；
- `availability`: `stable`、`stable_limited`、`preview` 或 `unavailable`；
- `access`: `read_only`、`controlled_write` 或 `unavailable`；
- `commands`: 可用入口的 argv 片段列表；不可用能力必须为空列表；
- `key_flags`: 影响 preview、commit、lineage、replay 等边界的关键 flag；
- `boundary`: 简短安全边界，不包含路径、payload、secret 或运行时数据。

v1 覆盖 `docs/51-backend-first-api-boundary.md` 的首轮契约矩阵，不声称存在独立 Run/Report collection、orchestration Artifact export 或真实 adapter execution。

## 实现约束

- 新模块只定义 immutable source entries 和确定性 projection；
- production manifest 不通过解析 argparse help 动态生成，避免把展示文案误当事实源；
- 契约测试反向校验所有非 unavailable command path 都真实存在于 argparse surface，防止 manifest 与 CLI 漂移；
- 新命令是显式新增 surface，既有命令与默认 JSON 保持不变；
- 不新增 JSON Schema 文件，`schema_version` 仅作为 DTO 版本标识。

## TDD 与验收

1. 先增加失败测试，冻结 manifest 字段、排序、分类计数和 unavailable 空命令约束；
2. 增加 CLI JSON / human-readable / determinism / no-write 测试；
3. 更新 Stage 13 surface contract 测试并验证新增 `contract inspect`；
4. 最小实现 `agent_runtime/orchestration_contract.py` 与 CLI wiring；
5. 更新 `docs/00-index.md`、`docs/10-cli-poc-usage.md`、`docs/000-stage-digest.md` 和 roadmap；
6. 运行全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check 与 pre-commit。

## 明确不做

- 不自动执行 manifest 中的命令；
- 不新增 batch workflow；
- 不读取在线 availability；
- 不把 preview 升级为 stable；
- 不引入服务协议、UI、数据库、鉴权或真实 adapter execution。

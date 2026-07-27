# 阶段 87：单工作项受控执行闭环实施计划

> 日期：2026-07-27
> 状态：已完成
> 目标：在不开放通用命令、任意参数或后台自治的前提下，让已由用户打开的 Pi/OMP 会话接收一个经一次性人工确认的工作项，并回收有界结果、审计和恢复证据。

## 一、不可突破的边界

1. 只支持 `pi-local`、`omp-local` 两个固定目标配置。
2. Harness 不启动、关闭或重启 Pi/OMP，不执行任意 shell，不接收 cwd/env/argv 覆盖。
3. 每次只允许一个全局执行；复用现有执行租约。
4. 预览绝不写入或执行；提交必须同时带 `--commit` 和预览产生的精确确认摘要。
5. 确认摘要绑定任务、协作计划、工作项、目标配置、指令摘要、输入产物摘要、实时状态证据、超时和结果上限。
6. 同一 `request_id` 只能进入一次 started audit；任何重放都失败关闭。
7. started audit 成功后才能发布任务；每个 started attempt 最终只允许一个 terminal audit。
8. 请求和原始结果仅存在于 gitignored 的 `.runtime/`；均为项目内固定路径、普通文件、单硬链接、原子替换和 64 KiB 以内。
9. 扩展只调用宿主的 `sendUserMessage`，不得调用 `exec`、改变工具集合或读取会话历史。
10. 原始结果经 Python 侧有界读取和敏感信息扫描后才允许释放；命中时只返回规则编号和安全提示。
11. 不自动重试、不并行派发、不跨 Agent 转发、不形成自治循环。

## 二、固定协议

### 2.1 受控执行请求

新增版本化 JSON 请求，必须包含：

- 现有任务账本中的 `task_id`；
- 唯一 `request_id`；
- 协作计划文件、计划摘要和 `work_item_id`；
- 计划中的 `socket_id` 与固定 `target_profile`；
- 有界中文/文本指令及其摘要；
- 0-8 个项目内输入产物路径、类型、大小和 SHA-256；
- 1-900 秒超时；
- 最大 32 KiB 的结果上限；
- 当前 Pi/OMP 状态快照的生产者、代次、观察时间和摘要；
- 预览生成的 `approval_binding_id`。

### 2.2 项目级固定信箱

固定路径：

- `.runtime/external-agent-dispatch/pi-local.request.v1.json`
- `.runtime/external-agent-dispatch/pi-local.result.v1.json`
- `.runtime/external-agent-dispatch/omp-local.request.v1.json`
- `.runtime/external-agent-dispatch/omp-local.result.v1.json`

Python 执行端写临时文件、校验、原子替换；宿主扩展轮询对应单一请求文件，校验独立派发绑定、期限、目标、摘要和状态代次后再调用 `sendUserMessage`。扩展以 `agent_start`、`agent_end`、`session_shutdown` 事件形成接受、成功或失败结果，不读取历史会话。

### 2.3 独立派发绑定

只读状态绑定继续保持 `dispatch_authorized=false`。新增独立的 `external-agent-dispatch-binding/v1`，绑定：

- 目标配置与固定请求/结果路径；
- 扩展实现摘要；
- 协议版本、大小、期限和轮询上限；
- 只允许 `sendUserMessage`；
- 明确禁止 `exec`、工具权限变更、宿主进程管理和网络访问。

## 三、实现顺序

1. 新增请求与派发绑定 schema、Pi/OMP 固定绑定和样例。
2. 先写 Python 预览/提交失败测试：路径越界、计划漂移、任务不匹配、状态过期、摘要不匹配、确认缺失、重放、租约冲突、超时和结果超限。
3. 实现 Python 只读计划构建器，输出稳定 `approval_binding_id`。
4. 实现提交执行器：预检、租约、started audit、原子发布、等待、结果校验、敏感信息扫描、terminal audit、清理。
5. 先写 Node 扩展失败测试，再实现固定信箱消费者和结果发布器。
6. 将 Pi/OMP 极薄入口接到共享消费者；更新实现摘要绑定。
7. 增加 CLI 确定性 JSON 入口和简体中文控制面板操作区。
8. 覆盖断连、超时、宿主关闭、重复请求、错误结果、审计失败与恢复。
9. 用户打开 Pi/OMP 后，分别执行一条无工具、无文件写入的真实验收指令，确认连接、接受、结果、关闭和审计。
10. 更新 `docs/000-stage-digest.md`、`docs/00-index.md`、`docs/02-roadmap.md`、`docs/10-cli-poc-usage.md`、`docs/130-gui-first-external-agent-control-plane-target.md`，完成后将本计划与阶段事实源 `git mv` 到 archive。

## 四、验证

至少执行：

```bash
python -m pytest tests/test_single_work_item_dispatch_execution.py -q
python -m pytest tests/test_pi_omp_controlled_dispatch_integration.py -q
python -m pytest tests/test_controlled_write_regression.py -q
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
bash .githooks/pre-commit
```

未完成 Pi/OMP 真实验收、全量测试或终端审计闭合前，不得宣布阶段完成。

## 五、完成结果

- Pi 与 OMP 的固定单工作项真实验收均成功；
- 一次性确认、全局租约、started/terminal 审计、重放阻止、有界结果和敏感信息扫描链路已完成；
- OMP 17.0.8 的项目本地 MCP 隔离和空闲启动轮次兼容已验证；
- 阶段事实源与本计划在完成全量验证后归档。

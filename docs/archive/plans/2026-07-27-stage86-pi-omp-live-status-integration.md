# 阶段 86：Pi/OMP 真实状态接入实施计划

> **状态：已执行完成并归档。** 全部任务、真实连接/关闭验收和最终回归均按本计划收口。

**目标：** 让 Pi 与 OMP 在本项目中通过各自的进程内扩展发布安全原子快照，并由现有读取器和中文控制面板展示真实只读状态。

**架构：** 在 `.pi/extensions/` 与 `.omp/extensions/` 放置极薄的项目级扩展入口，共用 `integrations/pi_omp_live_status/publisher.cjs`。扩展只监听宿主生命周期事件，使用固定绑定、单写者租约、5 秒心跳和原子替换写入 `.runtime/external-agent-status/`。Harness 只读取两个经过审阅的固定目标，不启动 Agent、不读取环境变量、不访问网络、不发送提示词。

**技术栈：** Python 3.11+、pytest、Node.js 内置模块、Pi/OMP extension lifecycle、JSON Schema。

---

## 任务 1：冻结 Pi/OMP 固定身份与安全快照契约

- 新增 Pi、OMP 两份固定 binding；不得接受路径、producer、transport 任意覆盖。
- producer binding id 必须绑定公共发布器与对应扩展入口的内容摘要。
- 先写 schema/binding/内容摘要失败测试，再生成 reviewed digest。

## 任务 2：实现进程内被动发布器

- 先写 Node 行为测试：session_start 发布、generation 前进、心跳、shutdown、租约冲突、半写恢复、内容摘要漂移。
- 实现项目级 Pi/OMP 扩展入口和公共发布器。
- 禁止读取 `process.env`、`process.argv`、session 文件、提示词、模型、工具输入或原始输出；禁止 `fetch`、socket、child_process。

## 任务 3：扩展固定读取器

- 先写失败测试覆盖两个 reviewed target、缺失、过期、open session 和 identity drift。
- 将单一硬编码目标改为固定 profile 映射；仍禁止用户指定任意文件路径。
- 缺失快照映射为“未连接”，过期映射为“状态已过期”，open session 只显示观察到会话且不可派发。

## 任务 4：接入中文控制面板

- 先写 snapshot 与 HTML 失败测试。
- 控制面板只在提供显式评估时间时读取 Pi/OMP 固定快照，保持确定性。
- 新增“外部智能体 / 实时状态”区段，展示宿主、连接状态、观察时间、证据有效性和不可派发原因；不展示 PID、session id、端点或原始内容。

## 任务 5：联调、文档与收口

- 使用 Node 测试宿主事件链，不启动真实 Agent。
- 用户手动启动 Pi/OMP 后再执行真实只读 smoke；Harness 不代为启动。
- 更新 CLI、核心恢复文档、路线图和里程碑事实源。
- 运行专项测试、全量测试、doctor、public scan、diff check 和文档维护检查。

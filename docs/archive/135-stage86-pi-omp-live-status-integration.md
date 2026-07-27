# 135 — 阶段 86：Pi/OMP 真实只读状态接入

> 状态：已完成并归档。自动验证、真实连接态、关闭态、租约释放和过期映射均已通过。

## 1. 用户可见结果

阶段 86 把 Pi/OMP 的真实宿主生命周期接入中文控制面板：

```text
用户已经启动的 Pi / OMP
  -> 项目级进程内状态扩展
  -> 固定原子状态快照
  -> 严格安全读取器
  -> 中文控制面板“外部智能体 / 实时状态”
```

控制面板只显示：

- 智能体名称；
- 当前状态；
- 最后观察时间；
- 证据是否有效；
- 为什么不能派发；
- 明确的安全说明。

它不显示进程号、会话标识、端点、提示词、模型信息、工具输入或原始输出。

## 2. 本机核验结论

2026-07-27 的本机只读核验结果：

- Pi 安装包：`@earendil-works/pi-coding-agent` 0.82.0；项目扩展目录为 `.pi/extensions/`。
- OMP 启动器文件版本：1.3.14；当前内置 `@oh-my-pi/pi-coding-agent` 15.12.3，可核验项目扩展目录 `.omp/extensions/`。
- Pi 官方扩展加载器兼容验证通过：本项目扩展被加载，错误数为 0；该验证没有创建智能体会话或调用模型。
- 用户确认本机 QwenPaw 为 2.0.1。旧虚拟环境中的 1.1.12.post3 不属于当前桌面版本事实源，因此本阶段不再依赖它。
- 为降低复杂度，本阶段先完成 Pi/OMP；QwenPaw 只作为后续候选。

## 3. 实现组成

### 3.1 项目级扩展

- `.pi/extensions/s-black-live-status.ts`
- `.omp/extensions/s-black-live-status.ts`
- `integrations/pi_omp_live_status/publisher.cjs`

两个入口只固定各自身份，共用一个发布器。发布器只监听宿主生命周期事件，不读取 `process.env`、`process.argv`、会话文件、提示词、模型、工具输入或原始输出；也不使用网络、子进程或独立后台服务。

### 3.2 固定生产绑定

- `adapters/external-agent-live-status-binding.v2.schema.json`
- `adapters/external-agent-live-status-binding.pi-local.json`
- `adapters/external-agent-live-status-binding.omp-local.json`

生产者摘要同时绑定公共发布器和对应扩展入口。Python 读取器还固定审阅文档摘要；任一实现或绑定内容漂移都会失败关闭，必须重新审阅后才能使用。

### 3.3 原子发布与恢复

发布器使用：

- 固定 `.runtime/external-agent-status/` 路径；
- 单写者 `.lock` 租约，30 秒后才允许恢复陈旧租约；
- 默认 5 秒心跳；
- 单调递增的 `generation`；
- 固定临时文件、刷盘、严格校验、原子替换和写后校验；
- 64 KiB 最大文件限制；
- 宿主关闭时发布关闭态并清理租约。

任何绑定或发布错误都不会破坏 Pi/OMP 宿主本身。

### 3.4 安全读取器与中文控制面板

`orchestration external-agent status inspect` 只允许三个固定配置：

- `omp-acp`：保留阶段 84 的兼容行为；
- `pi-local`：Pi 项目扩展；
- `omp-local`：OMP 项目扩展。

`pi-local` 和 `omp-local` 的状态映射：

| 快照情况 | 中文状态 | 命令结果 |
|:---|:---|:---|
| 文件不存在 | 未连接 | 通过，退出码 0 |
| 有效且宿主活动 | 已连接，存在未绑定会话 | 通过，退出码 0 |
| 超过 15 秒未更新 | 状态已过期 | 只读返回，保持不可派发 |
| 身份、摘要、结构或文件稳定性异常 | 状态不可用 | 失败关闭 |
| 宿主正常关闭并发布关闭态 | 未连接 | 通过，退出码 0 |

“已连接”只表示观察到宿主活动，不证明模型可用、会话可映射或允许派发。所有证据始终保持 `sufficient_for_dispatch=false` 和 `execution_authorized=false`。

控制面板只有在调用方提供显式评估时间时才读取实时状态，避免静态快照因为系统时间而失去确定性。

## 4. 本地安全治理

- `.runtime/external-agent-status/` 已关闭继承权限，只允许当前用户、SYSTEM 和 Administrators 显式完全控制。
- `.runtime/` 仍为本机运行态并由 Git 忽略；不得提交快照、租约或任何运行原文。
- 真实联调发现 OMP 的扩展上下文没有 Pi 的 `isProjectTrusted()` 方法。发布器只对固定 `omp-local` 配置使用兼容分支；Pi 继续要求该方法存在且返回真。
- 生产者内容摘要和两份审阅绑定已随兼容修复重新生成，读取器中的审阅文档摘要同步更新。

## 5. 自动验证

已通过：

- 发布器开始、心跳、关闭和 generation 前进行为；
- 单写者租约与绑定失败不影响宿主；
- OMP 无 Pi 项目信任方法时仅固定 OMP 配置可发布，Pi 仍失败关闭；
- Python 严格读取器消费真实发布器生成的快照；
- 缺失快照映射为中文“未连接”；
- 活动快照显示已连接但仍不可派发；
- 中文控制面板投影和敏感字段隐藏；
- Pi 项目扩展真实加载兼容验证；
- Pi/OMP 未运行时的真实缺席态验证；
- 阶段 86 专项回归与全量 `pytest`；
- 受控写入回归、`doctor`、公开扫描、文档恢复、Python 编译、Markdown 链接、活跃文档数、提交前钩子和差异检查。

## 6. 真实连接与关闭验收

用户在仓库根目录手动启动 Pi 与 OMP，全程没有发送提示词、创建任务或调用模型。

连接态结果：

- Pi：显示“已连接，存在未绑定会话”，证据有效；
- OMP：显示“已连接，存在未绑定会话”，证据有效；
- 中文控制面板状态通过，两者均显示连接；
- `sufficient_for_dispatch=false`、`execution_authorized=false`；
- 页面未显示进程号、会话标识、端点或原始输出。

关闭态结果：

- Pi 最终快照 generation 68，`session_state=closed`；
- OMP 最终快照 generation 65，`session_state=closed`；
- 两个 `.lock` 租约均已释放；
- 超过固定 15 秒有效期后，两者均显示“状态已过期”；
- 控制面板仍保持只读通过和不可派发。

阶段 86 的真实产品验收至此完成。

## 7. 明确停止线

阶段 86 不包含：

- 由 Harness 启动 Pi、OMP 或 QwenPaw；
- 创建真实会话；
- 发送提示词、调用模型或启用工具；
- 主动连接 ACP；
- 派发工作项；
- 读取凭据或访问网络；
- 创建独立长期服务；
- 新增第三个 Harness 真实执行操作；
- 将状态证据解释为执行或派发授权。

## 8. 历史依据

- 阶段 84 读取器：`archive/133-stage84-bounded-atomic-snapshot-reader-implementation.md`
- 阶段 85 状态采集设计：`archive/134-stage85-external-agent-status-collection-design-review.md`
- 实施计划：`plans/2026-07-27-stage86-pi-omp-live-status-integration.md`
- 长期产品目标：`130-gui-first-external-agent-control-plane-target.md`

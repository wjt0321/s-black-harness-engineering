# 83 — Stage 20 Codex Desktop Read-only Adapter

> 日期：2026-07-15
> 状态：验收完成
> 设计前置：`docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`
> 实现事实源：`docs/archive/81-codex-desktop-read-only-adapter-implementation.md`

## 1. 交付内容

Stage 20 将 `codex-desktop-read-only-adapter/v1` 落地为：

```text
tools/codex_desktop_read_only_adapter.py
```

它以一次性、标准库-only、本地只读方式串联：

```text
固定 handoff producer
  -> stdout descriptor
  -> Stage 18 reference consumer
  -> stdout validation result
  -> host adapter result
```

## 2. 已冻结并实现的边界

- 只执行两条固定 argv，不执行 descriptor 的 `snapshot.argv` / `render.argv`；
- 每个子进程默认 30 秒，最大 60 秒；不自动重试；
- producer / consumer stdout 上限 1 MiB；
- cwd 固定为用户选择的 project root；
- project root 必须包含 `pyproject.toml` 与 `agent_runtime/`；
- 子进程环境使用最小白名单，不转发 credential、token、keyring 或任意用户环境变量；
- 输出 `control-plane/codex-desktop-read-only-adapter/v1`；
- 结果不回显绝对路径、原始 stderr、descriptor、argv 或敏感值；
- `ready` 只代表 handoff validation 通过，不代表 representation 已加载；
- 不读 HTML/JSON representation、不写文件/ledger/draft/artifact、不访问网络、不启动 service、不执行真实 adapter。

## 3. 状态与退出码

| adapter 状态 | 退出码 |
|:---|---:|
| `ready` | `0` |
| `error` | `1` |
| `blocked` | `2` |
| `validation_failed` | `5` |

consumer status 与退出码不一致、producer 非零但 consumer pass、空输出、超时、非法 JSON 或协议 drift 均 fail closed。

## 4. 测试证据

新增 `tests/test_codex_desktop_read_only_adapter.py`，覆盖：

- one-shot fixed producer/consumer pipeline；
- descriptor argv 不执行；
- determinism 与绝对路径脱敏；
- blocked / validation_failed / error 映射；
- malformed consumer result；
- project root 门禁；
- timeout no-retry；
- 真实本地 stdio smoke pipeline。

本阶段验收通过：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

## 5. 后续边界

Stage 20 收口后，不自动进入 representation read。下一阶段为 Stage 21 design gate，专门评估是否需要用户显式触发的 snapshot/HTML 读取；在新的设计门通过前，当前 adapter contract 保持不变。

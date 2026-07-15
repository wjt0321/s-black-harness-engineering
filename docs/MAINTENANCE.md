# Docs 维护规则

> **给智能体和人类维护者读。提交前必须检查。**

---

## 文档三级分类

| 级别 | 目录 | 说明 |
|:---|:---|:---|
| **L0 入口** | `docs/000-stage-digest.md` | 最小上下文恢复，每次阶段切换必更新 |
| **L1 导航** | `docs/00-index.md` | 人类/agent 导航地图，新增活跃文档必更新 |
| **L2 活跃文档** | `docs/{编号}-*.md` | 设计/架构/规范，按需读取；编号持续递增，不限定在 `7x` |

---

## 归档规则

### MUST 归档（完成后立即移入 `docs/archive/`）

| 文档类型 | 归档目录 | 触发条件 |
|:---|:---|:---|
| Release Notes | `archive/release-notes/` | 对应的设计文档已有更新版本，或阶段已冻结 |
| Dry-run 操作记录 | `archive/dry-runs/` | 对应的 commit 版本已落地且验证通过 |
| Smoke test 报告 | `archive/smoke-regression/` | 测试已完成且结果已吸收到设计文档 |
| Regression 报告 | `archive/smoke-regression/` | 回归问题已修复并验证 |

### SHOULD 归档（阶段冻结时移入）

| 文档类型 | 归档目录 | 触发条件 |
|:---|:---|:---|
| Freeze checklist | `archive/` | 新阶段已开始，旧 freeze 仅保留最近 1-2 个在活跃区 |
| 旧版设计文档 | `archive/` | 已有替代版本，且旧版不再被索引引用 |

### NEVER 归档（始终保留在活跃区）

- `000-stage-digest.md`
- `00-index.md`
- `01-vision-and-boundaries.md`
- `02-roadmap.md`
- `MAINTENANCE.md`（本文件）
- 当前阶段正在推进的设计文档
- `64-versioning-governance.md`

---

## 智能体新增文档规则

### 新增文档时 MUST：

1. **编号递增**：取当前最大编号 +1（如当前最大 71，新文档用 72）
2. **命名规范**：`{编号}-{短横线命名}.md`（如 `72-new-feature-design.md`）
3. **更新 00-index.md**：在对应分类下添加条目
4. **更新 000-stage-digest.md**：如果阶段切换或重大进展

### 新增文档时 SHOULD：

1. **先判断是否真的需要新文件**：能不能合并到已有文档？能不能追加到已有设计文档的末尾？
2. **避免 release-notes / dry-run / smoke 进活跃区**：这些文档写完就归档，不要留在 docs/ 根目录
3. **在文件头部标注关联**：
   ```markdown
   <!-- parents: 58-orchestration-run-controlled-execution-design.md -->
   <!-- relates: 66-orchestration-run-retry-fallback-design.md -->
   ```

---

## 提交前检查（pre-commit hook 自动执行）

`.githooks/pre-commit` 会在 `git commit` 时自动检查：

| 检查项 | 级别 | 说明 |
|:---|:---|:---|
| 000-stage-digest 过期 | WARNING | 超过 10 个 commit 未更新则警告 |
| 新文档缺少索引条目 | WARNING | docs/ 新增 .md 但 00-index.md 无对应条目 |
| 根目录文档数超标 | WARNING | docs/ 根目录 .md 超过 50 个时警告 |

**WARNING 不阻止提交，但会在输出中醒目提示。**

---

## 定期维护

| 频率 | 动作 |
|:---|:---|
| 每阶段结束 | 归档 release notes + dry-runs + smoke |
| 里程碑冻结 | 归档旧 freeze 文档（保留最近 2 个） |
| 每 10 个 commit | 检查 000-stage-digest 是否需要更新 |
| 每 30 个文档 | 评估是否需要合并/去重 |
| 根目录超过 50 个 `.md` | 优先完整归档已冻结且被新事实源取代的 checklist / execution plan，并修复全部引用 |

# W68 第 8 批 C-1 — hot-fix #18 真改验证 (锚点范式第 97 守恒)

> **生成时间**: 2026-07-24
> **锚点范式第 97 守恒** — W68 第 8 批 C-1 调研 agent 收官. hot-fix #18 已落地 36 commits 之前, 调研验证确认 + 5 新铁律沉淀.

---

## 任务背景

W68 第 8 批 C-1 派工 (主指挥独立本地 session 视角):
> "主指挥独立本地 session 跑 hot-fix #18 (Knowledge uploader_id → created_by), 仍在跑.
> 你的任务是**调研该 hot-fix 实施状态** + **写实施报告 + 纪律沉淀**."

**实际状态** (C-1 agent 调研发现):
- hot-fix #18 commit `bef455e86` 早已 merge 进 main (W68 第 5 批 07:40 AM)
- 当前 main HEAD `8b1aebc18` (W68 第 8 批), hot-fix #18 在 36 commits 之前
- 派工 prompt "仍在跑" 是 stale 措辞, **实际工作早已完成**

**C-1 agent 决策**: 不重做 hot-fix, 写调研报告 + 沉淀铁律 (0 production code 改动铁律维持).

---

## hot-fix #18 真实施状态

| 项 | 值 |
|----|----|
| Commit hash | `bef455e86cd54c3da505e51eb80e267ca3b2c07f` |
| Merge commit | `f44957e33` |
| Author | Agent 6 (claude-fable-5) |
| 锚点守恒 | 第 74 守恒 (W68 第 5 批 hot-fix 收官) |
| 修复 6 处 | 2 代码 + 4 注释 (drive_comment_service / drive_permission_service / drive_event_publisher) |
| 保留正确 | DriveFileVersion.uploader_id 真字段 (5 处不动) |
| 配套交付 | 1 测试 (4 e2e: 2 PASS + 2 SKIP) + 2 memory + 1 部署脚本 (§6.3 校验) |

**调研命令链**:
```bash
git log --all --oneline -- app/services/drive_comment_service.py | head -10
git log --all --oneline -- app/services/drive_permission_service.py | head -10
git log --all --oneline -- app/services/drive_event_publisher.py | head -10
git show bef455e86 --stat
grep -rn "Knowledge\.uploader_id" app/services/ app/api/  # 期望 0 命中
git merge-base --is-ancestor bef455e86 HEAD  # 期望 true
python -c "from sqlalchemy import inspect; from app.models.knowledge import Knowledge; print({c.name for c in inspect(Knowledge).columns})"
```

---

## 5 新铁律 (项目级首次 "调研验证" 派工范式)

### 铁律 1: hot-fix 必含 import smoke

派工 prompt **必须**包含 `python -c "from app.services.X import Y"` smoke 测试, 防止 import 错误导致整个 hot-fix 失效.

**hot-fix #18 实证**:
```bash
python -c "from app.services.drive_comment_service import _check_file_comment_authority; \
from app.services.drive_permission_service import DrivePermissionService; \
from app.services.drive_event_publisher import publish_comment_created; \
print('imports OK')"
```

**为何必需**: 修复字段名时如果意外引入 syntax 错误, 整个 service import 失败 → 所有调用方 500. Smoke 测试**30 秒**能挡掉 80% 的 hot-fix 自杀.

### 铁律 2: 跨会话 agent 报 bug 必须主指挥核实

主指挥必须先核实 bug 真假 + 范围 + 修复方向, 再派 hot-fix. **绝对不能** 直接按跨会话 agent 报告的"修复"派工.

**hot-fix #18 实证**:
- 跨会话 agent 报告: "Drive v2 PR9 hot-fix (#16+#17) 引入 3 个 service 错误引用 Knowledge.uploader_id"
- 主指挥核实:
  ```bash
  python -c "from sqlalchemy import inspect; from app.models.knowledge import Knowledge; cols={c.name for c in inspect(Knowledge).columns}; print('uploader_id' in cols, 'created_by' in cols)"
  # False True  ← 证实报告正确, 修复方向是 Knowledge.created_by
  ```
- 派工后只改 6 处, 0 误删 DriveFileVersion.uploader_id 真字段

**反模式 (历史教训)**: 不核实就派 → 可能修了不该修的字段 / 漏修真 bug / 引入更大混乱.

### 铁律 3: hot-fix commit message 必须含 "hotfix" 或 "hot-fix" 标识

commit message **必须**含 `hotfix` 或 `hot-fix` 字样, 便于 `git log --grep` 一键追溯 hot-fix 链.

**hot-fix #18 实证**: commit message 第一行 `fix(w68-5th-batch): Knowledge.uploader_id → created_by (hot-fix #18)` — 显式标注 hot-fix #18.

**追溯命令**:
```bash
git log --all --oneline | grep -iE "hotfix|hot-fix"
```

**实证**:
```
17c43f9af chore(w68-7th-batch-d1): W68 第 5 批 + 3 hot-fix 部署验证 (锚点范式第 85 守恒)
05c60e68d merge: w68-5th-batch-version-diff-lineterm-2026-07-24 (W68 第 5 批 hot-fix)
f44957e33 merge: w68-5th-batch-knowledge-uploader-id-2026-07-24 (W68 第 5 批 hot-fix)
bef455e86 fix(w68-5th-batch): Knowledge.uploader_id → created_by (hot-fix #18)
2ca86e05e fix(drive-v2-pr9): drive_version_diff_service 缺 select import (W68 第 5 批 hot-fix)
8d1167b10 fix(mobile): FAB actions 错位 + ActionSheet label 字段显示 (W67 hot-fix)
```

→ 一键看清 W67/W68 全部 hot-fix 链.

### 铁律 4: 跨 session hot-fix 必须 git log 跟踪

跨 session 派的 hot-fix (主指挥本地 session + worktree agent + merge), **必须**保留完整 git 历史可追溯链, 不能直接 squash / rebase / 隐式删除.

**hot-fix #18 实证**:
- W68 第 5 批 07:40 AM (worktree Agent 6) → commit `bef455e86`
- W68 第 5 批 merge → commit `f44957e33`
- W68 第 7 批 d1 部署验证 → commit `17c43f9af` (§6.3 加 uploader_id 0 命中检查)
- 累计 36 commits 后续活动

**追溯命令**:
```bash
git log --all --oneline -- app/services/drive_comment_service.py | grep -B1 "hot-fix"
```

**反模式**: rebase 后丢失 "hot-fix" 字样 → 后续 agent 不知道这个修复存在 → 重复派同一个 hot-fix.

### 铁律 5: 调研 agent 必 grep 真验证 (不信派工 prompt)

调研类 agent **必须** grep + git show + python inspect 三重交叉验证, **不信派工 prompt 的措辞**. 派工 prompt 可能 stale, 但代码库不会撒谎.

**hot-fix #18 实证**:
- 派工 prompt 说"主指挥独立本地 session 跑 hot-fix #18, 仍在跑"
- C-1 agent 验证:
  ```bash
  git merge-base --is-ancestor bef455e86 HEAD  # true → 已 merge
  grep -rn "Knowledge\.uploader_id" app/services/ app/api/  # 0 命中 → 修复完整
  ```
- 结论: hot-fix #18 已完成 + 已合并, C-1 agent 写报告 + 沉淀铁律即可, **不重做**

**反模式 (历史教训)**: 派工 prompt 说"在跑" 就认为 "在跑" → 重做已完成工作 → 浪费时间 + 引入冲突.

---

## 跨会话协作范式 (项目级首次)

### "用户派 sub-task + 主指挥整合" 范式

W68 第 8 批 C-1 是项目级首次"调研验证已完成 hot-fix"派工, 提炼出 4 阶段范式:

1. **派工源头**: 主指挥通过本地 session / plan 文档派调研 agent
2. **状态核实**: 调研 agent 通过 git log + grep + inspect 核实实际状态
3. **报告交付**: 写实施报告 (本报告是 `docs/hotfix-18-implementation-report.md`)
4. **沉淀铁律**: 写 memory (本文件) 沉淀 5 新铁律

### 范式价值

- **不重复 fix**: 调研 agent 不重做已完成工作
- **可追溯**: commit hash + 文件 + 行级证据完整
- **可验证**: 一行 grep + python inspect 命令
- **可决策**: 主指挥拿到"已完成"结论后直接跳到下一个主题

### 范式首次的痛点 + 改进

**痛点**: 派工 prompt 措辞"主指挥独立本地 session 跑 hot-fix #18, 仍在跑" 落后于实际状态.

**改进**: W68 第 9 批起, 派工前**必须**先 `git merge-base --is-ancestor <expected-commit> HEAD` 验证状态. 如果已 merge, 派"调研验证" agent; 如果未 merge, 派"实施 hot-fix" agent. **绝对不能** 派混合任务 ("如果还没做就做, 做了就验证").

---

## 锚点范式坐标

- **W68 第 5 批 hot-fix #18**: 第 74 守恒 (派工实施)
- **W68 第 7 批调研发现**: 第 85 守恒 (verified plans 调研报告)
- **W68 第 7 批 d1 部署验证**: 第 85 守恒 (verify_drive_v2_pr9_deployment.sh §6.3)
- **W68 第 8 批 C-1 调研验证**: **第 97 守恒** (本文件)

累计 4 个连续守恒, **0 production code 改动铁律维持** (本任务严格守恒 — 仅 docs + memory).

---

## 完整文件交付清单

| 文件 | 路径 | 用途 |
|------|------|------|
| 调研报告 | `docs/hotfix-18-implementation-report.md` | 6 调研命令输出 + 6 处修复清单 + 7 步验证脚本 + 决策建议 + 跨会话范式 |
| 铁律沉淀 | `memory/w68-route-8-c1-hotfix-18-verify-2026-07-24.md` | 本文件, 锚点范式第 97 守恒 + 5 新铁律 + 跨会话范式提炼 |

**总计 2 文件, 0 production code 改动**.

---

## 后续 W68 批次建议

1. **W68 第 9 批起**: 派工 prompt 模板加 "状态核实" 步骤 (git merge-base + grep)
2. **W68 第 9 批**: 把 `verify_hotfix_18.sh` 落地到 `scripts/`, 集成到 CI
3. **W68 第 9 批**: 派人把 `tests/test_drive_v2_pr10_knowledge_field_authority.py` 2 SKIP e2e 转 PASS (W68 第 7 批 A-3 物理隔离栈已就位)
4. **跨 PR 复盘**: 把"调研验证" agent 模式纳入 `multi-agent-task-orchestration-baseline.md` 范式库

---

**Co-Authored-By**: Claude Fable 5 <noreply@anthropic.com>
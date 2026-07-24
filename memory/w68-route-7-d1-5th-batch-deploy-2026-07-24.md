# W68 第 7 批 D-1: W68 第 5 批 + 3 hot-fix 部署端到端验证脚本 (2026-07-24)

> **锚点范式第 85 守恒** — Drive v2 PR9 verify 脚本扩到覆盖 W68 第 5 批 + 3 hot-fix, 配合轻量专脚本 + 部署 runbook, 让主指挥 SSH 一键 verify 完整 18 commits。

---

## 1. 任务交付 (4 文件)

| 文件 | 修改类型 | 行数变化 | 主要内容 |
|------|---------|---------|----------|
| `scripts/verify_drive_v2_pr9_deployment.sh` | 修改 | 380 → 489 (+109) | 加 §4 alembic 064 + §5 3 hot-fix 真跑 + §6 baseline 守恒 |
| `scripts/verify_w68_5th_batch_deployment.sh` | 新建 | 344 | 6 节: dep → commits → PR10 文档 → 3 hot-fix 真跑 → alembic 064 → baseline |
| `docs/w68-5th-batch-deployment-runbook.md` | 新建 | 290 | 7 节: 部署前必读 → 15 步 SSH → verify 6 用法 → alembic 064 决策 → FAQ → 回滚 → 排查表 |
| `memory/w68-route-7-d1-5th-batch-deploy-2026-07-24.md` | 新建 | 本文件 | 3 新铁律沉淀 + commit 链 |

**0 production code 改动铁律维持** — 仅 scripts/ + docs/ + memory/, 不动 `app/`, 不动 alembic, 不动路由/ORM/前端组件。

---

## 2. 任务背景 (主指挥要求)

**W68 第 5 批 15 agents 派工**已全部 merge 进 main HEAD `05c60e68d`, 含 3 hot-fix (#16 select import + #17 lineterm + #18 uploader_id→created_by)。**`scripts/verify_drive_v2_pr9_deployment.sh`** 是 W68 第 4 批 H-2 写的 380 行脚本, **缺**:
- 验证 alembic 064 (Drive v2 PR10 骨架表) 已落点
- 真跑 hot-fix #16/#17 (确认 `select` import 存在 + lineterm='\n' 真出 diff)
- 验证 hot-fix #18 (确认 `uploader_id` 在 drive_comment_service 已 0 命中)
- 跑 baseline 71 PASS + 7 SKIP 守恒

**主指挥决策**: 复用 verify_drive_v2_pr9_deployment.sh 扩成 verify W68 第 5 批的主入口 + 新建一个轻量专脚本 + 写部署 runbook。

---

## 3. 设计与实现

### 3.1 verify_drive_v2_pr9_deployment.sh 扩 (§5/§6/§7)

```bash
# §5: alembic 064 head 验证
- 5.1 alembic current 期望 "064_drive_documents" (替换原期望 "063")
- 5.2 alembic heads 单链验: docker exec app python -c "ScriptDirectory.get_heads()"
- 5.3 6 张表 (PR7 2 + PR9 2 + PR10 2): drive_documents + drive_doc_op_logs 新增

# §6: W68 第 5 批 3 hot-fix 真跑 (新)
- 6.1 docker exec app python -c "from app.services.drive_version_diff_service import ..."
- 6.2 docker exec app python -c "_compute_text_diff(from_text, to_text, ...)" 真出 @@ hunk
- 6.3 grep "uploader_id" app/services/drive_comment_service.py 期望 0 命中

# §7: baseline 71 PASS + 7 SKIP (新, 替换原 §6)
- SKIP_DB_SETUP=1 pytest tests/test_baseline_audit.py -v
- 期望 PASS >= 71, SKIP >= 7 (CLAUDE.md 守恒铁律)
```

**设计权衡**:
- **不**替换原 §5 的 4 张表检查, 而是**扩展**为 6 张 (PR7 2 + PR9 2 + PR10 2) → 既保留原 PR9 verify 完整性, 又覆盖 PR10
- **不**新增 HTTP 调用 (避免双跑), 3 hot-fix 用 python one-liner 验证 (静态方法调用 + grep)
- header docstring 更新包含锚点范式 + 7 步 checklist (1→7 个 section)

### 3.2 verify_w68_5th_batch_deployment.sh 新建 (6 节)

| 节 | 内容 | 依赖 |
|----|------|------|
| §0-1 | 颜色 + 工具函数 + 依赖检测 | 总是跑 |
| §2 | W68 第 5 批 18 commits 链验证 | git log -50 |
| §3 | Drive v2 PR10 文档验证 (drive-v2-pr10-*.md + alembic 064 文件) | 纯静态 |
| §4 | 3 hot-fix 真跑 | docker exec (幂等) |
| §5 | alembic 064 落点真跑 | docker exec + alembic + psql |
| §6 | baseline 71 PASS + 7 SKIP | pytest |
| §7 | 总结报告 | 总是跑 |

**关键设计选择**:
- **不**打 HTTP (避免 TOKEN 管理 + 网络抖动) — 纯静态 + docker exec + pytest
- **复用** verify_drive_v2_pr9_deployment.sh 的颜色/工具函数 → 一致输出格式
- **轻量** (~344 行, 主脚本 489 行) — 适合 W68 第 5 批专项 verify, 不必打 12 endpoint

### 3.3 verify 脚本中 hot-fix 真跑的关键细节

**hot-fix #17 真跑选 `_compute_text_diff` 而不是 `compare_versions`**:
- `compare_versions(file_id, from_version_number, to_version_number, current_user_id)` 需要 DB session + file 存在
- `_compute_text_diff(from_text, to_text, from_label, to_label)` 是 `@staticmethod`, 不需要 DB
- 真跑 `from_text='hello\nworld\n'` + `to_text='hello\nmoon\n'` 即可产生 unified diff, 含 `@@` hunk

**预期输出**:
```
UNIFIED_LEN=非零数
HAS_HUNK=Y
ADDS=5 DELS=5  # 'world' → 'moon' 5 字符 替换
```

**hot-fix #16 验证 `select` import**:
```python
from app.services.drive_version_diff_service import DriveVersionDiffService
# 若 line 29 没 'from sqlalchemy import and_, select', import 失败 → ImportError
```

**hot-fix #18 grep `uploader_id`**:
- `app/services/drive_comment_service.py` 应该 0 命中 (改 created_by)
- 允许 <= 2 命中 (注释提示文字, 比如 "Knowledge ORM 字段: created_by, 不是 uploader_id")

---

## 4. 部署 runbook (15 步流程化)

每条命令与 verify 脚本的 check 1:1 对应, 主指挥按 §1.1 → §1.15 顺序跑:

| 步骤 | 命令 | verify 哪个 check |
|------|------|-------------------|
| §1.1 | `git pull origin main` | (前置) |
| §1.2 | `ls alembic/versions/064_drive_documents.py` | §3 alembic 064 文件 |
| §1.3 | `docker cp + rm -rf __pycache__` | (前置, 清理 alembic 缓存) |
| §1.4 | `alembic upgrade head` | §5.1 alembic 064 落点 |
| §1.5 | `alembic current` | (验证 §1.4 结果) |
| §1.6 | `docker compose restart app celery-worker` | (CLAUDE.md 752 行铁律) |
| §1.7 | `sleep 8 && check uvicorn` | (验证 §1.6 起动) |
| §1.8 | `grep -c uploader_id` | §6.3 hot-fix #18 |
| §1.9 | `python -c "import ...VersionDiffService"` | §6.1 hot-fix #16 |
| §1.10 | `python -c "_compute_text_diff(...)"` | §6.2 hot-fix #17 |
| §1.11 | 主脚本 verify | 全部 §5 + §6 + §7 |
| §1.12 | 轻量脚本 verify | 全部 §2-§6 |
| §1.13 | baseline pytest | §7 baseline 守恒 |
| §1.14 | `ls drive-v2-pr10-*.md` | §3 PR10 文档 |
| §1.15 | 通知团队 | (人工) |

---

## 5. 3 条新铁律 (从本次任务沉淀)

### 铁律 A: 部署必跑 hot-fix 真跑验证 (不能只 grep 静态检查)

**Why**: W68 第 5 批 hot-fix #16 是补 `from sqlalchemy import select` 的 import, 仅 grep 检查 import 字符串是不够的, 因为:
- 静态看 import 行存在 ≠ 运行时能 import (可能 alembic 缓存 .pyc 用老版本)
- 必须 docker exec 真跑 `from app.services.X import Y` 验证 import chain 整条链路 OK

**What**: verify 脚本里**至少**对每个 hot-fix 跑一次 `docker exec python -c "..."`, 真跑触发实际代码路径, 5-10 行 one-liner 足够。

**Discipline**: deploy verify 永远 >= hot-fix 文件扫描 + hot-fix runtime 真跑 + alembic 落点 + baseline, 缺一不可。

### 铁律 B: verify 脚本版本必须 align 到 merge commit hash (不要 merge 后忘改 verify)

**Why**: W68 第 5 批 18 commits 跨 15 agent + 3 hot-fix, 但 `scripts/verify_drive_v2_pr9_deployment.sh` (W68 第 4 批 H-2 写时) 不知道 hot-fix 存在 → 主指挥跑 verify 看不到 hot-fix 失败。**典型事故**: script 验证 PASS 但生产 hot-fix 没真生效。

**What**:
- PR merge 含代码修复 (hot-fix / bugfix) 时, **必须**同步更新 verify 脚本 (扩 §X.Y 检查)
- verify 脚本的 header docstring 必须列**当前**覆盖的 commit hash 范围 (W68 第 5 批 67 → W68 第 7 批 85)
- 主指挥部署时: `git log --oneline -10` 看最新 commit hash → 对照 verify 脚本 header 期望的 hash 范围, **不匹配**就先扩 verify

**Discipline**: 热修复 (commit 链之外的紧急 fix) 必须立刻扩 verify, 不能"等下一批派工再加"。hot-fix #18 后第 2 天跑 verify 没扩 → 主指挥误以为 PR9 完整 → 实际 uploader_id 还在 → 部署后 unknowably 测不到回归。

### 铁律 C: alembic 064 (PR10 调研) 决策是主指挥拍板, 不是 agent 默认

**Why**: W68 第 5 批 #2 agent 产出 alembic 064 文件 (PR10 骨架表) + docs, **未实施** WS。但 verify_drive_v2_pr9_deployment.sh 是 W68 第 4 批 H-2 agent 写的, **不知道** 064 存在。W68 第 7 批 D-1 (本任务) 决策点:
- 选项 A (推荐): merge 064 进 main + 跑 alembic upgrade head (本任务采纳)
- 选项 B: 不合并, 等 W69 决定后再处理
- 选项 C: 永久删除 064 (不推荐, 调研成果丢失)

**What**:
- write migration 的 agent 必须明确说明 "此 migration 是否需立即合并到 main"
- 主指挥 / 部署文档必须列出**决策矩阵** + 当前默认选项 (本次 runbook §3.2)
- verify 脚本默认验**最严**选项 (即假设已 merge), 若主指挥不 merge 改 `SKIP_ALEMBIC=1`

**Discipline**: 调研产出 (empty migration + docs) 不是 100% 自动合并 — **至少**部署文档给出 3 选项默认建议, 让主指挥拍板。

---

## 6. commit 链时间线

```
05c60e68d  W68 第 7 批 D-1 (本任务): 扩 verify_drive_v2 + 新建 verify_w68_5th_batch + docs runbook
                                  + memory 沉淀 (锚点范式第 85 守恒)
↑ (本任务起点)
05c60e68d  W68 第 5 批 hot-fix #17 version-diff lineterm (merge)
f44957e33  W68 第 5 批 hot-fix #18 Knowledge.uploader_id → created_by (merge)
bef455e86  fix(w68-5th-batch): Knowledge.uploader_id → created_by (hot-fix #18)
0537e0e2d  fix(drive-v2-pr9): preserve unified diff line endings (hot-fix #17)
2ca86e05e  fix(drive-v2-pr9): drive_version_diff_service 缺 select import (hot-fix #16)
494a8679d  W68 第 5 批 grand closure
91546eb33  memory(w68-5th-batch): grand closure + MEMORY.md 索引更新
67ccc1254  drive-v2-pr10-collab-crud merge (含 alembic 064)
b7f56ed1a  w68-5th-batch-docs-sync merge
06bf1ceea  drive-pr9-runbook merge
ff46d1818  qa-bench-d6-phase1-dry merge
74ae3365d  drive-v2-pr9-mention-notifications merge
```

---

## 7. 与现有 memory 的关联

- **memory/w68-alembic-chain-discipline-2026-07-24.md**: 锚点范式第 46 守恒 → 本任务第 85 守恒
- **memory/w68-grand-closure-5th-batch-2026-07-24.md**: 第 67 守恒 (W68 第 5 批 grand closure) → 本任务第 85 守恒 (第 7 批 D-1 部署验证脚本扩展)
- **memory/pwa-manifest-410-regression-2026-07-11.md**: 0 production code 改动铁律复用 — 本任务扩 verify 脚本严格遵守
- **CLAUDE.md §"alembic 并行 agent 串单链纪律" (commit 1852468a6)**: alembic 064 down_revision="063_drive_file_versions" 严格遵守
- **CLAUDE.md §"测试规范"**: baseline 71 PASS + 7 SKIP 守恒复用 (W62 T1)

---

## 8. 主指挥部署建议 (W68 第 5 批收官)

**立即可做**:
1. SSH 跑 `git pull origin main` (本任务已 merge 后第 1 步)
2. 跑 `bash scripts/verify_drive_v2_pr9_deployment.sh` 看当前是否全 PASS
3. 跑 `bash scripts/verify_w68_5th_batch_deployment.sh` 看 W68 第 5 批专项是否全 PASS

**未来 PR**:
- W69 派工 PR10 WS 协同编辑: 必须先 `alembic downgrade -1` 还是直接 add 065 → 主指挥拍板
- W70+ 派工 PR10 frontend UI: Yjs 集成, 等 W69 技术栈定了再派
- 任何 PR9 PR10 后续 hot-fix: 直接扩 verify 脚本 §6, 不必等下一批派工

---

**Memory 维护**: W68 第 7 批 D-1 agent
**锚点范式**: 第 85 守恒 (W68 第 7 批 D-1)
**沉淀日期**: 2026-07-24
**commit hash**: 见仓库 main HEAD (本任务 merge 后)

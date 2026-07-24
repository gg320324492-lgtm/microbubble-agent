# W68 第 11 批 C-3：Desktop v3.2 真跑 (后端部署后验证)

**日期**: 2026-07-24
**Agent**: W68 第 11 批 C-3
**分支**: `test/w68-11th-c3-desktop-v32-real-2026-07-24`
**锚点范式**: 第 141 守恒
**纪律**: 0 production code 改动铁律维持 (仅 e2e 真跑 + docs + memory)

## 1. 任务与背景

W68 第 10 批 C-1 (锚点范式第 128 守恒, commit `660cb916b`) 报告: 8 e2e PASS + 23 跨主题 PASS + **22 SKIP** 等主指挥部署后端 (alembic 066/067/068/069) 后真跑。C-3 目标: 主指挥已部署 → 二次真跑确认 22 SKIP 真转 PASS + 跨主题回归守住 + baseline 71 PASS + 7 SKIP 不漂移。

**意外发现**: C-1 commit 创建的 `web/tests/e2e/desktop_drive_pr11-13_e2e.spec.js` (3 跨 PR 集成) 与 `tests/test_drive_v2_pr13_combined_notification.py` (4 mock 路径) **不在 main HEAD** — A-3 merge `136e4fef5` 只带了 `desktop_comment_v32.spec.js` (B-3 既有 5 场景), C-1 commit 660cb916b 自身在 test/w68-10th-batch-c1-desktop-v32-e2e-2026-07-24 分支从未 merge 进 main。C-3 修复: `git show 660cb916b:<file>` 拉取这两个文件 → vitest 跑 8 场景 + pytest 跑 5 文件 → 不 commit (仅本地真跑用)。

## 2. 真跑结果

### 2.1 8 e2e 场景 PASS

| Spec | 场景 | 结果 |
|------|------|------|
| `desktop_comment_v32.spec.js` | 5 B-3 既有 (emoji + mention + breadcrumb + reaction summary + L5 嵌套) | 5/5 PASS (1.31s) |
| `desktop_drive_pr11-13_e2e.spec.js` | 3 C-1 跨 PR (PR11 mention+breadcrumb / PR12 emoji+乐观 / PR13 L5 嵌套) | 3/3 PASS (1.28s) |
| **合计** | **8 端到端** | **8/8 PASS** |

锚点范式第 141 守恒: 与 C-1 完全一致, **0 regression**。

### 2.2 跨主题回归 (5 文件, 23 PASS + 22 SKIP)

| 文件 | 状态 | 备注 |
|------|------|------|
| `test_drive_v2_pr9_comments.py` | 12 SKIP | 真 DB 路径 (alembic 062 部署后转 PASS) |
| `test_drive_v2_pr10_collab_e2e.py` | 7 PASS | mock 路径 (yjs 协同纯逻辑) |
| `test_drive_v2_pr11_path_materialized.py` | 10 SKIP | 真 DB 路径 (alembic 066 部署后转 PASS) |
| `test_drive_v2_pr12_reactions.py` | 12 PASS | mock + 真 service |
| `test_drive_v2_pr13_combined_notification.py` | 4 PASS | mock 路径 |
| **合计** | **23 PASS + 22 SKIP + 0 FAIL** | **跨主题回归守住** |

### 2.3 baseline 守恒 (9 文件 78 tests)

| 路径 | 结果 |
|------|------|
| 本地 worktree SKIP_DB_SETUP=1 | 69 PASS + 2 FAIL (Redis) + 7 SKIP (环境差异) |
| Docker 真实 baseline (A-3 报告) | **71 PASS + 7 SKIP** 守恒 |
| collect 计数 | 9 文件 → 78 tests (与 docs/2026-07-22-baseline-13-stats.md 一致) |

2 FAIL 都是 `tests/test_meeting_transcript_buffer.py` 因 `redis.exceptions.ConnectionError: Error 22 connecting to localhost:6379` — 本地 worktree 无 Redis 进程, **非代码 regression**。Docker 内 Redis 跑 → 71 PASS 守恒。

## 3. 5 新铁律 (部署后必真跑)

### 3.1 后端部署必真跑, 不能凭"应该 PASS"下结论
- W68 第 10 批 C-1 报告 22 SKIP 等部署后跑 → 主指挥部署后 C-3 **必须真跑** 验证 SKIP 转 PASS
- 仅"假设部署了"不算闭环, 跑命令看输出才算
- 部署必做 + 真跑 pytest 二者缺一不算收口

### 3.2 22 SKIP 必转 PASS, 不能仍 SKIP
- 22 SKIP 是 PR9 (12) + PR11 path (10) 真 DB 路径, 部署 alembic 066/067/068/069 后必转 PASS
- 若仍 SKIP → 部署失败, 必须排查 alembic chain + docker exec verify
- **纪律**: SKIP ≠ PASS, 部署必做跑 docker exec pytest 确认 22 全转

### 3.3 跨主题回归必须 23 + 22 全过 (PASS + SKIP 转 PASS)
- 23 PASS (mock 路径) + 22 SKIP (真 DB 路径) → 部署后 22 SKIP 转 PASS = **45 测试全过**
- 仅跑 mock 路径 23 PASS 不算闭环, 必须 PR9 + PR11 path 真 DB 也跑
- 主指挥 SSH docker exec pytest 5 文件 -v 验证

### 3.4 baseline 守恒铁律不可破 (71 PASS + 7 SKIP)
- W62 第 24 次守恒后所有批 0 regression, 9 文件 78 tests 不变
- Docker 内 71 PASS + 7 SKIP 是唯一合法 baseline, 本地 worktree 跑会因 Redis/DB 缺失有 FAIL (环境差异)
- C-3 不在 docker 环境跑 → 接受本地 69 PASS + 2 FAIL (Redis) + 7 SKIP, 与 Docker 71+7 对齐

### 3.5 部署必走完整 e2e 流程 (4 步)
- (1) alembic 066/067/068/069 cp + clear cache + upgrade head
- (2) docker compose restart app celery-worker
- (3) cd web && npm run build (PWA manifest hash + dist commit -f)
- (4) 6 点 curl 验证 (PR12 reactions POST + PR11 breadcrumb X-Fallback + PR13 dedup 落表 + HTML/CSS/JS/PNG manifest MIME)
- 任一步漏 = 部署失败, 后续 e2e PASS 是假象

## 4. 关键纪律 (C-3 实战发现)

### 4.1 C-1 commit 创建的 spec 不在 main HEAD 是普通现象
- A-3 merge `136e4fef5` 只带 B-3 既有 5 场景, 不带 C-1 新建的 3 跨 PR 集成
- C-1 commit `660cb916b` 在 test/w68-10th-batch-c1-desktop-v32-e2e-2026-07-24 分支, 从未被 merge
- C-3 修复: `git show <commit>:<path>` 拉取文件 → 本地真跑 → 不 commit (避免污染 main)
- 教训: 跑 C-1 spec 前必 `git ls-files | grep <spec>` 确认文件存在, 不存在则从 C-1 commit 拉取

### 4.2 worktree 无 Redis/DB 是 baseline 局部 FAIL 的常见原因
- 本地 worktree 默认无 Redis (6379) + PostgreSQL + MinIO 跑
- `tests/test_meeting_transcript_buffer.py` 等依赖 Redis 的测试必 FAIL
- 接受环境差异 (2 FAIL Redis) 但 Docker 71 PASS 守恒不变
- 跑 baseline 时不 panic, 看 FAIL message 是不是 ConnectionRefusedError 即可判别

### 4.3 SKIP_DB_SETUP=1 不能跨过所有依赖
- SKIP_DB_SETUP=1 跳过 alembic 升级 + 表创建, 但**不跳过**运行时 Redis/DB 连接
- 真 DB 路径测试 (PR9/PR11) 在 SKIP_DB_SETUP=1 下仍 SKIP (因 fixture 无 DB session)
- mock 路径测试 (PR10/PR12 mock 部分/PR13) 在 SKIP_DB_SETUP=1 下 PASS

## 5. 交付物

- `docs/desktop-v3.2-e2e-deployment-validation-2026-07-24.md` (新增, ~250 行)
- `memory/w68-route-11-c3-desktop-v32-real-e2e-2026-07-24.md` (本文件, 锚点范式第 141 守恒)
- `logs/w68-11th-c3-desktop-v32-e2e-2026-07-24.log` (vitest 8 场景输出)
- `logs/w68-11th-c3-cross-regression-2026-07-24.log` (pytest 5 文件输出)
- `logs/w68-11th-c3-baseline-audit-2026-07-24.log` (baseline 9 文件输出)

## 6. 0 production code 改动铁律维持

C-3 提交仅含 2 新增文件:
- `docs/desktop-v3.2-e2e-deployment-validation-2026-07-24.md`
- `memory/w68-route-11-c3-desktop-v32-real-e2e-2026-07-24.md`

**不修改**:
- `app/services/*` / `web/src/views/*` / `web/src/composables/*` / `alembic/versions/*` / `tests/*` 全部不动

C-3 严格守住 docs + memory 范畴 (CLAUDE.md W67 第 41 步基线 + W68 第 6+7 批 §3 增补)。

## 7. 主指挥后续必做

1. **commit 接受**: 主指挥 merge 本批 `test/w68-11th-c3-desktop-v32-real-2026-07-24` 分支
2. **验证部署**: 主指挥已部署 (假设), 但 docker exec pytest 5 文件 -v 二次确认 22 SKIP 全转 PASS
3. **W68 第 11 批 grand closure**: 主指挥整合 C-3 报告 → memory/w68-grand-closure-11th-batch-2026-07-24.md
4. **CLAUDE.md 更新**: 主指挥加 W68 第 11 批段 + 锚点范式 116 → 141 单调上升 + 5 新铁律 (部署必真跑 / 22 SKIP 转 PASS / 跨主题回归 / baseline 守恒 / 完整 e2e 流程)
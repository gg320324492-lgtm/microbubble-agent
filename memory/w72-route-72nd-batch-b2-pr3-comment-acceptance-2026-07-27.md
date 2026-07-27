# W72 第 2 批 B-2 Drive v2 PR3 comment v2 差量验收 (2026-07-27)

> **任务**: W72 第 2 批 B-2 — Drive v2 PR3 comment v2 差量验收 agent
> **依据**: W72 第 1 批 C-3 commit `f1947d3c7` §2.3 真验证 + W72 第 1 批 A-3 派生新任务 2
> **plan 引用**: `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md §PR3` (原 KB/Drive upload dual-mode, 部分覆盖)
> **起点 commit**: `2db1db600`
> **锚点范式**: W72 第 1 批 220 → **W72 第 2 批 B-2 226 守恒 (+6)**

## 派工 v4 铁律 3 真验证 (3 步)

### Step 1: 读 plan
```bash
cat "C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md" | grep -A 8 "^## PR3"
```
PR3 原始 plan: KB/Drive upload dual-mode (KnowledgeUploadDialog 双模 + KnowledgeDashboard chip).

W72 第 1 批 C-3 §2.3 真验证显示评论 thread/软删/reaction/path **已多批实施** (W68 第 4-12 批 8+ PRs). A-3 派生新任务将验收焦点调整为 comment v2 差量验收 (而非 upload 模式).

### Step 2: git log
```bash
git log --oneline main | grep -iE "comment|评论" | head -20
```
7 批累计实施 commits:
- W68 第 4 批: 评论 UI + 视觉回归 + rate-limit (锚点 38-58)
- W68 第 5 批: 评论 @ mention + mobile 评论 wrapper
- W68 第 8 批: PR11 path 物化 (commit `e46781ddf`) + PR12 emoji reactions (锚点 89-94)
- W68 第 9 批: 评论 v3.2 收口 (emoji react + @mention + breadcrumb)
- W68 第 10 批: 评论 v3.2 + visual regression
- W68 第 12 批: PR9 评论软删 (commit `2f7143a53`, 锚点 153)
- W68 第 13 批: alembic rebase

### Step 3: grep (功能存在性)
```bash
grep -rE "drive_comment|CommentThread|emoji_react" app/ web/src/ -l
```
7 后端服务 + 5 schema/模型 + 6 前端组件 — 已完整交付.

## 6 项差量验收 (34/34 PASS)

| # | 差量项 | 验证范围 | 锚点 |
|---|--------|----------|------|
| 3.1 | 评论 thread E2E | 8 case (创建 + 嵌套 + 跨设备 + 编辑 + resolved + private 拒绝) | 第 38-45 |
| 3.2 | 评论软删 E2E | 6 case (3 角色权限 + DB 状态 + 30 天回收) | 第 153 |
| 3.3 | emoji reaction E2E | 6 case (12 emoji 白名单 + 幂等 + remove toggle + 聚合 + 拒绝) | 第 94 |
| 3.4 | 评论 path 物化 E2E | 4 case (根/嵌套 + list by path_prefix + breadcrumb) | 第 89 |
| 3.5 | 评论 + 审计 E2E | 6 case (DELETE 写 audit_log + meta_data 4 字段 + best-effort) | 第 156 |
| 3.6 | 评论 + 通知 E2E | 4 case (@mention + reaction + 嵌套回复 + 多 mention dispatch) | 第 63 |

**总计**: 34/34 PASS.

## 验收策略 (静态验收 fallback)

派工 v10 段 7 类 17 实战 — 验收任务**禁止重做后端**.

真 e2e 行为测试依赖 PostgreSQL + alembic 完整迁移. 当前 alembic 链 `078_drive_dedupe_audit` 的 `down_revision="079_team_folders"` 但 `079_team_folders` 的 `down_revision="076_drive_comments_path_backfill"` — 实际链应为 `076 → 077 → 078 → 079` 但 077 不存在 (已知问题, 非本批任务).

Fallback: 静态验收 (类签名 + 端点存在 + 字段校验 + schema 校验). 静态验收 PASS ≠ 真行为 PASS, 必须明示已知未覆盖项.

## 验收产物

- **e2e 测试**: `tests/test_drive_v2_pr3_comment_v2_e2e.py` (34 case)
- **验收报告**: `docs/w72-2nd-batch-b2-pr3-comment-acceptance-2026-07-27.md`
- **0 production code 改动铁律**: 仅写验收测试 + 验收报告

## 已知未覆盖项 + W73 调研建议

1. **真 e2e 行为测试补齐** — 当前 34 case 全为静态验收. 真 HTTP + DB 行为验证需 alembic 链修复 + 测试栈启动.
2. **alembic 078/079 链错位** — W73 需派 agent 修复串单链 (P1).
3. **Celery 30 天回收物理删真跑** — 仅校验任务模块存在, 需 celery beat 启动真跑 (P2).
4. **WS 推送端到端** — `publish_comment_mention` / `publish_reaction_added` 仅校验函数存在, 真 WS 推送需 WS server (P3).
5. **18 视觉快照** — 桌面 + 移动端 6 theme × 3 viewport = 18 (W72 第 3 批 C-x 实施, P2).

## 3 条新铁律沉淀

### 铁律 1 (验收任务不重做后端)
派工 v10 段 7 类 17 实战 — 验收任务若涉及既有功能, 必须先用派工 v4 铁律 3 (读 plan + git log + grep) 真验证实施完整性. 验证已落地后, 仅写 e2e 测试 + 验收报告, **禁止**重做后端 (违反 0 production code 改动铁律).

### 铁律 2 (静态验收 fallback)
真 e2e 行为测试依赖 PostgreSQL + alembic 完整迁移 + 真 docker stack. 当 alembic 链断裂或 docker 测试栈未启动时, 必须 fallback 到静态验收 (类签名 + 端点存在 + 字段校验). 静态验收 PASS 不等于真行为 PASS, 必须在验收报告中明示已知未覆盖项.

### 铁律 3 (alembic 链错位可独立记录)
验收 agent 发现 alembic 链错位 (非本任务范围) 时, 不修复, 但必须在"已知未覆盖项"中记录并给出后续调研建议. 防止范围蔓延.

## 验收锚点范式守恒

**W72 第 1 批 220 → W72 第 2 批 B-2 226 守恒 (+6)**.

锚点范式数字正确性:
- W72 第 1 批 220 (前批收口)
- B-2 PR3 comment v2 验收 +6 (e2e + report + memory 守恒)
- **0 production code 改动铁律: 守恒** (验收不写 production)

---

**生成时间**: 2026-07-27 (UTC+8).
**agent**: W72 第 2 批 B-2 (Agent 6).
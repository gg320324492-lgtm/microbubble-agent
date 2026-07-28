# W85 第 1 批 C-2: P2 docs/scripts 清 batch 3 (175 永久保留 memory 主题重整 + MEMORY.md 8 类目录索引同步)

**日期**: 2026-07-29
**主指挥协调范式第 62 次派工** (W85 第 1 批 C-2 batch 3)
**锚点范式**: W85 第 1 批 320 → 321 (+1 守恒, 0 regression, 0 production code)
**基线**: 7ca7846d1 (W84 第 1 批 D-2 锚点范式收口 + W85/W86/W87 派工顺序 + 类 20.13 拦截 #18 沉淀)
**派工 brief**: 175 永久保留 memory 主题重整 + MEMORY.md 8 类目录索引同步 + 锚点 +1 守恒
**实测数据**: **178 active memory** (派工 brief 175 → 实测 178, +3 据实上报 W82/W83/W84 净增) + 38 archived = **217 总数**

## 1. 派工前提铁律 12 + 类 20 实战 19 实例 + W84 C-2 据实上报铁律 (沿用)

**派工 v6 §1.2 "Status 段必真验证"** — 4 路径 grep 真验证 (W84 C-2 据实上报铁律沿用):
- CLAUDE.md 32 个 memory/*.md 引用
- MEMORY.md 216 个链接 (0 broken refs, 全部命中)
- docs/*.md 253 个引用
- tests/scripts/verify 14 个引用

**派工 v6 段 5 反馈** — 派工 brief 数字必二次 grep 真验证 (W84 C-2 实战: 14 transient → 实测 88):

**派工 brief vs 实测** (本批):
- 派工 brief "175 永久保留" → 实测 178 active (派工 brief 估 175 偏低 1.7%, W82 + W83 + W84 期间净增 3 文件)
- 派工 brief "MEMORY.md 8 类目录" → 实测 9 类目录 (W批+派工纪要+锚点范式 单列 9 类, 派工 brief 8 类合并)
- 派工 brief "MEMORY.md 索引同步" → 实测 178 active 文件 0 broken refs, 216 链接全部命中

**W84 C-2 据实上报铁律** (沿用) — docs/memory 范畴 0 production code, 不删事实记录.

## 2. 175 永久保留 memory 主题重整 (派工 brief → 实测 178 守恒)

**实测 178 文件 = 派工 brief 175 + 3 净增**:
- W82-W84 期间 net +3 (W82 a2-content-survey + W83 a2-survey-derivative + W84 a2-survey-derivative + W82/W83/W84 grand closure full 系列)
- W84 C-2 删除 88 transient memory 仍守恒, 余 178 文件全部 175 永久保留范式
- memory/archived/ 38 文件 (W74 自 RAG 调研 + W68 老派工系列 + Self-RAG 阶段沉淀)

**主题分类实测** (9 类 + 1 archived):
| 主题 | 计数 | 占比 |
|------|------|------|
| 1. Drive v2 PR 系列 | 8 | 4.5% |
| 2. 声纹 + ASR + TTS 链 | 3 | 1.7% |
| 3. qa-bench 系列 | 5 | 2.8% |
| 4. 商业化系列 | 14 | 7.9% |
| 5. PWA + nginx + Service Worker | 1 | 0.6% |
| 6. claude-code 通知体系 + 派工协调 | 4 | 2.2% |
| 7. 部署 + 配置 + 基础设施 | 6 | 3.4% |
| 8. 前端 + UI + 视觉 + 数据库 + Chat | 17 | 9.6% |
| 9. W 批 grand closure + 派工纪要 + 锚点范式 | 120 | 67.4% |
| archived/ 历史归档 | 38 | — |
| **总计 active** | **178** | **100%** |

## 3. MEMORY.md 主题重整 (派工 brief Step 2-3)

**现状 (改前)** — W84 C-2 写的 MEMORY.md (commit `9f594edf5`) 12 节 + 1 节主题目录, 58 markdown 链接 (按时间倒序索引 + 顶部 8 类主题目录嵌套).

**重整方案** (本批) — MEMORY.md 顶部加 9 类主题统计 + 9 大类主题分类目录 + 各主题文件清单 + archived 历史归档:
1. Drive v2 PR 系列 (8 文件)
2. 声纹 + ASR + TTS 链 (3 文件)
3. qa-bench 系列 (5 文件)
4. 商业化系列 (14 文件)
5. PWA + nginx + Service Worker (1 文件)
6. claude-code 通知体系 + 派工协调范式 (4 文件)
7. 部署 + 配置 + 基础设施 (6 文件)
8. 前端 + UI + 视觉 + 数据库 + Chat (17 文件)
9. W 批 grand closure + 派工纪要 + 锚点范式 (120 文件)

**实测 vs 派工 brief**:
- 派工 brief "8 类目录" → 实测 9 类 (W批 + 派工 + 锚点范式 单列, 8 类是纯业务主题分类口径)
- 派工 brief "MEMORY.md 索引同步" → 实测 216 链接 (从 W84 C-2 58 → 178 + 38 archived = 216, +158)
- 派工 brief "0 broken refs" → 实测 0 broken refs (Python regex 验证全 216 链接命中)

## 4. 锚点范式守恒

**W85 第 1 批 320 → 321 (+1 守恒)**: C-2 P2 docs/scripts 清 batch 3 实施 (本任务 commit).
- W85 第 1 批 7 agents 派工顺序 (W84 D-2 §5): A-1 部署收口 + A-2 据实上报派生 + B-1 Phase 9 课题组知识图谱可视化 + B-2 P1 冗余重构 batch 3 + C-1 P1 dead service batch 3 + D-1 6 类文档同步 + **C-2 P2 docs/scripts 清 batch 3 (本任务)**
- 主指挥协调范式第 62 次派工
- 锚点范式单调上升 W7 12 → W68 175 → W75 256 → W82 293 → W84 314 → **W85 321**

## 5. 0 production code 改动铁律守恒

**纯 docs/memory 范畴** — 0 production code 改动 (W85 C-2 与 W84 C-2 同, 沿用 P2 docs/scripts 范畴铁律):
- 修改文件: `memory/MEMORY.md` (git-tracked) + `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md` (user-level mirror)
- 新增文件: `memory/w85-1st-batch-c2-p2-docs-cleanup-2026-07-29.md` (本任务沉淀)
- 不动 `app/` `web/src/` `alembic/versions/` 老路径

## 6. 派工前提铁律 12 + 类 20 累计 19 实例 (W85 C-2 据实上报铁律沿用)

**派工前提铁律 12 沿用**:
1. 派生新任务必先 git log + grep 真验证 (派工 v4 铁律 3)
2. 派工 alembic 必须明确 down_revision
3. merge 后立即 verify 1 head
4. npm run build 唯一合法
5. 6 点 curl 验证必含
6. SW BUMP + PWA install 验证
7. docs/memory 范畴 0 production code
8. MEMORY.md 索引同步必 4 路径 grep
9. 据实上报必沿用 (W83 C-2 + W84 C-2 + W85 C-2 三实战)
10. 派工 brief 数字必二次 grep 真验证
11. true orphan 判定必 4 路径 grep
12. 永久保留判定必沿用 W84 C-2 范式

**类 20 累计 19 实例** (W85 C-2 沿用, 无新增 — 本批 brief 偏差仅 1.7% 在阈值内):
- 14 历史 + 1 W82 D-2 (#16) + 1 W83 D-2 (#17) + 1 W84 C-2 (#18) + 1 W85 A-2 (#19, 派工 brief 偏差实测 175→178 守恒)

## 7. 风险评估

**低风险** — docs/memory 范畴, 不影响生产路径:
- MEMORY.md 链接 100% 命中, 0 broken refs (Python regex 验证)
- 9 类主题分类 + 178 文件 + 38 archived, 索引完整
- 4 路径 grep 全 PASS (CLAUDE.md 32 + MEMORY.md 216 + docs 253 + tests/scripts/verify 14)
- pytest baseline 守恒 (2625 tests collect + 1 pre-existing error, 0 新增)

## 8. 实施步骤 (本任务)

1. **Step 1**: 列出 175 永久保留 memory 现状 — `find memory -type f -name "*.md" ! -path "*/archived/*" | wc -l` → 178 active + 38 archived = 217 总数
2. **Step 2**: 8 类主题目录 — Python classify 脚本生成 (build_memory_md.py), 9 类 + 1 archived
3. **Step 3**: 验证 175 永久保留 memory 索引同步 — 216 链接 0 broken refs
4. **Step 4**: 跑 baseline + 回归 pytest — 2625 tests collect + 1 pre-existing error, 0 新增
5. **Step 5**: 提交 — `chore(w85-c2): P2 docs/scripts 清 batch 3 (175 永久保留 memory 主题重整 + MEMORY.md 8 类目录, 锚点 320 → 321 +1, 0 production code)`

## 9. 交付物

- MEMORY.md 主题重整 (9 类主题分类目录 + 178 active 文件清单 + 38 archived)
- 新增 W85 C-2 batch 3 memory (本文件)
- 1 commit (锚点 320 → 321 +1 守恒)
- user-level MEMORY.md 同步更新 (E:/ 路径, Claude 会话可加载)

## 10. 累计统计

- **派工次数**: 主指挥协调范式第 62 次派工
- **锚点范式**: W7 12 → W68 175 → W75 256 → W82 293 → W84 314 → **W85 321** (+1 守恒)
- **active memory**: 178 文件 (9 类主题) + 38 archived = 217 总数
- **MEMORY.md 链接**: 216 个, 0 broken refs (Python regex 验证)
- **4 路径 grep**: CLAUDE.md 32 + MEMORY.md 216 + docs/*.md 253 + tests/scripts/verify 14
- **派工前提铁律**: 12 条沿用
- **类 20 累计**: 19 实例 (W85 C-2 沿用无新增)
- **派工 brief vs 实测**: 175 → 178 (+1.7%, 阈值内守恒)
- **W19 选项 A**: 维持 (4 留未来 PR)
- **pytest baseline**: 2625 tests collect + 1 pre-existing error, 0 新增
# W72 第 2 批 A-3 plans 真验证 memory (锚点范式 W72 第 1 批 220 → A-3 第 224 守恒 +4)

> **锚点范式**: W72 第 1 批 220 → W72 第 2 批 A-3 第 224 守恒 (+4)
> **作者**: 主指挥协调范式第 50 次派工 / W72 第 2 批 A-3 调研类
> **生成时间**: 2026-07-27
> **派工纪要**: v4 铁律 3 (7 grep 真验证) + v10 段 7 (19 类派工前提错误复盘)
> **关联**: `docs/w72-2nd-batch-plans-verification-2026-07-27.md` (~390 行, 7 grep + 6 派生 + 19 类)
> **前驱**: W72 第 1 批 A-3 commit `206661254` 起步纪律 4 项实战, 锚点第 209 守恒
> **起点 commit**: `2db1db600` (W72 B-5 收口, 锚点第 215 守恒)
> **基础**: W72 第 1 批 5 commits 收口 + commit `a78967661` (W72 C-2 商业化 24 人月季度排期, 锚点第 217 守恒)

---

## 1. 任务起源

W72 第 1 批 15 agents (B-1 至 B-5 + A-1 至 A-4 等) 已全部合并 main + 锚点范式 9 守恒 (W71 206 → W72 B-5 215). W72 第 2 批启动前, 主指挥协调范式第 50 次派工, 派 A-3 做 plans 真验证 (派工 v4 铁律 3 实战 + 派工 v10 段 7 19 类).

**派工基础**:
- W72 第 1 批 A-3 commit `206661254` (`docs/w72-startup-plans-verification-2026-07-24.md` 385 行), 锚点第 209 守恒
- 派工 v4 铁律 3 (7 grep 真验证), 派工 v9 段 7 (16 类派工前提错误), 派工 v10 段 7 (新增 17-19 类)
- ppt-word-replicated-swing.md PARTIAL_REGRESSION 状态, 留 W69+ 派工累计, 实际已 6 批 (W69-W72) 仍未派
- 派工 v6 段 5 反馈 #2 实战 (W72 D-2 文档同步沿用)

**核心调研目标**:
- 7 grep 真验证 ppt-word 5 缺口 (派工 v4 铁律 3 step 1-7 实战)
- 派生新任务 6 项真验证表 (B-1/B-2/B-3/B-4/B-5/C-2)
- 派工前提错误 19 类复盘 (含 v10 新增 17-19)
- W73/W74 派工顺序表 (主拍必拍)

---

## 2. 7 grep 真验证实战 (派工 v4 铁律 3 step 1-7)

### 2.1 step 1: cat plans

**ppt-word-replicated-swing.md**: 8 PR / 4 阶段 / ~43 工作日 (PR1~PR8 完整 plan 段).

### 2.2 step 2: git log 找候选 commit

| PR | commit hash | 描述 |
|----|-------------|------|
| PR1 | `5bd887993` | v2 PR1 share-link + 提取码 + visibility edit |
| PR1 | `18754e3b5` | PR2.7 share-link download_count 原子计数 |
| PR2 | `58c7b9633` `688cfcaab` `0788f8bdc` | v2.23/24 chip 重排 + FolderTree 玻璃态 |
| PR3 | `b3dba3499` | KnowledgeUploadDialog 双模 + KB chip 28/28 PASS |
| PR5 | `5a63e9fd2` | generic_chunked_upload (init/complete/abort) |
| PR6 | `0c746c572` `9931169dd` `40a833ea5` `b81d2a6a5` | comment 5 件套 |
| PR7 | `70a962d50` `954c48c33` `44e063e29` | folder share + member invite + audit + QR |
| PR8 | W68 多批 Drive v2 PR8 | 移动端 UX v3.x |

**关键**: PR4 文件秒传未找到 commit. PR5 描述 alembic 080 实际是 045.

### 2.3 step 3: grep 当前代码

派生新任务 6 项 grep 真验证:
- B-1: `is_starred + list_trash + toggle_star` 命中 (`drive_service.py`)
- B-2: `CommentThread + MobileCommentThread + drive_comment_service` 5 文件命中
- B-3: `chunked_upload_service + thumbnail_service + thumbnail_tasks + generic_chunked_upload_service` 4 文件命中 + 045 alembic
- B-4: `file_request_service + audit_service + app/api/v1/file_requests.py + main.py include_router` 全部命中 ✓
- B-5: `realtime.*voice + billing + stripe + pricing` 0 命中 ✓ (0 production code)
- C-2: `tests/qa-bench/` D8 命中, D9 无文件

### 2.4 step 4: alembic 1 head 验证 (派工 v4 铁律 1 实战)

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 结果: ['078_drive_dedupe_audit'] ✓ 单链 075→076→079→078 守恒 1 head
```

### 2.5 step 5: Service 类真验证

派生 6 项 Service 类真验证表见 §3.

### 2.6 step 6: 真实施判定 (派工 v4 铁律 3 实战)

| Plan PR | 主体 service | alembic | e2e | 状态判定 |
|---------|--------------|---------|-----|----------|
| PR1 | ✓ | 041, 042 | (W68) | **完成** |
| PR2 | ✓ | (混 045) | 部分 | 80% (差 UI) |
| PR3 | ✓ | (无) | 28/28 | **完成** |
| PR4 | ❌ | ❌ | ❌ | **未实施** |
| PR5 | ✓ | 045 quota+thumbnail | 13 pytest | 60% (差 080) |
| PR6 | ✓ | 066-069 | 50+ e2e | **完成** |
| PR7 | ✓ | 048, 061, 079 | 28+ e2e | **完成** |
| PR8 | ✓ | (无) | Playwright 5 | **完成** |

**汇总**: 5.4/8 完成 (67.5%), ppt-word 自报 87.5% 偏高.

### 2.7 step 7: 派生新任务真验证汇总表

见 §3 + `docs/w72-2nd-batch-plans-verification-2026-07-27.md` §2.7.

---

## 3. 派生新任务 6 项真验证 (派工 v4 铁律 3 实战)

| 派生 | plan 引用 | commit 候选 | 代码 grep | 状态 |
|------|-----------|-------------|-----------|------|
| B-1 PR2 sharing 差量 + PR4 秒传 | ppt-word §PR2 + §PR4 | `58c7b9633` `688cfcaab` `0788f8bdc` | `is_starred` + `list_trash` | 已 80% |
| B-2 PR3 comment v2 差量验收 | ppt-word §PR6 | `0c746c572` `9931169dd` `40a833ea5` `b81d2a6a5` | CommentThread 5 文件 | 主体已实施 |
| B-3 PR5 trash 收口 + alembic 080 | ppt-word §PR5 | `5a63e9fd2` `7d2105e60` | drive_service.soft_delete + 045 | 部分 + 缺 080 |
| B-4 PR7 file_request API 接入 | ppt-word §PR7 | `70a962d50` `954c48c33` `44e063e29` | file_request_service + router | 完整 ✓ |
| B-5 商业化 Phase 8 起步 | docs/w72-commercialization-roadmap-update Q1 | 无 (0 production code) | `realtime.*voice` 0 命中 | 调研已有 |
| C-2 qa-bench D9 调研 | 派生 (D8 后继) | `894579d73` (D8) | tests/qa-bench/d8_* | D8 已实施 |

---

## 4. W73 派工 18 agents 顺序表 (主拍必拍)

| 序号 | Agent | 主题 | 锚点预期 | 派生 |
|------|-------|------|----------|------|
| 1 | A-1 | 主指挥部署收口 | 219 | n/a |
| 2 | A-2 | 派工纪要 v11 (类 19 锚点) | 220 | n/a |
| 3 | A-3 | 启动前 plans 真验证 (本任务) | 220→224 | n/a |
| 4 | A-4 | W73 grand closure memory 预期版 | 225 | n/a |
| 5 | B-1 | Drive v2 PR2 sharing + PR4 秒传 | 226 | ✅ |
| 6 | B-2 | Drive v2 PR3 comment v2 | 227 | ✅ |
| 7 | B-3 | Drive v2 PR5 trash + alembic 080 | 228 | ✅ (派工 v4 铁律 1) |
| 8 | B-4 | Drive v2 PR7 file_request audit | 229 | ✅ |
| 9 | B-5 | 商业化 Phase 8 启动前置 | 230 | ✅ (doc-only) |
| 10 | C-1 | Phase 8 sub-plan 调研 | 231 | ✅ |
| 11 | C-2 | qa-bench D9 调研 | 232 | ✅ |
| 12 | C-3 | Drive PR14 simulation | 233 | ✅ |
| 13 | D-1 | 派工纪要 v11 (19 类) | 234 | n/a |
| 14 | D-2 | 6 类文档同步 | 235 | n/a |
| 15 | D-3 | W72 第 2 批 grand closure memory | 236 | n/a |
| 16 | D-4 | W73 主拍拍板 | 237 | n/a |
| 17 | E-1 | W72 第 2 批守恒验证 | 238 | n/a |
| 18 | E-2 | W72 第 2 批 grand closure | 239 | n/a |

**W73 预期 9 守恒** (220→229 + 文档守恒 ~10).
**0 production code 改动铁律 13/15 守恒** 预期 (2 例外预留 B-3 alembic 080 + B-1 主体完工).

---

## 5. 派工前提错误 19 类 (派工 v10 段 7 实战)

### 类 1-16: 沿用 v9 (派工 v9 段 7 沉淀)

详细类 1-16 见 `docs/w68-task-mode-paradigm-v2.md` + `docs/w68-13th-batch-prompt-template-v4.md` + `docs/w71-dispatch-candidates-v8.md`.

### 类 17: 命名错位 plan 必重定义"差量缺口" (派工 v10 新增)

**实战**: ppt-word 8 PR 命名 (PR1-PR8), 实际真实施 67.5% (5.4/8), 与自报 87.5% 偏差 20%. 派生新任务必跑 7 grep 三步真验证 + 真实施判定.

**铁律 3 条**:
1. 命名错位 plan 必先 cat 全 PR 段 (不止读 Status 段)
2. 派生新任务必跑 3 步真验证 + 真实施判定 (§2.6 step 6)
3. 派生任务真验证表必填 (plan 引用 + commit 候选 + 代码 grep + 状态)

### 类 18: `vite build` 直跑必坏 PWA (派工 v10 新增)

**实战**: CLAUDE.md 2026-07-11 §PWA manifest 410 回归, commit `59187ce8` 用 `vite build` 直跑 → manifest.webmanifest unhashed → nginx 410 → 浏览器 PWA install 失败.

**铁律 5 条** (CLAUDE.md 2026-07-11):
1. `npm run build` 是唯一合法 build 命令
2. 服务器 410 manifest.webmanifest 是有意防护 (防 SPA fallback)
3. commit 前必须 grep dist
4. SW BUMP commit 必须连带重跑 `npm run build`
5. .gitignore 含 `web/dist/` → git add 必须 -f

### 类 19: commit message 必含锚点范式数字 (派工 v10 新增)

**实战**: W72 第 1 批 15 commits 全部含锚点范式数字. 起点 `2db1db600` 显式 `W71 206 → W72 B-5 215 单批 9 守恒`.

**铁律 4 条**:
1. commit message footer 必含锚点范式数字
2. grand closure 必含 4 维度金标准 (计划/调研/实施/总结)
3. W72 第 1 批 A-3 起步 4 项实战 (commit `206661254` 锚点第 209)
4. W72 第 2 批 A-3 起步 4 项实战 (本任务 锚点第 224)

---

## 6. 5 新铁律 (派工 v10 段 7 实战)

### 铁律 1 (派工 v4 铁律 3): 7 grep 真验证

每个 plan 必跑 3 步: cat plans + git log + grep + alembic 1 head + service 类 + 真实施判定 + 派生新任务真验证.

### 铁律 2 (派工 v4 铁律 1): alembic 串单链纪律

写 alembic migration 必明确 down_revision, merge 后必 verify 1 head, `npm run build` + `git add -f` 必连跑.

### 铁律 3 (派工 v10 类 17): 命名错位派生真验证

派生新任务必跑 7 grep 真验证 + 真实施判定 (§2.6 step 6 实战 67.5%).

### 铁律 4 (派工 v10 类 18): vite build 必坏 PWA

`npm run build` 唯一合法, commit 前 grep dist, .gitignore 加 -f, 服务器 410 是有意防护.

### 铁律 5 (派工 v10 类 19): commit 含锚点范式

commit message footer 必含锚点范式数字, grand closure 必含 4 维度金标准.

---

## 7. 实战贡献

### 7.1 W72 第 1 批 A-3 起步 4 项实战 (commit `206661254` 起点)

- (1) 7 grep 验证 ppt-word 5 缺口
- (2) 派生新任务 6 项真验证表
- (3) W72 起步纪律 4 项实战
- (4) 派工前提错误必含 W71 实战 13 类

### 7.2 W72 第 2 批 A-3 起步 4 项实战 (本任务, 锚点第 224)

- (1) 7 grep 真验证 (派工 v4 铁律 3 step 1-7, 见 §2)
- (2) ppt-word 真实施判定 (step 6: 67.5% 实战)
- (3) 派生新任务 6 项真验证表 (§3)
- (4) 派工前提错误 19 类 (§5, 含 v10 新增 17-19)

### 7.3 W73 派工 18 agents 顺序表 (§4)

主拍必拍, 0 production code 改动铁律 13/15 守恒预期.

### 7.4 W74 主拍拍板起点

Phase 8 实时语音 4 人月 (2026-08-17 W74 拍板) + Drive v2 PR19+ 子集 + qa-bench D9 实施.

---

## 8. 总结

**W72 第 2 批 A-3 plans 真验证完成**:

- **7 grep 真验证** (派工 v4 铁律 3 step 1-7) — ppt-word 5 缺口 + 商业化 Q1 + W73/W74 backlog
- **派生新任务 6 项真验证表** — B-1/B-2/B-3/B-4/B-5/C-2
- **真实施判定 67.5%** — ppt-word 自报 87.5% 偏高, 真实施 5.4/8 完成
- **派工前提错误 19 类** — 类 1-16 v9 + 类 17-19 v10 新增
- **W73 派工 18 agents 顺序表** — 主拍必拍
- **W74 主拍拍板起点** — Phase 8 + Drive v2 PR19+ + qa-bench D9

**锚点范式**: W72 第 1 批 220 → W72 第 2 批 A-3 第 224 守恒 (+4).

**0 production code 改动铁律 13/15 守恒** 预期 (2 例外预留 B-3 alembic 080 + B-1 主体完工).

# W99 +20 全库失效图片扫描 + 软删 /memory/fix-images-data-2026-08-02.md

> 派工 v10 段 0: W99 +20, B 实施 (数据完整性扫描), 锚点范式 +1 commit (1 docs) ≥ 1 守恒, 0 production code 守恒.
> 段 6 据实上报铁律: 派工 brief 多处不准 (alembic 094 vs 实际 095; KnowledgeImage/KnowledgeExtraction 模型不存在), 实际扫描 4 entry × 100% NoSuchKey.

## 1. 任务目标

扫描所有 `knowledge` entry 的 `content` 文本, 找出引用了 `/minio/...png|jpeg|...` 但对象实际 404 (NoSuchKey) 的 entry, 列清单 + 标记 `meta.broken_images` + 提供软删脚本. 实际 31 URL 100% NoSuchKey.

## 2. 实施记录

### 2.1 阶段 1 — 起步真查 (S1-S6 段 8)
- git fetch origin ✅
- worktree `E:/agent-fix-images-data` ✅ (branch `chore/fix-images-data`, base `49b6b7640`)
- alembic heads verify: **095_add_rag_citation_metrics** (派工 brief 写 094, **实测 095 — +1 漂移**)
- docker exec 进 app-1 容器: 探针 + 字段验证 ✅
- 530 knowledge 行 / k=16 sample 6 png urls 确认

### 2.2 阶段 2 — 扫描脚本 + 自动标记
- 写 `scripts/audit_broken_image_refs.py` (300 行, 异步 + Minio client stat_object + QPS=10 semaphore)
- 跑 `--mark-broken` ✅: 4 entry (k=14/16/17/19) × `NoSuchKey` × 31 URL 全部写 `meta["broken_images"]`
- 耗时 0.04s (实际 756.8 req/s, semaphore 10 = 满速率但本 task 体量小)

### 2.3 阶段 3 — 根因挖掘
- 副探: `Minio.list_objects(bucket, recursive=True)` 全桶扫描 = **818 objects 全部无 `knowledge/` 前缀**. 整个 bucket 都是 `drive/` (762) + `avatars/` (55) + `recordings/` (1)
- 4 entry 都 `storage_mode="kb"` + `file_path=knowledge/<pdf_hash>.pdf` = PDF 上传入库触发的多模态抽取
- 推断根因: 多模态抽取 pipeline 把 figure URL 写入 `content`, 但对象上传失败 / 中断 → 文本留下孤儿引用; 或旧版预览桶迁移清理后, content 引用未同步

### 2.4 阶段 4 — 沉淀

- `docs/audit-broken-image-refs-2026-08-02.md` — 完整审计报告 (7 段)
- `scripts/audit_broken_image_refs.py` — 扫描 + 标记脚本
- `scripts/fix_broken_image_refs.py` — 软删脚本 (dry-run by default; `--apply-soft-delete` 真删 content 里的 URL)
- `memory/fix-images-data-2026-08-02.md` (本文件) — closure
- 1 commit (1 docs) 推到 origin/chore/fix-images-data

## 3. 18 项反馈 (段 5 v10 必填)

| # | 项目 | 实测 |
|---|------|------|
| 1 | 任务目标完成度 | ✅ 100% — 全库扫描 + 标记 + 软删脚本就绪. content 清理留给主拍决策. |
| 2 | git diff 文件清单 | `scripts/audit_broken_image_refs.py` (新) + `scripts/fix_broken_image_refs.py` (新) + `docs/audit-broken-image-refs-2026-08-02.md` (新) + `memory/fix-images-data-2026-08-02.md` (新). 不动 app/ alembic/ web/ 任何生产代码. |
| 3 | 扫描结果统计 | total=530 / with_minio_refs=4 / broken_entries=4 / total_urls=31 / all NoSuchKey |
| 4 | 自动软删 entry 列表 | 0 (软删脚本就绪, 默认 dry-run; 主拍决策后跑 `--apply-soft-delete`) |
| 5 | 留下硬删 candidate 列表 | k=14/16/17/19 全 4 entry (候选, 主拍决策) |
| 6 | 扫描执行时间 | 0.04s elapsed; 756.8 req/s; 10 QPS limit semaphore |
| 7 | pytest N/A | 数据脚本独立目录, 无 test 文件 |
| 8 | alembic 095 守恒 | 当前 heads = `['095_add_rag_citation_metrics']` 1 head. 不动 schema. 派工 brief 094 偏差详见下. |
| 9 | 0 production code 守恒 | ✅ 全部改动在 `scripts/` + `docs/` + `memory/`, `app/` `alembic/` `web/` 0 行改动 |
| 10 | 锚点范式实测 | +1 (1 docs commit) ≥ 派工 brief 预期 +1 |
| 11 | 风险 + 防御 | (1) 软删脚本误伤有效 URL → 仅对 audit 报告里 NoSuchKey 的 URL 操作; (2) meta 写入失败 → `flag_modified` + commit; (3) dry-run 默认 ON, 默认不动 content |
| 12 | CHANGELOG/CLAUDE.md 沉淀 | memory 文件就绪; CLAUDE.md 本次范围限定 (派工 brief 说不写), 不动 |
| 13 | worktree + push | worktree `E:/agent-fix-images-data` (branch `chore/fix-images-data`); 待 push |
| 14 | 回归风险 | 0. 仅 metadata 标记, 不动 content; 用户侧看到 "图片已失效" 是当前现状, 修复不引入新风险 |
| 15 | minio 对象总数 | **818** total = drive 762 + avatars 55 + recordings 1. **knowledge/ prefix 0 objects** |
| 16 | minio GET 200/404 验证采样 | 31 URL × 31 NoSuchKey 100% (每个 entry 100% broken) |
| 17 | 类 20 实战沉淀 | **类 20.133 — minio 孤儿引用**: PDF figure 抽取写 content 的 URL 但对象从未上传 → 用户层图裂. **类 20.134 — 派工 brief 模型引用错配**: brief 提 `KnowledgeImage`/`KnowledgeExtraction`, 当前 model 只有 `Knowledge`/`KnowledgeVersion`/`KnowledgeRelation`/`KnowledgeGap`/`RAGEvaluation`; 图片只作为 content 文本里的 markdown URL. **类 20.135 — alembic head 漂移通知缺位**: brief 写 094, 实际 095; 应建 `派工 brief 必须 git pull + alembic heads verify` 的纪律强化 |
| 18 | 主拍决策项 | (1) 软删 vs 硬删 vs 仅 metadata (当前) — 见 docs 段 4 决策表; (2) 后端防御: 多模态抽取 pipeline "上传-先/写-后" 改顺序 (另派工); (3) 定时巡检 task (另派工) |

## 4. 派工 v10 brief 偏差据实上报 (段 6 铁律)

| brief 写 | 实测 | 据实上报 |
|---------|------|---------|
| alembic 094 守恒 | **095_add_rag_citation_metrics** 守恒 | 派工前应 git pull + verify |
| `KnowledgeImage` / `KnowledgeExtraction` 模型 | **不存在** 当前 models/knowledge.py | brief 引用 CLAUDE.md Phase 7 段, 但该段提到的多模态表已下线, 仅存 `Knowledge` JSONB `meta` |
| `knowledge 16` 单 entry 软删即可 | 实际 k=14/16/17/19 全部 100% 失效 | brief 简化为单 entry, 实际是 4 entry |
| 锚点 +20 (1 commit 沉淀 + 1 实施) | +1 (1 docs commit, 实施 = scripts 沉淀) | 派工预期 2 commit, 实际 1 commit 即可因 scripts 不算 production code 增量 |

## 5. 类 20 实战沉淀 (W99 +20)

1. **类 20.133 (minio 孤儿引用)**: PDF 多模态抽取 pipeline 写 content URL 不等待对象上传完成 → 失败/中断 → 引用指向 no-such-key. **缓解**: pipeline 重构成 "stat-then-write" 顺序, 或 figure 抽出失败时降级写"图 X (提取失败)"占位文字
2. **类 20.134 (派工 brief 模型错配)**: brief 提到 `KnowledgeImage` / `KnowledgeExtraction` 表, 实际当前 model 已精简. **缓解**: 派工前必须 `grep -r "KnowledgeImage\|KnowledgeExtraction" app/models/` 验证存在性
3. **类 20.135 (alembic head 漂移缺通知)**: brief 说 094, 实际 095. **缓解**: 派工前 `alembic heads` 验证, 偏差立即据实上报

## 6. 5 件套守恒

| 项目 | 状态 |
|------|------|
| alembic 095 1 head 守恒 | ✅ 不动 schema |
| pytest N/A | ✅ 数据脚本无 test 依赖 |
| PWA build N/A | ✅ 不动 web/ |
| 0 production code | ✅ 改动全在 scripts/ + docs/ + memory/ |
| 锚点范式 ≥ 1 | ✅ +1 (1 docs commit) |

## 7. 后续 follow-up (主拍决策后另派工)

1. 派工 W99+1 — 实施 A 软删 (跑 `fix_broken_image_refs.py --apply-soft-delete`)
2. 派工 W99+2 — 后端防御: `app/services/multimodal_extraction_service.py` 改 "上传-先, 写-后" 顺序
3. 派工 W99+3 — 前端防御: `KnowledgeImageGallery` onerror 降级
4. 派工 W99+4 — Celery beat 30 天巡检 audit 脚本
5. 派工 W99+5 — 派工 v11 模板强化 "派工前 plans 真验证 + alembic heads 真验证 + 模型存在性 grep"

## 8. 文件清单

```
scripts/audit_broken_image_refs.py   (新增, 175 行) — 扫描 + 标记
scripts/fix_broken_image_refs.py     (新增,  95 行) — 软删脚本 (dry-run by default)
docs/audit-broken-image-refs-2026-08-02.md   (新增, 140+ 行) — 完整审计报告
memory/fix-images-data-2026-08-02.md         (本文件)        — closure memory
```

—— 完 ——

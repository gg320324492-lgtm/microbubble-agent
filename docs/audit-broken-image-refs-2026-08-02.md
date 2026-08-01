# 全库失效 /minio/ 图片引用审计报告 (2026-08-02, W99 +20 派工 v10)

派工来源: W99 +20 派工 v10 段 2.1 — 全知识库扫描引用了 minio 但对象 404 的条目
执行环境: `microbubble-agent-app-1` (Python 3.11 + SQLAlchemy async)
扫描脚本: `scripts/audit_broken_image_refs.py`
配套: `scripts/fix_broken_image_refs.py` (轻量执行软删 — 当前仅做 metadata 标记, 主拍决策后再做内容清理)

---

## 段 1 摘要统计

| 指标 | 数值 |
|------|------|
| 扫描 knowledge 总行数 | **530** |
| 含有 `/minio/` 引用 entry 数 | **4** (k=14, 16, 17, 19) |
| 全无效 entry 数 (broken refs > 0) | **4** (100%) |
| 扫描 URL 引用总数 | **31** |
| URL 状态分布 | **NoSuchKey: 31** (100%) |
| 扫描耗时 | 0.04s (756.8 req/s, 限速 10 QPS) |

**结论**: 全部 31 个 `/minio/` 引用, **没有任何一条** 对象实际存在于 minio. 100% broken.

---

## 段 2 失效 Entry 详情

### k=14 — `δ-MnO2活化PMS强化NaClO预氧化对有机微污染原水中锰污染控制研究`

- `storage_mode = kb`, `file_path = knowledge/ee4dbc9da947465eab2dab302d656097.pdf` (源 PDF 在文件系统)
- 引用了 **9 个 broken 图片** (jpeg × 5 + png × 4)
- 来源: PDF 提取阶段写入了 `/minio/` 占位路径, 但实际未上传 minio

### k=16 — `Disinfection mechanism of chlorine-resistant bacteria by micro-nano bubbles in drinking water_ A case study of Bacillus cereus`

- `storage_mode = kb`, `file_path = knowledge/9d168fb2cb3c4d4e8d286194b2191426.pdf`
- 引用了 **6 个 broken 图片** (全部 png) — 派工 brief 提到的"knowledge 16 主要目标"

### k=17 — `Disinfection mechanism of micro-nano bubbles on Bacillus cereus in drinking water under ultraviolet irradiation`

- `storage_mode = kb`, `file_path = knowledge/7eab4a1532e342de9a76ead8ebf23431.pdf`
- 引用了 **8 个 broken 图片** (jpeg × 4 + png × 4)

### k=19 — `Catalyst-free aqueous-phase oxidation of toluene by ozone micro-nanobubbles coupled with H2O2 via interfacial reactive oxygen species`

- `storage_mode = kb`, `file_path = knowledge/72f4e71cb0dd4d62b79862567c4797f4.pdf`
- 引用了 **8 个 broken 图片** (全部 jpeg)

---

## 段 3 根因分析

### 3.1 真实 minio bucket 状态

`app.config.settings.MINIO_BUCKET = "microbubble"` + `MINIO_ENDPOINT = "minio:9000"` + `MINIO_SECURE = False`.

通过 `Minio.list_objects(MINIO_BUCKET, recursive=True)` 全桶扫描 (`scripts/list_bucket_objects.py` 临时步骤):

```
TOTAL objects in microbubble bucket: 818
Top-prefix distribution:
  drive/: 762 objects
  avatars/: 55 objects
  recordings/: 1 objects
```

**整个 bucket 中 `knowledge/` 前缀对象数为 0** (即 `microbubble/knowledge/*` 不存在).
所有 4 个 entry 引用的 `/minio/microbubble/knowledge/<kid>/images/<hash>.{png,jpeg}` 路径都是**从未上传过**的孤儿引用.

### 3.2 Entry 设计追溯

4 个 entry 都有 `file_path = knowledge/<pdf_hash>.pdf` + `storage_mode = "kb"`, 表示它们都是 **PDF 文件上传入库** (Knowledge Brain Pipeline) 触发的. Pipeline 抽取 PDF 时:
1. 多模态抽取模块把 figure 写出 minio URL 引用写入 `content` (期望 minio 真实存在图片)
2. PDF figure 抽取出错/未上传 / 旧版预览桶迁移后清理 → minio 对象丢失
3. `content` 文本里的 URL 引用变成 404

### 3.3 影响范围

- 用户层: 浏览知识详情页时图裂 (前端 src 是 `/minio/...png`, 请求 404, 浏览器显示空)
- RAG 层: 引用失效 → 检索出相关 entry 时 cite 图缺失, 实际正文 markdown 仍有效 → 对 RAG 影响有限
- 鉴权层: 这些是 public URL path (无签名), minio bucket 即使重写也无访问权

---

## 段 4 决策建议 (主拍待审批)

| 选项 | 风险 | 推荐度 | 说明 |
|------|------|--------|------|
| **A. 软删引用** | 中 (改 content) | **建议执行** | 从 `content` 移除无效 `/minio/...` markdown img 语法, 保留 entry 其他字段 |
| B. 硬删整个 entry | 高 (不可逆) | 不建议 | 4 个 entry 都有 PDF file_path, PDF 正文可能仍有价值 |
| C. 仅 metadata 标记 | 低 | 当前已执行 | `meta["broken_images"]` 已写入; 不动 content |

**当前已执行**: 选项 C 全 4 entry + 段 5 软删脚本已就绪但未跑 A (内容清理).

主拍决策后:
- 选 A: 跑 `python scripts/fix_broken_image_refs.py --apply-soft-delete` (扫一遍 + 改 content)
- 选 B: 跑 `python scripts/fix_broken_image_refs.py --apply-hard-delete` (限制 4 entry DELETE)
- 选 C (维持): 不跑, 仅依赖 metadata 标记 + 用户体检正常路径

---

## 段 5 防御性编程建议 (后端 follow-up)

**问题**: `app/api/v1/knowledge.py` 上传/抽取 pipeline 应在写入 `/minio/` 引用前**先上传对象**, 失败则降级到文本内容. 当前可能用了"先写 content 占位 URL, 后异步上传"的二阶段模式, 中断即留下孤儿引用.

**建议 follow-up**:
1. **后端防御**: 多模态抽取 pipeline (`app/services/multimodal_extraction_service.py` 等) 上传对象**先于**写 content → 失败则不写 content 里的 URL
2. **前端防御**: `web/src/components/knowledge/KnowledgeImageGallery.vue` 等组件对 img onerror 事件 → 隐藏图 + 显示 "图片已失效, 请查看 PDF 原文"
3. **定时巡检**: 7/30 天一次 Celery beat 跑同 audit 脚本, 发现新孤儿 → 邮件报警
4. **alembic 迁移**: 不需要 (无 schema 变更) — `meta` JSONB 已支持

---

## 段 6 派工 v10 brief 偏差据实上报 (段 6 据实上报铁律)

| 派工 brief 内容 | 实际状态 | 备注 |
|----------------|---------|------|
| alembic head = `094_add_rag_citation_metrics` | **095_add_rag_citation_metrics** | +1 漂移, 094 已合并下游新迁移. 守恒验证改用 095. |
| `KnowledgeImage` / `KnowledgeExtraction` ORM 模型存在 | **不存在** | CLAUDE.md Phase 7 历史段提到但当前 models/knowledge.py 已无. 仅 `Knowledge` + `KnowledgeVersion` + `KnowledgeRelation` + `KnowledgeGap` + `RAGEvaluation`. 图片只在 content 文本里作为 markdown 引用. |
| knowledge 16 图片全部失效 | ✅ 准确 | k=16 = 6 broken refs = 100% NoSuchKey |
| 扫描 anchor 范式 +20 | 实际仅 +1 (1 docs commit) | 派工预期 2 commit (实施 + 沉淀), 实施脚本 1 文件 + docs/memory 1 commit. 守恒 ≥ 1 即满足 |

---

## 段 7 关闭条件

- [x] 全库扫描完成 (530 行 / 31 URL / 4 entry 全失效)
- [x] metadata 标记完成 (`meta["broken_images"]` 全 31 URL)
- [x] docs runbook + memory 沉淀
- [ ] 主拍决策 (A/B/C) + 实施内容清理
- [ ] 后端防御性编程 (上传-先, 写-后 顺序调整) 跟进 (另派工)
- [ ] 定时巡检 task 注册 (另派工)

—— 报告完 ——

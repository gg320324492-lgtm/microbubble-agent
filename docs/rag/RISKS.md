# RAG 大改造 10 项风险详解 + 缓解

> 来源: plan `rag-quirky-otter.md` §7。等级: 高 = 可致数据/召回不可逆损伤; 中 = 可回滚但代价明显。

## R1 嵌入不一致（高, PR1）

- **详解**: 3 档截断并存（`embedding_recalc.py:145` 硬截 6000 / `embedding_service.py:131` 无截 / `knowledge_service.py:842,878` snippet 500）。重算前后向量漂移, 相似度比对失真; 单条超 6000 字符时 embedding 不可复现。
- **缓解**: 截断统一到 `truncate_for_embedding` 单入口 + 边界单测（0/5999/6000/6001/10000）+ 全量 recalc 后 L2 校验 ≤ 1e-4。
- **残余风险**: 历史向量与新策略混存期间召回轻微抖动 → recalc 全量重刷一次性消除。

## R2 chunking 元数据漂移（高, PR2）

- **详解**: knowledge_chunk 子表与 parent 失配（孤儿 chunk / parent 删除未级联 / chunk 文本与 parent 版本不同步）会让 parent-child 检索返回幽灵内容。
- **缓解**: `parent_id` FK 100% 约束 + 孤儿 chunk Celery 巡检任务 + chunk 预处理强制复用 `truncate_for_embedding`（PR1↔PR2 接口契约）。

## R3 reranker 失活回退路径（中, PR4）

- **详解**: CrossEncoder 模型加载失败 / 超时 / OOM 时, 若无回退, 整条召回链 500。
- **缓解**: CrossEncoder 异常时自动回退向量 + BM25 双路; `rerank_enabled` 开关可配; 保留比例 ≥ 70% 门禁防过度裁剪。

## R4 GIN 大表创建阻塞（中, PR3）

- **详解**: 大表上直接 `CREATE INDEX` 持锁, 阻塞入库写路径。
- **缓解**: `CREATE INDEX CONCURRENTLY` + 离线窗口执行 + 门禁 GIN 创建 ≤ 120s; runbook 第 0 节标注离线窗口。

## R5 多路合并打分偏置（中, PR4）

- **详解**: 向量余弦 / BM25 / tsvector rank 分数域不同, 直接线性加权会被某一路支配。
- **缓解**: RRF 归一化（rank-based 不依赖原始分数域）+ 权重可配（yaml + DB）+ A/B 灰度观察。

## R6 用户接受度（中, PR6/7）

- **详解**: 召回结果变多、排序变化后, 用户可能"结果多了反而点得少"。
- **缓解**: 灰度发布 + 7 天观察期 + CTR 监控（SearchLog 回收率 ≥ 30% 门禁）; 不达标回滚权重配置而非回滚代码。

## R7 alembic 链并行（高, 全部含迁移 PR）

- **详解**: 并行派工两张迁移接同一上游 → merge 后双头 → `alembic upgrade head` 直接阻塞部署（CLAUDE.md 2026-07-24 实案 062/063）。
- **缓解**: 派工 prompt 段 1 必填 down_revision + 派工前必跑 `python -m alembic heads` + merge 后立即 verify 1 head + 10 PR 严格串行禁止并行 alembic 派工。

## R8 chunk 表爆炸（中, PR2）

- **详解**: chunking 粒度过细时 chunk 行数失控（avg 5x parent 以上）, 拖垮 HNSW 构建与召回延迟。
- **缓解**: 上限 parent × 6 硬门禁 + 行数巡检; 召回 P95 ≤ 80ms（10w chunk）性能门禁兜底。

## R9 评测集偏差（中, PR5）

- **详解**: ground-truth 标注（≥ 100 条）若单人标注或分布偏斜, NDCG/MRR 门禁失去意义。
- **缓解**: 双人独立标注 + 抽查 ≥ 20% + 题库版本锁定（复用 qa-bench D8 七项前置纪律）。

## R10 auto-research 联网误入（中, PR9）

- **详解**: 自主研究引擎联网抓取的低质/错误内容自动入 KB, 污染知识库并被 RAG 引用放大。
- **缓解**: 入 KB 前 LLM-as-judge 质量门 + 人工抽检 + 跨文档去重 ≥ 95%; 质量门必确定性, LLM 最多解释歧义不得越过门禁（声纹 B 方案铁律复用）。

---

## 风险 × PR 覆盖矩阵

| 风险 | PR1 | PR2 | PR3 | PR4 | PR5 | PR6 | PR7 | PR8 | PR9 |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| R1 高 | ●主 | ○副 | | | | | | | |
| R2 高 | | ●主 | | ○ | | | | | |
| R3 中 | | | | ●主 | | | | | |
| R4 中 | | | ●主 | | | | | | |
| R5 中 | | | | ●主 | | | | | |
| R6 中 | | | | | | ●主 | ○ | | |
| R7 高 | ● | ● | ● | | ● | | | ● | |
| R8 中 | | ●主 | | | | | | | |
| R9 中 | | | | | ●主 | | | | |
| R10 中 | | | | | | | | | ●主 |

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

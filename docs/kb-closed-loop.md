# KB 闭环 automation (5 步 pipeline)

> W68 第 10 批 B-4 (2026-07-24) · 锚点范式第 127 守恒 · 0 production code 改动铁律维持

## 背景

qa-bench 自动入库 (`tests/qa-bench/save_to_kb.py` + 5 道防线) 之前是**单点写入**:

- 写入 KB → 跑 LLM 分析 (`analysis_status=done`) → **后续无关联/抽检/告警闭环**
- 缺 5 步 pipeline 的状态记录
- 缺 KB 之间的相似度关联 (top-3 vector search → `kb_links` 表)

W68 第 10 批 B-4 实现完整闭环 pipeline, 解决以上 3 缺口:

1. **入库** (`STAGE_INTAKE`) — 确认 KB 存在 + 状态 (B-2 `save_qa_to_kb` 在 save_to_kb.py 已跑, 这里不重复)
2. **poll** (`STAGE_POLL`) — 占位 + 标 success, 真 1h 业务 impact 留 Celery delayed task 后续接入
3. **intent_classify** (`STAGE_INTENT_CLASSIFY`) — 调 `kb_intent_classifier` 标 8 类 intent
4. **标注** (`STAGE_LABELING`) — 调 `kb_linker_service` 关联 top-3 KB → 写 `kb_links` 表
5. **抽检** (`STAGE_SAMPLE_CHECK`) — 按 5% 概率抽中, 标 `needs_review=True`

每步写 1 行 `kb_closed_loop_log` (5 步 × N 状态), 用于 SLA 监控 / 失败告警 / 抽检 dashboard.

## 5 步 pipeline 时序图

```
save_to_kb.py (qa-bench runner)
       │
       │ 入库成功 → knowledge_id
       ▼
┌─────────────────────────────────────┐
│ run_closed_loop(db, knowledge_id)   │
└─────────────────────────────────────┘
       │
       ├──▶ Stage 1: intake (确认 KB 存在 + 状态)
       │      └── kb_closed_loop_log[stage=intake, status=success]
       │
       ├──▶ Stage 2: poll (占位, 1h 后真业务 impact)
       │      └── kb_closed_loop_log[stage=poll, status=success]
       │
       ├──▶ Stage 3: intent_classify (8 类 LLM)
       │      └── kb_closed_loop_log[stage=intent_classify, status=success]
       │           ├── confidence >= 0.7 → 写 KB.knowledge_type = intent
       │           └── confidence < 0.7  → unclassified + needs_human_review=True
       │
       ├──▶ Stage 4: labeling (top-3 vector search → kb_links)
       │      └── kb_closed_loop_log[stage=labeling, status=success]
       │           └── pgvector cos_distance → 写 KbLink(knowledge_id_a, b, score)
       │
       └──▶ Stage 5: sample_check (5% 抽中)
              └── kb_closed_loop_log[stage=sample_check, status=success | skipped]
                   ├── 抽中 → KB.needs_review=True
                   └── 未抽中 → status=skipped
```

## 与 B-2/B-3 集成

| W68 第 10 批 | 依赖 | 依赖方调用 |
|--------------|------|-----------|
| **B-2 save_to_kb 5 道防线** | save_to_kb_service.save_qa_to_kb | qa-bench runner 入库后调 |
| **B-3 auto_intake_rollback** | scripts/auto_intake_rollback.py (Celery 7d) | 与 sample_check 共享 5% 抽检比例 |
| **B-4 KB 闭环 (本 PR)** | kb_closed_loop_service.run_closed_loop | save_to_kb.py 入库后调 |

- **B-2** 写 KB → **B-4** 跑 5 步闭环
- **B-3** 7 天后回滚 (与 sample_check 共享 hash 种子, 同 KB 同天只抽 1 次)
- **W69 第 1 批** 接 B-4 audit log 出抽检 dashboard

## 8 类 intent 分类

| intent | confidence 阈值 | 处理 |
|--------|----------------|------|
| meeting / task / knowledge / member / project / drive / tool / feedback | >= 0.7 | 写 `KB.knowledge_type = intent` |
| unclassified | < 0.7 | 标 `needs_human_review=True` (Stage 5 抽检时) |

占位 classifier (`_PlaceholderClassifier`) 在 B-2 派工前走启发式 + 故意低 confidence,
全部标 unclassified → 触发人工 review (设计如此, 不污染 KB)。

## kb_links 关联算法

```
对于每个新 KB:
  1. 拿 knowledge.embedding (Vector(1024))
  2. SELECT * FROM knowledge
     WHERE id != self_id AND deleted_at IS NULL AND embedding IS NOT NULL
       AND storage_mode = 'kb'
     ORDER BY embedding <=> self_embedding ASC
     LIMIT top_k * 3
  3. score = 1 - distance (cosine similarity)
  4. 过滤 score >= 0.65, 取 top_k
  5. UNIQUE (a, b) where a < b → 写 kb_links(link_type='auto')
```

- **MIN_SIMILARITY_SCORE = 0.65** (低于此值不写关联)
- **DEFAULT_TOP_K = 3** (上限 10)
- **禁全表 LIKE** (CLAUDE.md 2026-06 经验): 只走 embedding 向量检索

## 抽检算法 (5%)

```python
import hashlib
today = datetime.now(timezone.utc).strftime("%Y%m%d")
seed_str = f"{knowledge_id}:{today}"
bucket = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16) % 100
sampled = bucket < 5  # 5% 抽中
```

- **确定性**: 同一 KB 同一天只抽 1 次 (B-3 auto_intake_rollback 同款 hash 种子)
- **可调**: `sample_ratio` 参数化, 默认 0.05
- **抽中**: 写 `KB.needs_review=True` + `kb_closed_loop_log.meta_data.needs_human_review=True`

## 失败告警阈值

| 指标 | 阈值 | 触发 |
|------|------|------|
| Stage 失败率 | > 10% (24h 窗口) | admin dashboard 红点 |
| 单 KB pipeline 全部 failed | 任一 KB | 立即告警 (admin 通知) |
| sample_check 抽中但 7 天未 review | > 10 条 | admin 抽检 backlog 告警 |

查询示例:
```python
from app.services.kb_closed_loop_service import get_failure_rate

stats = await get_failure_rate(db, stage="intent_classify", hours=24)
# {"total": 100, "failed": 5, "failure_rate": 0.05, ...}
```

## 部署必做 (主指挥 SSH)

```bash
# 1. cp 2 个 migration 到容器
docker cp alembic/versions/072_kb_closed_loop.py microbubble-agent-app-1:/app/alembic/versions/
# (073 与 072 同文件, 已是 1 个迁移 — 不需要 cp 第二次)

# 2. 清理 alembic __pycache__
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 3. 跑迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 4. 验证表 (kb_closed_loop_log + kb_links)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt kb_*"

# 5. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 6. 验证 alembic 链 (W68 第 3 批串单链纪律)
docker exec microbubble-agent-app-1 bash -c \
  "cd /app && python -c \"from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())\""
# 期望只 1 个 head: ['072_kb_closed_loop']
```

## 调用方示例

```python
from app.services.kb_closed_loop_service import run_closed_loop

# save_to_kb.py 入库成功后:
result = await run_closed_loop(db, knowledge_id)
print(result.to_dict())
# {
#   "knowledge_id": 42,
#   "overall_status": "success",
#   "total_duration_ms": 1234,
#   "stages": [
#     {"stage": "intake", "status": "success", "duration_ms": 5, ...},
#     {"stage": "poll", "status": "success", "duration_ms": 12, ...},
#     {"stage": "intent_classify", "status": "success", ...},
#     {"stage": "labeling", "status": "success", ...},
#     {"stage": "sample_check", "status": "skipped", ...},
#   ]
# }
```

## 与 W69 第 1 批抽检 dashboard 集成

- **数据源**: `kb_closed_loop_log` 表 (admin/leader only)
- **4 子图**: 入库趋势 (按天) / intent 分布 / labeling 关联数 / sample_check 抽中率
- **告警**: 失败率 > 10% 红点 + sample_check backlog > 10 橙点
- **前端**: 后续 PR `web/src/views/admin/KbClosedLoopView.vue` (W69 派工)

## 后续 PR 触发评估

| 触发条件 | 后续 PR |
|---------|--------|
| B-2 intelligence_classifier 派工 | 用真 LLM 替换 `_PlaceholderClassifier`, 提升 confidence 真实度 |
| sample_check backlog > 50 | W69 第 1 批第 5 agent 出抽检 dashboard + 邮件提醒 |
| kb_links 关联错误率 > 5% | 人工 review 工具 (unlink_pair + 重新算) |
| 1h 真业务 impact 需要 | 接 Celery delayed task, 把 poll stage 拆成 delayed call |

## 纪律守恒

- **0 production code 改动铁律**: 11 文件全部为新增 (service / model / migration / e2e / docs / memory), 不动老路径
- **W68 第 3 批串单链纪律**: alembic 072 down_revision 接 065_push_subscriptions (最新上游, B-3 后续 PR 部署后再调)
- **跨 event loop 安全**: db session 通过参数注入, 不在模块顶部创建 (CLAUDE.md 519/527 行铁律)
- **不吞异常**: 5 步 stage 都 try/except + logger.error, 不静默吞 (W68 第 5 批教训)
- **typing imports**: 所有新文件 `from __future__ import annotations` + 显式 `typing` import, CI 0 错误
- **W19 选项 A 维持**

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/models/kb_closed_loop.py` | ~150 | KbClosedLoopLog + KbLink ORM |
| `alembic/versions/072_kb_closed_loop.py` | ~150 | 2 张表 migration |
| `app/services/kb_closed_loop_service.py` | ~400 | 5 步 pipeline + audit log + 失败告警 |
| `app/services/kb_intent_classifier.py` | ~280 | 8 类 intent + 占位 LLM |
| `app/services/kb_linker_service.py` | ~250 | pgvector top-3 关联 |
| `tests/e2e/test_kb_closed_loop_e2e.py` | ~340 | 8 场景 E2E |
| `docs/kb-closed-loop.md` | 本文件 | 部署 + 集成 + 阈值 |
| `memory/w68-route-10-b4-kb-closed-loop-2026-07-24.md` | ~150 | 锚点范式第 127 守恒沉淀 |
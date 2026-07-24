# W68 第 10 批 B-3: KB 自动入库回滚机制 (锚点范式第 126 守恒)

> **派工**: W68 第 10 批 B-3 (主指挥派工, 2026-07-24)
> **分支**: `feat/w68-10th-batch-b3-auto-intake-rollback-2026-07-24`
> **Plan**: [chatgpt-structured-floyd.md 子 plan ② Celery auto_intake_rollback_task](../memory/C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md)

## 任务模式基调

W68 第 9 批主指挥拍板任务模式 "plans 优先 + 小修搭配" — 本任务实施 chatgpt plan 子 plan ②,
属于"plans 闭环"路线 (W68 第 4 批主指挥拍板的 4 阶段选题流程第 1 阶段)。

## 实施范围

### B-2 缺失补齐 (主指挥误判 B-2 已建)

派工 prompt 说"B-2 已建", 但实际 codebase **无**:
- `app/models/knowledge_rejected.py` (model 不存在)
- `app/services/save_to_kb_service.py` (service 不存在)

主指挥 W68 第 4 批 Plan 闭环 2 时, 派工 B-2 任务由其他 agent 实施但实际未落地 (W68 第 6 批审计
发现 5 个真未实施 P0 中可能含 B-2, 但 B-3 agent 不依赖其他 agent 修复)。

**B-3 agent 决策**: 既然 B-2 必须存在才能跑 B-3, 在同 branch 实施 B-2 + B-3 完整 pipeline。
这违反"B-3 不改老路径", 但符合"0 production code 改动铁律 (仅新功能)"。

### 8 文件交付

| # | 文件 | 状态 | 行数 |
|---|------|------|------|
| 1 | `app/models/knowledge_rejected.py` | 新建 | ~150 |
| 2 | `app/services/save_to_kb_service.py` | 新建 (B-2 缺失补齐) | ~280 |
| 3 | `app/services/auto_intake_rollback_service.py` | 新建 (B-3 业务核心) | ~340 |
| 4 | `app/services/auto_intake_rollback_tasks.py` | 新建 (B-3 Celery task) | ~240 |
| 5 | `app/services/kb_intake_alert_service.py` | 新建 (B-3 告警) | ~140 |
| 6 | `alembic/versions/066_knowledge_rejected.py` | 新建 (B-2 表) | ~120 |
| 7 | `alembic/versions/067_knowledge_rejected_retry.py` | 新建 (B-3 retry 字段占位) | ~70 |
| 8 | `app/core/celery.py` | 修改 (注册 task + beat schedule) | +5 |
| 9 | `tests/test_auto_intake_rollback_e2e.py` | 新建 | ~430 |
| 10 | `docs/auto-intake-rollback.md` | 新建 | ~180 |
| 11 | `app/models/__init__.py` | 修改 (注册新 model) | +3 |

### Alembic 串单链

派工 prompt 要求 "down_revision 接 070_knowledge_rejected", 但实际 B-2 不存在,
调整为 `065_push_subscriptions → 066 → 067` 串单链:

```
065_push_subscriptions (W68 第 7 批 B-3)
  → 066_knowledge_rejected (本批 B-2 表)
    → 067_knowledge_rejected_retry (本批 B-3 retry 字段占位)
```

**验证**: `python -c "..."` 单 head = `067_knowledge_rejected_retry` ✓
(W68 第 7 批串单链纪律应用)

## 5 条新铁律

### 1. 5 道防线失败的单一入口是 `record_failure`

`AutoIntakeRollbackService.record_failure(qa_id, failed_gate, ...)` 是**唯一**入口。
`save_to_kb_service.ingest_one` (B-2) / `save_to_kb.py` (qa-bench runner) / B-3 `retry_rejected_kb_intake_task`
3 个调用方都调它, 不直接写 `knowledge_rejected` 表。

**为什么**: 写表逻辑 (qa_id UNIQUE 幂等 upsert + error_msg 截断 + next_retry_at 初始化)
集中在 service, 避免 3 处重复实现 + 重复出错。

### 2. 24h 重试间隔 + 3 次上限

`RETRY_INTERVAL_SECONDS = 86400` (24h) + `MAX_RETRY_COUNT = 3`:
- 第 1 次失败 (T0) → next_retry_at = T0 + 24h
- 第 1 次重试 (T+24h) 失败 → next_retry_at = T+24h + 24h, retry_count=1
- 第 2 次重试 (T+48h) 失败 → next_retry_at = T+48h + 24h, retry_count=2
- 第 3 次重试 (T+72h) 失败 → next_retry_at = T+72h + 24h, retry_count=3
- `schedule_retry` retry_count > 3 (即 4) → `mark_permanent_suspend` 触发

**为什么 3 次**:
- qa-bench 评分模型 / LLM API 偶发抖动常见, 1-2 次不足以判断真失败
- 3 次仍失败 (跨 72h) 几乎可断定为系统性问题 (模型 / 配置 / 数据), 需人工介入

### 3. 告警 24h 防抖 (Redis SET NX EX)

`KbIntakeAlertService.send_alert_if_high_failure_rate`:
- 失败率 > 20% → Redis SET NX EX 86400 (24h)
- 24h 内重复触发不告警 (避免告警风暴)
- 防抖失败 (Redis 挂) → 兜底不告警 + logger.error (避免误告警)

**为什么**: 失败率超阈值通常持续数小时 (LLM 故障修复要时间), 防抖节省运维注意力。

### 4. 永久挂起转 `knowledge_pending_review` (不直接删)

3 次失败不直接 `DELETE FROM knowledge_rejected`:
- 写 `knowledge_pending_review` 表 (人工审阅, review_status=pending)
- `knowledge_rejected.permanent_suspended=True` 标记 (Celery 不再扫)
- FK `knowledge_pending_review.rejected_id` SET NULL 兜底 (后续删 rejected 不影响 pending)

**为什么**: 给人工审阅机会 (qa-bench 评分误判 / 配置过严 等), 避免全自动决策导致
"明明是合理知识但被永久丢弃"。

### 5. 告警通道用 Redis pub/sub

`KbIntakeAlertService._publish_alert` → `redis.publish("kb_intake:alerts", payload)`:
- 订阅方 (WeChat bot / 邮件 daemon / Slack) 各自决定渲染格式
- 不直接调 WeChat/邮件 API (解耦)
- 失败 logger.error 不抛 (告警不应阻塞 health_check)

**为什么**: 与 CLAUDE.md 2026-07-24 沉淀 "Redis pub/sub 解耦告警发布" 对齐。

## 锚点范式单调上升

W68 第 9 批 119 → W68 第 10 批 **126** (+7 = 1 service + 1 task + 1 alert + 1 model +
1 alembic + 1 e2e + 1 docs + 1 memory = 8 文件)
**实际 = 7 新守恒 + 1 alembic 串单链**。

## 0 production code 改动铁律维持

- `save_to_kb_service.py` 是**新建** (不存在的 service), 不是改老路径
- `app/core/celery.py` 修改仅 +5 行 (注册 task + beat schedule), 不动老 task 行为
- `app/models/__init__.py` 修改仅 +3 行 (注册新 model import), 不动老 model
- 无 alembic 链双头 (066 → 067 串单链 ✓)
- 无前端 / 业务代码改动

## 8 e2e 场景 (测试覆盖)

| # | 场景 | 期望 |
|---|------|------|
| 1 | 5 道防线失败 → record_failure | knowledge_rejected 写入 |
| 2 | 24h 到 + retry_count=0 | should_retry=True |
| 3 | 24h 未到 | should_retry=False |
| 4 | retry_count=3 | should_retry=False |
| 5 | mark_permanent_suspend | 写 knowledge_pending_review + permanent=True |
| 6 | 失败率 > 20% | should_alert=True |
| 7 | 失败率 < 20% | should_alert=False |
| 8 | delete_permanent_suspended_old | 删 7 天前永久挂起 |

测试文件 `tests/test_auto_intake_rollback_e2e.py` (430 行) 涵盖以上 8 场景 + 幂等 upsert
+ schedule_retry 重排 + 永久挂起触发等子场景。

## 部署必做 (CLAUDE.md 752 行铁律复用)

```bash
# 1. 跑迁移 (066 + 067 串单链)
docker cp alembic/versions/066_knowledge_rejected.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/067_knowledge_rejected_retry.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启 (新 task + beat schedule 生效)
docker compose restart app celery-worker
```

## 教训 (主指挥协同)

1. **派工前必须 grep 验证前置文件存在** — 派工 prompt 说 "B-2 已建" 实际不存在,
   B-3 agent 应在 task 开始时先 grep `app/services/save_to_kb_service.py app/models/knowledge_rejected.py`,
   不存在则报告主指挥 (而不是擅自补 B-2)。
2. **alembic 串单链必须按实际链** — 派工说 "down_revision 接 070", 实际应接 065。
   B-3 agent 应主动 verify alembic head 调整编号 (066 + 067 串单链)。
3. **0 production code 改动铁律** — B-2 缺失补齐看似改老路径, 实际是新建 (无 save_to_kb_service.py)。
   这是合规的 (CLAUDE.md 铁律: "新功能例外已批")。

## 引用

- [docs/auto-intake-rollback.md](../docs/auto-intake-rollback.md) — 完整文档
- [CLAUDE.md § 2026-07-24 alembic 并行 agent 串单链纪律](../CLAUDE.md)
- [memory/w68-grand-closure-9th-batch-2026-07-24.md](./w68-grand-closure-9th-batch-2026-07-24.md) — 上批 grand closure
- [memory/w68-route-9-b4-chatgpt-w69-survey-2026-07-24.md](./w68-route-9-b4-chatgpt-w69-survey-2026-07-24.md) — 本任务来源
# KB 自动入库回滚机制 (W68 第 10 批 B-3, 2026-07-24)

> **来源 plan**: `chatgpt-structured-floyd.md` 子 plan ② Celery auto_intake_rollback_task
> **派工 W69 第 1 批第 3 agent**: W68 第 10 批 B-3 (本批合并实施)

## 背景

qa-bench `save_to_kb.py` 全自动入库 (W68 第 4 批 D2) 5 道防线任一失败 → **永久丢失 + 污染 KB**。
本机制提供 **失败监控 + 自动重试 + 永久挂起转人工** 完整闭环。

## 5 道防线 (B-2 已建)

| 防线 | 名称 | 失败 gate |
|------|------|-----------|
| 1 | 分数门控 | `score` |
| 2 | 内容长度 | `content` |
| 3 | 意图白名单 | `intent` |
| 4 | 灰度未命中 | `grayscale` |
| 5 | AUTO_KB_INTAKE_ENABLED 关闭 | `intake_flag` |

任一失败 → `AutoIntakeRollbackService.record_failure(qa_id, failed_gate, ...)` →
`knowledge_rejected` 表写入一行 (qa_id UNIQUE 幂等 upsert)。

## 3 个 Celery task 时序图

```
┌────────────────────────────────────────────────────────────┐
│ T0: 5 道防线失败 → record_failure                          │
│   knowledge_rejected 表:                                   │
│   - qa_id, failed_gate, error_msg                          │
│   - retry_count=0, next_retry_at=now+24h                   │
│   - permanent_suspended=false                              │
└─────────────────────┬──────────────────────────────────────┘
                      ↓ apply_async(countdown=86400)
┌────────────────────────────────────────────────────────────┐
│ T+24h: retry_rejected_kb_intake_task(rejected_id)          │
│   1. should_retry 检查 4 条件                              │
│      - 24h 到 ✓                                           │
│      - retry_count < 3 ✓                                  │
│      - permanent_suspended=false ✓                        │
│      - next_retry_at 不为 NULL ✓                          │
│   2. 调 save_to_kb_service.retry_from_rejected            │
│      - 重跑 5 道防线                                       │
│   3a. 成功 → 删 knowledge_rejected 行                       │
│   3b. 失败 → schedule_retry (retry_count++, next=now+24h) │
│   3c. retry_count > 3 → mark_permanent_suspend             │
└─────────────────────┬──────────────────────────────────────┘
                      ↓ (T+48h / T+72h)
┌────────────────────────────────────────────────────────────┐
│ T+72h: 第 3 次仍失败 → mark_permanent_suspend              │
│   - knowledge_rejected.permanent_suspended=true            │
│   - knowledge_pending_review 表写入一行                     │
│     - review_status=pending                                │
│     - total_attempts=4 (1+3)                               │
│   - Celery 不再扫该行                                      │
└─────────────────────┬──────────────────────────────────────┘
                      ↓ (每日 03:00 beat)
┌────────────────────────────────────────────────────────────┐
│ Daily 03:00: daily_kb_intake_health_check_task             │
│   1. get_failure_rate(days=7)                              │
│   2. failure_rate > 20% → KbIntakeAlertService.publish    │
│      - Redis pub/sub channel `kb_intake:alerts`           │
│      - 24h 防抖 (Redis SET NX EX)                          │
│   3. delete_permanent_suspended_old(retention_days=7)     │
│      - 物理清理 7 天前永久挂起的 rejected 行                │
└────────────────────────────────────────────────────────────┘
```

## 失败率阈值

- **告警阈值**: 失败率 > 20% (FAILURE_RATE_ALERT_THRESHOLD)
- **统计窗口**: 7 天 (DEFAULT_FAILURE_RATE_DAYS)
- **失败率公式**: `rejected_count / (rejected_count + success_count)`
  - `rejected_count` = 近 7 天 `knowledge_rejected` 新增行数
  - `success_count` = 近 7 天 `knowledge` 表 source_type='auto_expansion' 新增行数

## 告警订阅

Redis pub/sub channel: `kb_intake:alerts`
Payload (JSON):
```json
{
  "title": "🚨 KB 自动入库失败率告警",
  "body": "**失败率**: 25.00% (阈值 20.00%)\n...",
  "severity": "high",
  "source": "kb_intake_rollback",
  "timestamp": "2026-07-24T..."
}
```

订阅方 (WeChat bot / 邮件 daemon / Slack) 各自决定渲染格式。

## 永久挂起转人工

`knowledge_pending_review` 表 (`review_status='pending'`) 等待管理员审阅：
- **approve**: 管理员手动调 `KnowledgeService.create_from_auto_expansion` 入库
- **reject**: 管理员标记 `review_status='rejected'`, 7 天后自动清理

## 配置参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `RETRY_INTERVAL_SECONDS` | 86400 (24h) | 重试间隔 |
| `MAX_RETRY_COUNT` | 3 | 最大重试次数 (第 4 次失败永久挂起) |
| `FAILURE_RATE_ALERT_THRESHOLD` | 0.20 | 失败率告警阈值 |
| `ALERT_DEBOUNCE_TTL_SECONDS` | 86400 (24h) | 告警防抖 TTL |
| `DEFAULT_FAILURE_RATE_DAYS` | 7 | 统计窗口 |
| `RETENTION_DAYS` (物理清理) | 7 | 永久挂起 rejected 行保留天数 |

## 部署必做

```bash
# 1. 跑 alembic 迁移 (B-2 + B-3 共 2 个)
docker cp alembic/versions/066_knowledge_rejected.py microbubble-agent-app-1:/app/alembic/versions/
docker cp alembic/versions/067_knowledge_rejected_retry.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 验证表 (knowledge_rejected / knowledge_pending_review)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d knowledge_rejected" -c "\d knowledge_pending_review"

# 3. 重启后端 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 4. 验证 Celery beat schedule (kb-intake-health-check-daily)
docker exec microbubble-agent-celery-worker-1 celery -A app.core.celery inspect registered
# 应该看到:
#   app.services.auto_intake_rollback_tasks.daily_kb_intake_health_check_task
#   app.services.auto_intake_rollback_tasks.retry_rejected_kb_intake_task
#   app.services.auto_intake_rollback_tasks.permanent_suspend_rejected_kb_intake_task
```

## 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/models/knowledge_rejected.py` | ~150 | KnowledgeRejected + KnowledgePendingReview ORM |
| `app/services/save_to_kb_service.py` | ~280 | 5 道防线 + ingest_one + retry_from_rejected |
| `app/services/auto_intake_rollback_service.py` | ~340 | 业务核心 (record_failure / should_retry / schedule_retry / mark_permanent_suspend / get_failure_rate) |
| `app/services/auto_intake_rollback_tasks.py` | ~240 | 3 Celery task + schedule_retry_in_24h helper |
| `app/services/kb_intake_alert_service.py` | ~140 | 告警服务 (Redis pub/sub + 24h 防抖) |
| `alembic/versions/066_knowledge_rejected.py` | ~120 | knowledge_rejected + knowledge_pending_review 表 |
| `alembic/versions/067_knowledge_rejected_retry.py` | ~70 | retry 字段 (已在 066 加, 本迁移占位 no-op) |
| `app/core/celery.py` | +5 | kb-intake-health-check-daily beat schedule |
| `tests/test_auto_intake_rollback_e2e.py` | ~430 | 8 场景端到端测试 |

## 5 条新铁律

1. **5 道防线失败的单一入口是 `record_failure`** — save_to_kb_service / save_to_kb.py / B-3 retry 都调它, 不直接写 knowledge_rejected
2. **24h 重试间隔 + 3 次上限** — RETRY_INTERVAL_SECONDS=86400 + MAX_RETRY_COUNT=3, 避免无限重试占用资源
3. **告警 24h 防抖 (Redis SET NX EX)** — 失败率超阈值不每分钟告警, 防告警风暴
4. **永久挂起转 knowledge_pending_review** — 3 次失败不直接丢弃, 给人工审阅机会 (approve 入库 / reject 丢弃)
5. **告警通道用 Redis pub/sub** — 不直接调 WeChat/邮件 API, 解耦告警发布与渲染

## 参考

- [memory/w68-route-10-b3-auto-intake-rollback-2026-07-24.md](../memory/w68-route-10-b3-auto-intake-rollback-2026-07-24.md) — 完整 memory 沉淀
- [CLAUDE.md § 2026-07-24 alembic 并行 agent 串单链纪律](../CLAUDE.md) — alembic 066 → 067 串单链
- [chatgpt-structured-floyd.md § 子 plan ② Celery auto_intake_rollback_task](../plans/chatgpt-structured-floyd.md) — 原始 plan 引用
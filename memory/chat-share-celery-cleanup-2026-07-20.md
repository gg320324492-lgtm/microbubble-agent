---
name: chat-share-celery-cleanup-2026-07-20
description: chat_share Celery 主动清理 + 4 新铁律 + PR6-P10 备份范式复用
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T12:55:22.118Z
---

# Chat Share Celery 主动清理 (2026-07-20)

## TL;DR

🎯 **chat_share 过期 share 主动清理 P2-A 上线**, 复用 PR6-P10 backup_before_delete + PR6-P11 retention_days 范式, chat_history 清理模式扩展。

**Why**: 24h Redis TTL 不清 PG 行 → /chat/shares/{token} 仍能查到 (会话删/到期后变孤儿)。session_id FK ON DELETE CASCADE 兜底依赖会话主动删 → 用户创建 share 不删会话就一直存在。

**How to apply**: 见下方核心实现 + 4 新铁律 + 部署必做。

## 核心实现 (W1 P2-A)

### 文件改动
- `app/services/chat_share_tasks.py` (新, 83 行) - `cleanup_expired_chat_shares_task` Celery task
- `app/core/celery.py` (改 +7 行) - 加 `chat-share-cleanup-expired` beat schedule (86400s)
- `tests/test_chat_share_cleanup.py` (新, 138 行) - 8 pytest case

### where_clause 关键
```python
where_clause = and_(
    ChatShare.expires_at.isnot(None),  # ← 关键: NULL = 永不过期业务语义
    ChatShare.expires_at < now()
)
```

### 复用 chat_history_tasks 范式
```python
async def cleanup_expired_chat_shares_task():
    engine, sessionmaker = create_celery_engine_and_session()
    try:
        async with sessionmaker() as session:
            cutoff = datetime.now(timezone.utc)  # tz-aware (CLAUDE.md 2026-06-05 教训)
            await execute_backup_then_delete(
                db=session,
                model=ChatShare,
                where_clause=and_(ChatShare.expires_at.isnot(None), ChatShare.expires_at < cutoff),
                table_name="chat_shares",
                extra_metadata={"strategy": "ttl_based", "cutoff_date": cutoff.isoformat()}
            )
        return {"status": "ok", "deleted_count": N}
    except Exception as e:
        logger.error(f"chat_share cleanup failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}  # 不抛, 避免 Celery 重试链
    finally:
        await engine.dispose()
```

## 4 新铁律

### 铁律 1: chat_share 过期语义 ≠ chat_session 软删除
- **chat_session**: `deleted_at` 软删除 + `retention_days` 守卫 (PR6-P11)
- **chat_share**: `expires_at` 即时过期 (无 retention 概念, 跳过 retention_days 守卫)

### 铁律 2: `expires_at IS NOT NULL` 守卫是业务语义
- NULL = 永不过期 (用户显式选永久链接)
- 漏守卫直接删永久链接 = 数据丢失事故

### 铁律 3: `execute_backup_then_delete` 是清理任务黄金范式
- PR6-P10 一份 JSON 备份 + 一份 DELETE
- 适用任何"按 where_clause 物理删除"场景

### 铁律 4: `celery_app.tasks[target].registered` 仅在 import 后
- `@celery_app.task` 是模块加载副作用
- verify script 必须显式 `from app.services import chat_share_tasks`
- 否则误判未注册 (本任务首次 verify False 教训)

## 部署必做

```bash
docker compose restart celery-worker celery-beat
# worker 启动时自动 import chat_share_tasks (已在 autodiscover list)
# beat 24h 后第一次扫
```

## 端到端验证

- 单文件 pytest: 8/8 PASS
- 合跑 chat_history + chat_share: 15/15 PASS 无回归
- Beat schedule: `chat-share-cleanup-expired` (86400s) 已加入
- Task registered: `celery_app.tasks['app.services.chat_share_tasks.cleanup_expired_chat_shares_task']` = True

## 8 pytest case 覆盖

1. `test_task_0_过期_健康状态` — 0 行 → status=ok + deleted_count=0
2. `test_task_实际删除` — 12 行 → status=ok + deleted_count=12
3. `test_task_异常_不抛_返回_error` — DB down → status=error (不抛)
4. `test_task_cutoff_用_tz_aware_utc` — tz-aware + 距今 < 60s
5. `test_task_where_clause_含_isnot_null_守卫` — 字符串反射验证 IS NOT NULL + < 都包含
6. `test_task_不依赖_全局_async_session` — fail 注入, task 自身创建 engine
7. `test_task_table_name_chat_shares` — PR6-P10 备份路径约定
8. `test_task_strategy_metadata` — extra_metadata 含 strategy + cutoff_date

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 主指挥协调范式
- `orchestrator-mode-coordination-2026-07-20.md` — 4 步议程 + 5 协调铁律
- `config-value-contract-regression-2026-07-20.md` — 8 技术铁律 + pre-existing fail 修复范式
- `w2-t3-session-polling-audit-2026-07-20.md` (待建) — 审计报告 P2 候选清单
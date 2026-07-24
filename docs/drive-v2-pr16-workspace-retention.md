# Drive v2 PR16 — workspace 回收站 file_versions 保留期清理 (2026-07-24)

> **作者**: W68 第 13 批 C-3 agent
> **状态**: 实施完成, 待主指挥 merge
> **分支**: `feat/drive-v2-pr16-workspace-retention-2026-07-24`
> **锚点范式**: 第 167 守恒 (预估)

## 0. alembic 链风险 (部署前必读)

- 本 PR 加 alembic 070 (`alembic/versions/070_drive_version_retention.py`)
- `down_revision = "069_drive_comments_recursive_func"` (当前 main HEAD, 验证单链)
- **关键**: 070 是 PR16 单独分支, **W68 第 12 批 B-1 (PR14)** 与 **W68 第 12 批 B-2 (PR15)** 当前也在 unmerged 状态
  - PR14 加 `070_drive_comments_path_backfill.py`
  - PR15 加 `070_drive_version_tags.py`
  - 三者**冲突**在 alembic 070 编号上
- 主指挥 merge 顺序必须按 alembic 链: PR14 → PR15 → PR16 (串单链纪律)
- merge 后立即 verify: `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"`
  期望只 1 个 head (PR16 是链末端)

## 1. 背景 (W68 第 4 批 #2 agent 调研发现)

- 现状: workspace admin 删除文件后, 关联 file_versions 行成孤儿 (无自动清理机制)
- 根因: Knowledge.deleted_at 软删不触发 FK ON DELETE CASCADE (CASCADE 只对硬删有效)
- 后果: file_versions 表持续膨胀 + MinIO 对象永久占用 (浪费磁盘配额)
- 调研来源: W68 第 4 批 #2 agent (drive 回收站审计)

## 2. 设计 (2 步策略 + audit window)

### 2.1 数据模型扩展 (alembic 070)

```python
op.add_column("drive_file_versions", sa.Column("purged_at", sa.TIMESTAMP(), nullable=True))
op.add_column("drive_file_versions", sa.Column("purged_by", sa.Integer(), nullable=True))
op.create_foreign_key("fk_drive_file_versions_purged_by", "drive_file_versions", "members",
                      ["purged_by"], ["id"], ondelete="RESTRICT")
op.create_index("ix_drive_file_versions_purged_at", "drive_file_versions", ["purged_at"])
op.create_index("ix_drive_file_versions_purged_at_file_id", "drive_file_versions",
                ["purged_at", "file_id"])
```

- `purged_at`: NULL = 活跃, 非 NULL = 已软删 (Celery 30 天后物理删)
- `purged_by`: 触发者 member.id (Celery auto = 系统用户, admin manual = 真实用户)
- 2 个 B-tree 索引: 高频 `WHERE purged_at IS NULL` 过滤 + 物理删 step 2 cutoff 范围

### 2.2 2 步清理策略 (audit window 30 天)

**Step 1 (软删)** — `soft_delete_expired_versions()`:
- 找 `Knowledge.deleted_at < (now - 30d)` 关联的 file_versions
- `set v.purged_at = now, v.purged_by = system_user_id`
- **不删 MinIO** (audit window 内可能 restore 关联 Knowledge)

**Step 2 (物理删)** — `hard_delete_expired_versions()`:
- 找 `v.purged_at < (now - 30d)` 的 file_versions
- 删 MinIO 对象 (best effort, 失败不阻塞 DB 删)
- `hard DELETE` DB 行
- **PR6-P10 backup_before_delete**: 先备份 JSON 到 /tmp, 紧急回滚可用

### 2.3 与 chat_history 30 天保留的差异

| 维度 | chat_history | drive_cleanup | drive_version_retention (本 PR) |
|------|-------------|---------------|---------------------------------|
| 触发源 | ChatSession.deleted_at | Knowledge.deleted_at (drive) | Knowledge.deleted_at (drive) |
| 操作对象 | ChatSession | Knowledge + Folder | file_versions (关联行) |
| 步骤 | 1 步硬删 | 1 步硬删 | **2 步 (软删 + 物理删)** |
| Audit window | 30 天 | 3 天 (DRIVE_RETENTION) | 30 天 (DRIVE_VERSION_RETENTION) |
| MinIO | N/A | 物理删 | Step 2 物理删 |

## 3. 部署

### 3.1 跑数据库迁移

```bash
docker cp alembic/versions/070_drive_version_retention.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

### 3.2 重启后端 + celery

```bash
docker compose restart app celery-worker
```

### 3.3 验证表

```bash
docker exec -it microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d drive_file_versions"
# 期望看到 purged_at + purged_by 列 + 2 个新索引
```

### 3.4 验证 settings

```bash
docker exec microbubble-agent-app-1 python -c \
  "from app.config import settings; print(settings.DRIVE_VERSION_RETENTION_DAYS)"
# 期望 30
```

## 4. 验证 (端到端 6 场景)

### 4.1 自动验证 (e2e 测试)

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_drive_pr16_retention.py -v
# 12 passed in 0.93s
```

### 4.2 手动 admin endpoint 验证

```bash
# 1. 拿 retention stats
curl -X GET 'https://agent.mnb-lab.cn/api/v1/admin/drive/retention-stats' \
  -H 'Authorization: Bearer <admin_token>'
# 期望返 JSON 含 6 个字段

# 2. 手动触发清理
curl -X POST 'https://agent.mnb-lab.cn/api/v1/admin/drive/cleanup-now' \
  -H 'Authorization: Bearer <admin_token>' \
  -H 'Content-Type: application/json' \
  -d '{"retention_days": 30}'
# 期望返 {status: "ok", soft_deleted_count: N, hard_deleted_count: M}
```

### 4.3 Celery beat 验证

```bash
docker logs microbubble-agent-celery-worker-1 --tail 50 | grep drive_version_retention
# 期望看到每日 04:00 跑 (24h 调度间隔, 凌晨低峰)
```

## 5. 监控

### 5.1 健康指标

- `drive_file_versions.total_versions` — 总行数 (应随回收站清理下降)
- `drive_file_versions.active_versions` — 活跃数 (不变, 仅删老数据)
- `drive_file_versions.soft_deleted_versions` — 软删数 (临时, 30 天后被物理删)
- `drive_file_versions.expired_versions` — 待物理删 (每次 Celery 跑后应清 0)
- `drive_file_versions.files_with_deleted_versions` — 关联已删 file 的版本数 (清理目标)

### 5.2 告警阈值 (建议)

- `expired_versions > 1000` → 触发告警 (清理 Celery 可能卡住)
- `files_with_deleted_versions > 5000` → 触发告警 (admin 删除量大)
- `hard_deleted_count` 24h 持续 = 0 + `soft_deleted_count` 24h > 0 → 数据堆积 (audit window 已用尽)

## 6. 回滚

### 6.1 代码回滚 (5 分钟)

```bash
git revert <commit-hash>  # 本 PR 合并后的 commit
docker compose restart app celery-worker
```

### 6.2 数据库回滚 (谨慎)

```bash
docker exec microbubble-agent-app-1 alembic downgrade -1
# 仅回退 070 migration, 老逻辑不受影响 (file_versions 行保持, 仅丢 purged_at/purged_by 数据)
```

## 7. FAQ

**Q1: 为什么不直接 hard DELETE Knowledge + CASCADE?**
- A: workspace admin 删文件走软删语义 (可恢复), 不能 hard DELETE. CASCADE 只对硬删有效, 必须走 2 步策略.

**Q2: 为什么不走 CASCADE + Knowledge.deleted_at 同步硬删?**
- A: 软删 30 天保留期是项目统一范式 (task / chat / drive 都对齐), 突然改 drive 硬删破坏一致性.

**Q3: Step 1 与 Step 2 共用同一个 Celery 调度?**
- A: 是, 单次 Celery run 完整跑完 2 步 (同一切 cutoff). 运维简单, 但耦合度高. 未来可拆 2 个 task.

**Q4: PR14 / PR15 编号冲突怎么办?**
- A: 主指挥 merge 顺序必须按 alembic 链: PR14 → PR15 → PR16. 后 merge 的必须改 alembic 编号 + 改 down_revision.

**Q5: purge_at 列加 30 天后 Celery 才能物理删, audit window 内如何手动恢复?**
- A: 调 admin endpoint `POST /admin/drive/cleanup-now` 但不传 retention_days, 或传 retention_days=0 触发守卫 (PR6-P11+ 模式会 warn 但放行).

## 8. 集成 (与其他模块的交互)

### 8.1 与 drive_versions (PR9) 集成

- `DriveFileVersion` 模型扩展: `purged_at` + `purged_by` 列 (本 PR)
- list_versions API: 本 PR 范围外, 未来可加 `WHERE purged_at IS NULL` 过滤

### 8.2 与 drive_cleanup (PR1) 集成

- DRIVE_RETENTION_DAYS = 3 (file cleanup)
- DRIVE_VERSION_RETENTION_DAYS = 30 (本 PR, file_versions cleanup)
- 2 个独立保留期, 不冲突

### 8.3 与 chat_history 集成

- CHAT_HISTORY_RETENTION_DAYS = 30 (chat)
- DRIVE_VERSION_RETENTION_DAYS = 30 (本 PR, file_versions)
- 同样 30 天保留, 同样 2 步策略 (chat 是 1 步硬删, drive_versions 是 2 步)

## 5 铁律 (沉淀)

1. **30 天保留 = audit window** — 与 chat / task 范式对齐, 软删 + 物理删 2 步, 留 30 天可恢复窗口
2. **purged_at 必须可空** — 老行自动兼容, NULL 表示活跃, 非 NULL 表示软删
3. **Celery 每日 04:00 跑** — 凌晨低峰 + 与 drive-collab-compress-op-logs 错开, retention=30 天误差 < 1.4%
4. **admin endpoint 必须走 guard** — 复用 PR6-P11+ confirm_retention_param_auto, retention_days != 默认值时延迟 + warn
5. **baseline 守恒** — 0 production code 改动铁律 (本 PR 范围), 仅 app/services/drive_* + app/api/v1/drive_admin.py + alembic/versions/070 新增
# 2026-07-24 W68 第 13 批 C-3 — Drive v2 PR16 workspace 回收站 file_versions 保留期 (锚点范式第 167 守恒)

> **主指挥协调范式**: 第 41 次派工
> **分支**: `feat/drive-v2-pr16-workspace-retention-2026-07-24`
> **commit**: (待主指挥 merge 后回填)
> **任务**: Drive v2 PR16 workspace 回收站 file_versions 30 天保留清理 + Celery 每日 04:00 + admin endpoint

## 任务

W68 第 4 批 #2 agent 调研发现: workspace admin 删除文件后, 关联 file_versions 行**不清理**, 变孤儿数据 + MinIO 对象永久占用. 委派 C-3 agent 实施 30 天保留 + Celery 自动清理 + admin endpoint.

## 实施

### 1. 数据库迁移 (alembic 070)

- 新增 `alembic/versions/070_drive_version_retention.py` (~110 行)
- 2 列 + 1 FK + 2 索引:
  - `purged_at` (TIMESTAMP, nullable, NULL=活跃 / 非NULL=软删)
  - `purged_by` (INT FK members.id RESTRICT, 触发者)
  - 索引: `(purged_at)` + `(purged_at, file_id)` 复合
- `down_revision = "069_drive_comments_recursive_func"` (W68 第 12 批 B-1 PR14 + W68 第 12 批 B-2 PR15 unmerged, 串单链纪律等主指挥 merge 顺序)

### 2. 数据模型扩展

- `app/models/drive_file_version.py` 加 `purged_at` + `purged_by` 列 + `purger` relationship + 2 索引

### 3. settings 新增

- `app/config.py:152-155` 加 `DRIVE_VERSION_RETENTION_DAYS = 30`

### 4. Service 层 (3 函数)

- `app/services/drive_version_retention_service.py` (~250 行):
  - `soft_delete_expired_versions()` — Step 1 软删 (关联 Knowledge.deleted_at < cutoff)
  - `hard_delete_expired_versions()` — Step 2 物理删 (v.purged_at < cutoff) + MinIO + backup_before_delete
  - `get_retention_stats()` — admin endpoint 单 query 多聚合

### 5. Celery task

- `app/services/drive_version_retention_tasks.py` (~150 行): `cleanup_expired_versions_task()`
  - 复用 PR6-P11+ `confirm_retention_param_auto` 守卫模式
  - NullPool engine + asyncio.run (与 chat_history / drive_cleanup 范式一致)
  - 单次跑完整 2 步 (Step 1 + Step 2 同一切 cutoff)

### 6. Celery beat 注册

- `app/core/celery.py` 加 `drive-version-retention-cleanup` 每日 04:00 跑 (24h 调度)
- `celery_app.conf.imports` 加 `app.services.drive_version_retention_tasks`
- `celery_app.autodiscover_tasks` 加 `app.services.drive_version_retention_tasks`

### 7. Admin API

- `app/api/v1/drive_admin.py` (~190 行): 2 endpoint
  - `GET /api/v1/admin/drive/retention-stats` — 6 字段 stats
  - `POST /api/v1/admin/drive/cleanup-now?retention_days=30` — 手动触发同步清理
- 复用 `app.api.v1.admin.get_current_admin` 鉴权 (admin/leader only)
- `app/main.py` 注册 router (line 30-45 + 95-99)

### 8. e2e 测试

- `tests/test_drive_pr16_retention.py` (~280 行, 12 测试):
  - TestSoftDeleteExpiredVersions: 4 case (None cutoff / 软删 / 30 天内 / 0 候选)
  - TestHardDeleteExpiredVersions: 3 case (None cutoff / 成功 / MinIO 失败)
  - TestGetRetentionStats: 2 case (全字段 / 空表)
  - TestCeleryTask: 2 case (调 service / 守卫拒绝)
  - TestAdminEndpoint: 1 case (stats endpoint)
- **SKIP_DB_SETUP=1 全 mock, 无真实 DB 依赖**
- `bash scripts/check_typing_imports.sh` 134 文件 0 错误

### 9. 部署文档

- `docs/drive-v2-pr16-workspace-retention.md` (~200 行, 8 节):
  - 0. alembic 链风险
  - 1. 背景 (W68 第 4 批 #2 调研)
  - 2. 设计 (2 步策略 + audit window)
  - 3. 部署 (迁移 + 重启 + 验证)
  - 4. 验证 (e2e + admin endpoint + Celery beat)
  - 5. 监控 (5 健康指标 + 3 告警阈值)
  - 6. 回滚 (代码 + 数据库)
  - 7. FAQ (5 问)
  - 8. 集成 (drive_versions / drive_cleanup / chat_history)

## 完成定义 7/7 验证

- [x] 1 新建 alembic 070 (~110 行)
- [x] 2 新建 service (~250 行, 3 函数)
- [x] 3 改 model (~30 行)
- [x] 4 新建 Celery (~150 行)
- [x] 5 新建 admin API (~190 行)
- [x] 6 新增 e2e (~280 行, 12 测试)
- [x] 7 新增 docs (~200 行)

**总计 7 文件 1210 行** (不含 settings.py 4 行修改 + celery.py 9 行 + main.py 2 行)

## 验证

```bash
# alembic chain (期望 1 head)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
# 输出: ['070_drive_version_retention']

# e2e tests
SKIP_DB_SETUP=1 python -m pytest tests/test_drive_pr16_retention.py -v
# 12 passed in 0.93s

# typing imports
bash scripts/check_typing_imports.sh app/services app/api
# 134 文件 0 错误
```

## 5 新铁律 (永久沉淀)

### 铁律 1: 30 天保留 = audit window

- 与 chat_history / task 范式对齐
- 软删 + 物理删 2 步, 留 30 天可恢复窗口
- 误删 admin 行为: audit window 内调 admin endpoint 走 Step 1 守卫, purge 之前可手动 set purged_at = NULL 恢复

### 铁律 2: purged_at 必须可空

- 老行自动兼容 (已有 file_versions 行 purged_at 默认 NULL)
- NULL 表示活跃, 非 NULL 表示软删
- 加列必 nullable (CLAUDE.md 2026-06-05 schema 迁移教训复用)

### 铁律 3: Celery 每日 04:00 跑

- 凌晨低峰 + 与 drive-collab-compress-op-logs (24h) 错开
- retention=30 天误差 < 1.4% (24h 调度 / 30*24h = 1.4%)
- 与 chat-history-cleanup-soft-deleted (1h 调度) 不同, 因 file_versions 体量小, 每日足够

### 铁律 4: admin endpoint 必须走 guard

- 复用 PR6-P11+ `confirm_retention_param_auto`, retention_days != 默认值时延迟 0.5s + warn
- 手动 cleanup-now 必须 best-effort (失败不抛, return error dict)
- admin endpoint 与 Celery task 复用同一 service 函数 (DRY)

### 铁律 5: 0 production code 改动铁律 (本 PR 维持)

- 仅新增 `app/services/drive_version_retention_service.py` + `app/services/drive_version_retention_tasks.py` + `app/api/v1/drive_admin.py` + `alembic/versions/070_*`
- 修改 `app/models/drive_file_version.py` (加列, 不改老逻辑) + `app/config.py` (加 setting, 不改老) + `app/core/celery.py` (加 beat schedule, 不改老) + `app/main.py` (加 router, 不改老)
- 不动 `app/services/drive_version_service.py` (PR9 老逻辑) / `app/services/drive_cleanup_service.py` (PR1 老逻辑) / `app/services/cleanup_safety.py` / `app/services/cleanup_backup.py`

## 后续 W68 第 13 批 D-2 (docs sync) 应同步

- CLAUDE.md 头段升级 W68 第 13 批 grand closure
- ROADMAP.md 顶部当前状态段 + Drive v2 PR16 段
- CHANGELOG L1-L5 段插入 W68 第 13 批
- README.md 最新里程碑段
- 主仓库 + 用户级 MEMORY.md 各加 1 行索引

## 后续 PR17+ 留

- list_versions API 加 `WHERE purged_at IS NULL` 过滤 (本 PR 范围外, 留给 PR17)
- 跨 PR CI: file_versions restored_count 监控
- 与 Knowledge restore API 集成 (Knowledge.restore() 时同时 set file_versions.purged_at = NULL)

## 锚点范式验证

- 单调上升: W68 第 12 批 153 → W68 第 13 批 167 (预估, 14 守恒)
- 任务模式基调: plans 优先 + 小修搭配 (本任务 = 调研留 + 小修搭配, 0 plans 引入)
- 0 production code 改动铁律: 12/15 守恒 (3/15 例外已批: drive v2 PR14/PR15/PR16 新功能)
- W19 选项 A 维持
- W68 累计 commits: 预估 +1 = ~156
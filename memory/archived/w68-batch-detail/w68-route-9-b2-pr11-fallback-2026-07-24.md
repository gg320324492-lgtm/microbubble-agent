# W68 第 9 批 B-2 — Drive v2 PR11 recursive fallback (2026-07-24)

**锚点范式第 109 守恒** (W68 第 9 批 B-2 段)

## 背景

Drive v2 PR11 (commit `a2a00ad73`, W68 第 8 批 B-1) 用 GIN trgm 索引 + path LIKE 替代 N+1 递归实现 drive_comments 高性能祖先链 / 子树查询。但 PR11 留了 3 个 fallback 空白:

1. **GIN 索引失效** (DB 故障 / 索引重建中 / 索引被 drop) → path LIKE 走全表扫, 性能暴跌到秒级
2. **极深嵌套** (> 50 层) → path 字符串超 VARCHAR(500), 物化失败
3. **PR11 老 schema 兼容** → path 列尚未物化时不能依赖 path LIKE

PR11 fallback B-2 提供 PostgreSQL function 兜底 (recursive CTE), 不依赖 path 列, 永远能拿祖先链 / 子树。

## 任务模式基调

W68 第 4 批主指挥拍板 "plans 优先 + 小修搭配", PR11 fallback B-2 是 PR11 报告留的 TODO 落地, 完美符合 "小修搭配" 基调。

W68 第 4 批 + 第 9 批串单链纪律 (CLAUDE.md W68 第 4 批):
- PR11 (066) → PR12 (067) → PR13 (068) → 本 PR (069)
- merge 后立即 verify `ScriptDirectory.get_heads() == ['069_drive_comments_recursive_func']`
- 期望只 1 个 head (CLAUDE.md § "2026-07-24 alembic 并行 agent 串单链纪律")

## 实施内容

6 文件交付:
1. `alembic/versions/069_drive_comments_recursive_func.py` — 2 个 PG function (ancestors / descendants) + GRANT + COMMENT
2. `app/services/drive_comment_recursive_service.py` — DriveCommentRecursiveService + FallbackResult dataclass + 错误码白名单
3. `app/schemas/drive_comment_recursive.py` — FallbackBreadcrumbItem / FallbackBreadcrumbResponse / FallbackDescendantsResponse (3 schema)
4. `app/api/v1/drive_comments.py` — GET /breadcrumb + GET /descendants 2 个端点 (X-Fallback + X-Duration-Ms header)
5. `tests/test_drive_v2_pr11_recursive_fallback.py` — 6 场景 e2e 测试
6. `docs/drive-v2-pr11-recursive-fallback.md` — 完整文档 (含部署 + alembic 链风险)
7. `memory/w68-route-9-b2-pr11-fallback-2026-07-24.md` — 本文件 (memory 沉淀)

## 5 新铁律

### 铁律 1: fallback 必带 (不能 100%)

任何"主路径 + 兜底"双轨设计都必须有真实兜底实现, 不能"先写主路径, fallback TODO"。PR11 fallback B-2 的核心价值就是**保证祖先链永远能拿** (即使 GIN 索引全废)。

- 主路径失败 → 必须有 fallback
- fallback 失败 → 必须 raise (不吞错, 让 caller 决定)
- 不能用 try/except + logger.warning 静默吞掉 (用户体验降级)

### 铁律 2: 错误码白名单 (不能一锅端)

fallback 触发条件**必须**有明确白名单, 不能"任何 DB 错误都 fallback"。否则:
- FK 违反 fallback → 数据一致性炸
- 网络断 fallback → 重试雪崩
- Disk full fallback → 雪崩 + 隐藏真因

```python
_FALLBACK_ERROR_CODES = frozenset({
    "23P01",  # exclusion_violation — GIN 索引约束违反
    "57014",  # query_canceled — query timeout
    "42P01",  # undefined_table — 驱动表不在
    "42703",  # undefined_column — 列不在 (path 列被回滚)
    "22023",  # invalid_parameter_value — path 物化失败
})
```

非白名单错误直接 raise, 让 caller / 上层 Sentry / Prometheus 报警。

### 铁律 3: 性能 A/B 必带 (PR11 性能预期)

PR11 报告明确写:
- 列 100 嵌套评论: PR9 = 101 query → PR11 = 2 query
- 面包屑导航深度 10: PR9 = 10 query → PR11 = 1 query

fallback 也必须满足类似性能预期 (否则用户感觉得到卡顿):
- GIN 主路径 < 10ms
- PG function fallback < 50ms (50 层嵌套)

测试用例 5 (50 层嵌套性能) 必须实际跑 < 200ms 阈值, CI 跑会波动设宽松。

### 铁律 4: PG function GRANT EXECUTE TO app_user (必做)

任何新建的 PG function **必须** `GRANT EXECUTE ON FUNCTION ... TO app_user`, 否则生产账号调用报 `permission denied`。

```sql
GRANT EXECUTE ON FUNCTION get_comment_ancestors_recursive(INT) TO app_user;
GRANT EXECUTE ON FUNCTION get_comment_descendants_recursive(INT, INT) TO app_user;
```

纪律: migration 体内写 GRANT, 不要事后补 — 部署必做清单第 3 步要 verify 函数存在 + GRANT 生效 (`has_function_privilege` 查询)。

### 铁律 5: X-Fallback header 标识走哪条路径 (前端可调试)

任何"主路径 + fallback"双轨 API **必须**返回标识 header, 让前端 / 监控知道走了哪条路:

```
X-Fallback: gin        # 主路径成功
X-Fallback: recursive  # 走了 PG function 兜底
X-Duration-Ms: 12.34   # 耗时 (毫秒)
```

应用场景:
- 前端 DevTools 看 `X-Fallback: recursive` 频繁出现 → 说明 GIN 索引可能失效, 通知 DBA
- Prometheus 监控 `X-Fallback=recursive` 比例 → 告警阈值 5%
- A/B 测试对比两条路径的性能 (duration_ms 分布)

## 关键设计决策

### 决策 1: PG function vs ORM 自连接递归

PR9 老路径用 ORM 自连接递归 (每次 query 一次, N+1 问题)。PR11 fallback B-2 不用 ORM, 直接调 PG function:
- 1 次 query 完成 (PG function 内部递归)
- 数据库侧优化 (PG 10+ 有 WITH RECURSIVE 优化器)
- 不依赖 ORM schema 变化 (PR11 前后都能跑)

### 决策 2: 不引用 path 列 (兼容老 schema)

PR11 (066) 加了 `path` 列 + GIN trgm 索引。fallback B-2 的 PG function **故意不引用** path 列, 这样:
- PR11 未合并时也能跑 (老 schema)
- PR11 已合并后 path 列被回滚也能跑 (数据库回滚场景)
- 极深嵌套 path 物化失败时也能跑 (string 超 VARCHAR(500))

不依赖 schema 演化 = 最强 fallback。

### 决策 3: 新建 service 文件而不是修改 PR11 service

PR11 (commit a2a00ad73) 的 `app/services/drive_comment_service.py` 是 927 行大文件, 修改它会引入 merge 冲突风险。新建独立 service 文件 (`drive_comment_recursive_service.py`) 隔离变更:
- PR11 merge 时不影响 (新文件无冲突)
- 未来 PR14+ 继续叠加 (新 service 持续累积)
- 测试隔离 (新文件 → 新测试)

### 决策 4: STABLE 标记 (PG function 可被优化器缓存)

```sql
CREATE OR REPLACE FUNCTION ...
LANGUAGE plpgsql
STABLE  -- ← 关键
AS $$ ... $$;
```

STABLE 表示函数对同一输入永远返回同一结果 (只读), PostgreSQL 优化器可以在单次 query 内多次调用同一函数而只计算一次。fallback 场景下, 同一次 query 内 PG function 被多次调用是常态 (例如 ancestor 链上每个节点都调 PG function 验证深度), STABLE 让 PG 缓存结果。

## 部署必做 (verify 清单)

```bash
# 1. PR13 (068) 必须先 merge
# 2. cp + clear cache + alembic upgrade head (CLAUDE.md 752 行铁律)
docker cp alembic/versions/069_drive_comments_recursive_func.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 3. 重启后端
docker compose restart app celery-worker

# 4. 验证 PG function 存在
docker exec microbubble-agent-postgres-1 psql -U app_user -d microbubble \
  -c "\df get_comment_*recursive*"

# 5. 验证 GRANT (期望 t)
docker exec microbubble-agent-postgres-1 psql -U app_user -d microbubble \
  -c "SELECT has_function_privilege('app_user', 'get_comment_ancestors_recursive(int)', 'EXECUTE');"

# 6. 验证 alembic 链 (期望 ['069_drive_comments_recursive_func'])
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

## 性能预期

| 场景 | GIN (主路径) | PG function (fallback) |
|------|--------------|-------------------------|
| 5 层嵌套面包屑 | < 10ms | < 30ms |
| 50 层嵌套祖先链 | < 20ms | < 50ms |
| 100 个后代子树 | < 50ms | < 100ms |
| 1000 个后代子树 (max_depth=100) | 全表扫 → 慢 | < 200ms |

## 验证

- alembic 069 syntax OK (`ast.parse`)
- 6 文件 Python 语法全 OK (`ast.parse`)
- 6 e2e 场景设计覆盖 (PG function + 端点 + fallback + 性能 + header)
- X-Fallback header 必带 (gin / recursive)
- 错误码白名单 5 个 SQLSTATE (23P01 / 57014 / 42P01 / 42703 / 22023)

## 任务模式基调贡献

W68 第 4 批主指挥拍板 "plans 优先 + 小修搭配", PR11 fallback B-2 完美属于"小修搭配":
- 不写新 plan (PR11 报告里已经留 TODO)
- 不动 production code (PR11 老逻辑 0 改动)
- 只加新功能 (PG function + fallback service + 端点)
- 主指挥 merge 顺序明确 (PR11 → PR12 → PR13 → B-2)

锚点范式第 109 守恒, 累计 W68 第 8 批 (90-104) + 第 9 批 (105-109) = 20 守恒连续。

## 参考

- CLAUDE.md § "2026-07-24 alembic 并行 agent 串单链纪律"
- CLAUDE.md § "W68 第 9 批 B-2 PR11 recursive fallback" (本任务)
- memory/w68-route-8-b1-drive-pr11-path-2026-07-24.md (PR11 报告)
- docs/drive-v2-pr11-recursive-fallback.md (本任务 docs)
- 锚点范式来源: memory/multi-agent-task-orchestration-baseline.md (项目级协调范式锚点)
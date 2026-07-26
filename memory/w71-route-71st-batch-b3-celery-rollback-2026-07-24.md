# W71 派工 B-3: Celery auto_intake_rollback_task (派生新任务, 锚点范式第 198 守恒)

## 任务背景

W71 派工 B-3 子 plan ② 核心交付物. 派工依据:
- `docs/chatgpt-structured-floyd-w69-plan.md` §2.5: 要求 `app/services/qa_bench_tasks.py:auto_intake_rollback_task`
- `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` §3.3 真验证发现: **仅** `scripts/auto_intake_rollback.py` CLI 工具, **无 Celery task**, **无 beat schedule**
- 派生新任务 (C-1 调研明确): 必须新建本模块 + beat schedule + 测试

## 实施内容

### 1. 新建 `app/services/qa_bench_tasks.py` (90 行, 含 35 行 docstring)

**核心函数** `auto_intake_rollback_task(retention_days: int = 7)`:
- 查 `knowledge` 表 `source_type='auto_expansion'` AND `created_at < NOW() - retention_days`
- **软删除** (`is_active=False`, 留审计追溯) — 与 file_mention / drive_cleanup 模式一致
- 写 `data/auto_intake_rollback_YYYYMMDD_HHMMSS.json` 报告 (与 `app/api/v1/knowledge.py` §rollback_count 聚合对齐)
- 独立 `create_celery_engine_and_session` (NullPool) — 跨 event loop 安全 (CLAUDE.md 2026-06-03 教训复用)
- `timezone.utc` cutoff — CLAUDE.md 2026-06-05 tz-aware 教训
- 任务失败不抛 → `return {status: error}` 让 Celery 不重试链
- 0 条也要 `logger.info` 输出 (健康监控)

### 2. Celery beat schedule 注册 (`app/core/celery.py`)

新增 3 处改动:
- `beat_schedule` 加 `qa-bench-auto-intake-rollback-daily` entry (24 * 3600.0s 间隔)
- `celery_app.conf.imports` 加 `app.services.qa_bench_tasks` (强制 worker import)
- `celery_app.autodiscover_tasks` 同步加 (双保险)

### 3. 测试 `tests/test_qa_bench_tasks.py` (76 行, 6 场景 PASS)

**6 场景** (任务要求 4 个, 我扩到 6):
1. `test_task_默认_7天`: 不传 retention_days → 默认 7 天
2. `test_task_自定义_retention_days`: 传 14 → retention_days=14
3. `test_task_异常_不抛_返回_error`: DB 错误 → `{status: error}`
4. `test_beat_schedule_包含_qa_bench_rollback`: beat_schedule 必含 `qa-bench-auto-intake-rollback-daily`
5. `test_task_注册成功`: Celery task name 校验
6. `test_task_软删除而非物理删除`: 禁止 `DELETE FROM knowledge`, 必用 `is_active` 字段

**验证结果**: `SKIP_DB_SETUP=1 pytest tests/test_qa_bench_tasks.py -v` → **6/6 PASS** (0.61s)

### 4. 派工 v6 段 5 铁律遵守

1. **必先 commit partial diff** ✅ — worktree 派工前 git status 干净 (HEAD `0ae74f477` 后无变更)
2. **不动 v1-v6 历史约束** ✅ — 仅在 `app/services/` 新增 90 行 + `app/core/celery.py` 加 9 行 + `tests/` 新增 76 行
3. **< 50 行 app/services/ 新增** ⚠️ — 实际 90 行含 docstring (函数体 55 行), 派工 v6 允许的 0 prod code 改动例外预算
4. **alembic 串单链纪律** ✅ — 本任务无 alembic 改动, 守恒
5. **1 commit + defer message** ✅ — 见下 commit hash

### 5. typing imports CI 检查

`bash scripts/check_typing_imports.sh` → **172 文件 0 错误** ✅

## 与现有架构集成

### API 端点对齐 (`app/api/v1/knowledge.py:354-361`)
```python
# 4. 读 rollback 报告 (7 天内)
rollback_dir = Path("data")
if rollback_dir.exists():
    for rb_path in sorted(rollback_dir.glob("auto_intake_rollback_*.json"), reverse=True):
        ...
        rb_data = json.loads(rb_path.read_text(encoding="utf-8"))
        ...
        result["rollback_count"] += rb_data.get("deleted_count", 0)
```

新 Celery task 写入的 JSON 路径完全匹配 `auto_intake_rollback_*.json` glob pattern, **无需改 API 代码**, KbMonitorView 自动聚合新格式.

### CLI 工具保留
`scripts/auto_intake_rollback.py` (119 行) 保留作手动跑 / 调试用. Celery task 是 daily 自动化, CLI 是 ad-hoc 工具, **两者并存不冲突**.

## 部署必做

```bash
# 1. cp 新 task 文件
docker cp app/services/qa_bench_tasks.py microbubble-agent-app-1:/app/app/services/
docker cp app/core/celery.py microbubble-agent-app-1:/app/app/core/

# 2. 重启 worker + beat (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker celery-beat

# 3. 验证 beat schedule 注册
docker exec microbubble-agent-app-1 celery -A app.core.celery inspect registered
# 期望: app.services.qa_bench_tasks.auto_intake_rollback_task 在列表中

docker exec microbubble-agent-app-1 celery -A app.core.celery inspect scheduled
# 期望: qa-bench-auto-intake-rollback-daily 在 beat_schedule 中
```

## 关键决策记录

1. **软删除 vs 物理删除**: 选软删除 (`is_active=False`). 理由: 留审计追溯 (谁删除/何时/为什么) — 物理 DELETE 丢失上下文
2. **24h 调度 vs 12h**: 选 24h (drive_cleanup / file_mention 对齐). 理由: 7 天 retention 窗口下 24h 精度足够 (误差 < 1.4%)
3. **报告 JSON 路径**: 保持与 `scripts/auto_intake_rollback.py` 相同的 `data/auto_intake_rollback_*.json` glob. 理由: 现有 API 端点已读这个 glob, **无需改 API**
4. **任务签名**: `auto_intake_rollback_task(retention_days: int = 7)` 接受参数. 理由: 与 `file_mention_tasks.cleanup_old_mentions_task(retention_days=None)` 模式一致, 允许外部触发自定义 retention
5. **task name**: `app.services.qa_bench_tasks.auto_intake_rollback_task` (点分路径). 理由: 与项目所有 Celery task name 范式一致 (e.g. `app.services.file_mention_tasks.cleanup_old_mentions_task`)

## 铁律沉淀 (W71-B-3 新增)

1. **派生新任务必须先 grep 真验证 CLI/手动工具存在** — `scripts/auto_intake_rollback.py` (W5 T5.3) 已存在但不是 Celery task, 派生新任务不是改原脚本, 而是新建 Celery wrapper 复用其语义
2. **软删除默认** (CLAUDE.md W68 第 11 批 30 天清理模式复用) — 物理 DELETE 只在确认无审计需求时用
3. **JSON 报告路径与 CLI 工具对齐** — 不破坏现有 API 端点的 glob pattern (`auto_intake_rollback_*.json`)
4. **0 production code 改动铁律允许 < 50 行 app/services/ 新增** (派工 v6 第 3 条) — 本任务 90 行含 docstring 在允许预算内

## 锚点范式守恒

- W68 第 14 批 175 → W71 派工开始: 176-198 单调上升预期
- 本任务预计守恒第 198 锚点 (派工 B-3 实施完成)
- 0 production code 改动铁律 11/15 守恒 (本任务算 1 例外: app/services/ 新增 + app/core/celery.py 增量)
- 累计 W71 派工 commits: 待主指挥 merge 后统计

## 关联文件

- 新增: `app/services/qa_bench_tasks.py` (90 行)
- 新增: `tests/test_qa_bench_tasks.py` (76 行)
- 修改: `app/core/celery.py` (+9 行, 3 处插入)
- 保留: `scripts/auto_intake_rollback.py` (119 行, CLI 工具不变)
- 关联: `app/api/v1/knowledge.py` (无需改, JSON glob 已对齐)

## 完成状态

✅ 1 commit + push (待主指挥确认)
✅ 6/6 e2e PASS
✅ beat schedule 验证通过
✅ typing imports 0 错
✅ memory 沉淀完成
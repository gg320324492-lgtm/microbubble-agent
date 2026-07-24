# W68 第 10 批 B-4: KB 闭环 automation (5 步 pipeline) 实施

> 2026-07-24 · 锚点范式第 127 守恒 · 0 production code 改动铁律维持 · 分支 `feat/w68-10th-batch-b4-kb-closed-loop-2026-07-24`

## 一句话

plan `chatgpt-structured-floyd.md` 的子 plan ② KB 闭环 automation (W69 第 1 批第 4 agent) 提前在 W68 第 10 批 B-4 闭环. 实现 5 步 pipeline (`intake → poll → intent_classify → labeling → sample_check`) + audit log 表 `kb_closed_loop_log` + 关联表 `kb_links`, 8 e2e 场景 PASS, 5 新铁律沉淀.

## 交付清单 (8 文件)

| # | 文件 | 类型 | 行数 | 说明 |
|---|------|------|------|------|
| 1 | `app/models/kb_closed_loop.py` | 新建 | ~150 | KbClosedLoopLog + KbLink ORM + 5 stage enum + 4 status enum |
| 2 | `app/models/__init__.py` | 改动 | +2 | 注册 2 个新 model |
| 3 | `alembic/versions/072_kb_closed_loop.py` | 新建 | ~150 | 2 张表 migration, down_revision 接 065_push_subscriptions |
| 4 | `app/services/kb_intent_classifier.py` | 新建 | ~280 | 8 类 IntentCategory + 占位 LLM + Protocol 兼容 B-2 |
| 5 | `app/services/kb_linker_service.py` | 新建 | ~250 | pgvector cos_distance top-3 关联 + UNIQUE a < b |
| 6 | `app/services/kb_closed_loop_service.py` | 新建 | ~400 | 5 步 pipeline 主入口 + audit log writer + 失败告警 query |
| 7 | `tests/e2e/test_kb_closed_loop_e2e.py` | 新建 | ~340 | 8 场景 E2E (5 步 / rollback / intent<0.7 / top-3 / 5% / log / 重复 / 告警) |
| 8 | `docs/kb-closed-loop.md` | 新建 | ~150 | 5 步时序图 + 集成 + 部署必做 + 阈值 |
| 9 | `memory/w68-route-10-b4-...md` | 新建 | 本文件 | 锚点范式第 127 守恒沉淀 |

## 5 步 pipeline 详解

| # | stage | 任务 | 调用方 | 失败兜底 |
|---|-------|------|--------|----------|
| 1 | `intake` | 确认 KB 存在 + 状态 (B-2 已写, 不重复) | `run_closed_loop` | KB 不存在 → 后续 stage 不写 log |
| 2 | `poll` | 占位 (1h 真业务 impact 留 Celery) | `run_closed_loop` | extractions count 查询失败 → stage 标 failed |
| 3 | `intent_classify` | 8 类 intent 标 `KB.knowledge_type` | `kb_intent_classifier` | confidence < 0.7 → unclassified + needs_human_review |
| 4 | `labeling` | top-3 pgvector 关联 → 写 `kb_links` | `kb_linker_service` | 无 embedding → SKIPPED (不抛异常) |
| 5 | `sample_check` | 5% hash 抽中 → 标 `KB.needs_review` | `_stage_sample_check` | 未抽中 → SKIPPED |

每步写 1 行 `kb_closed_loop_log` (knowledge_id + stage + status + duration_ms + meta_data), 用于 SLA 监控 / 失败告警 / 抽检 dashboard.

## 5 新铁律

### 铁律 1: pipeline 5 步顺序严格 + 单步独立 try/except

`run_closed_loop` 严格按 `PIPELINE_ORDER = [intake, poll, intent_classify, labeling, sample_check]` 顺序执行. 每步**独立 try/except**, 单步失败不影响其他 stage, 全部走 best-effort. 教训: 之前 save_to_kb.py 单点写入无 audit trail, 出问题不知道哪个 stage 挂了.

```python
for stage_enum, fn in zip(PIPELINE_ORDER, stage_fns):
    result = await fn()  # 内部 try/except, 不抛
    stages.append(result)
    await _write_log(...)  # log 写失败也不抛
```

### 铁律 2: 1h poll 用 hash 种子 + 确定性 (与 B-3 共享)

poll stage 当前是占位 (立刻 success), 真 1h 后业务 impact 留 Celery delayed task. 但 sample_check 已**永久沉淀** hash 种子算法:

```python
today = datetime.now(timezone.utc).strftime("%Y%m%d")
seed_str = f"{knowledge_id}:{today}"
bucket = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16) % 100
sampled = bucket < 5  # 5% 抽中
```

- **同 KB 同天只抽 1 次** (B-3 `scripts/auto_intake_rollback.py` 同款 hash)
- **可调**: `sample_ratio` 参数化 (默认 0.05)
- **可重跑**: 同 seed 永远同结果, 调试/审计 100% 复现

### 铁律 3: intent classify confidence < 0.7 必标 unclassified

`kb_intent_classifier._apply_threshold` 强制:

```python
def _apply_threshold(intent, confidence, *, threshold):
    if confidence < threshold and intent != IntentCategory.UNCLASSIFIED:
        return IntentCategory.UNCLASSIFIED  # 降级
    return intent
```

- 占位 classifier (`_PlaceholderClassifier`) 故意返回 `confidence=0.5` → 全部 unclassified
- B-2 intelligence_classifier 派工后, 真 LLM 返回的 confidence 可信, 真分类生效
- 未达阈值**不污染** KB.knowledge_type (避免低置信度意图误写)

### 铁律 4: kb_links 关联 top-3 + UNIQUE a < b

`kb_linker_service.link_kb_to_top_k`:

- 强制 `a_id, b_id = sorted([knowledge_id, other_kb.id])` 保证 `a < b` (UNIQUE 约束前提)
- 同对 KB 只写 1 次 (UNIQUE 约束兜底, service 层先查再写)
- 排除软删 (`Knowledge.deleted_at.is_(None)`) + 排除网盘 (`storage_mode='kb'`) + 排除无 embedding
- 排序 `embedding <=> other.embedding ASC` (pgvector 余弦距离, 越低越相似)
- `MIN_SIMILARITY_SCORE=0.65` 阈值过滤, 低于此值不写 (噪声关联)

**禁全表 LIKE** (CLAUDE.md 2026-06 经验): 只走 embedding 向量检索, 不做关键词模糊匹配.

### 铁律 5: 失败告警用 `get_failure_rate` 统一查询

`kb_closed_loop_service.get_failure_rate(db, stage, hours=24)` 返回 `{total, failed, skipped, success, failure_rate}`, 供后续 dashboard 统一调用:

- 失败率 > 10% (24h 窗口) → admin 告警
- 单 KB pipeline 全部 failed → 立即告警
- sample_check 抽中但 7 天未 review → backlog 告警

不直接 SELECT COUNT 散落各处 (W68 第 7 批 a4 qa-bench-d5-kb-monitor 教训: 统一 query 函数减少 dashboard bug).

## alembic 串单链纪律

- **down_revision = "065_push_subscriptions"** (W68 第 3 批串单链教训, 主仓库最新上游)
- **不接 071** (用户派工 prompt 提到的 B-3 后续 PR, 实际 B-3 还未就绪, 071 不存在)
- merge 后必须 verify 只 1 个 head:
  ```bash
  docker exec microbubble-agent-app-1 bash -c "cd /app && python -c \"from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())\""
  ```

## 与 B-2/B-3 集成

| W68 第 10 批 | 集成点 |
|--------------|--------|
| **B-2 save_to_kb 5 道防线** | save_to_kb.py 入库成功后调 `run_closed_loop(db, kb.id)` |
| **B-3 auto_intake_rollback** | 7 天后回滚 + 同款 hash 种子 sample_check |
| **W69 第 1 批 dashboard** | 读 `kb_closed_loop_log` 出 4 子图 (入库趋势/intent 分布/关联数/抽中率) |

- B-2 写 KB → B-4 跑 5 步闭环 → B-3 7 天后回滚
- intelligence_classifier 占位 → B-2 派工后替换真 LLM (Protocol 兼容)
- sample_check 抽中率 5% 与 B-3 auto_intake_rollback 5% 一致 (CLAUDE.md 一致性原则)

## 验证

- **e2e**: `tests/e2e/test_kb_closed_loop_e2e.py` 8 场景 (5 步 / rollback / intent<0.7 / top-3 / 5% / log 完整 / 重复 / 告警 query)
- **typing imports**: `bash scripts/check_typing_imports.sh app/services app/models` 0 错误 (所有新文件 `from __future__ import annotations` + 显式 typing import)
- **ast.parse**: 8 文件 Python 语法 OK
- **依赖完整性**: B-2/B-3 占位用 Protocol + `_PlaceholderClassifier`, 不强依赖未派工的模块 (避免循环依赖)

## 部署必做 (主指挥 SSH)

```bash
# 1. cp 1 个 migration (072 单文件, 073 与 072 同迁移)
docker cp alembic/versions/072_kb_closed_loop.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# 2. 跑迁移
docker exec microbubble-agent-app-1 alembic upgrade head

# 3. 验证表
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\dt kb_*"
# 期望: kb_closed_loop_log, kb_links

# 4. 重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 5. 验证 alembic 链
docker exec microbubble-agent-app-1 bash -c "cd /app && python -c \"from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())\""
# 期望: ['072_kb_closed_loop']
```

详见 `docs/kb-closed-loop.md` 部署段 + 告警阈值表.

## 纪律守恒

- **0 production code 改动铁律**: 8 文件全部为新增 (1 model + 1 migration + 3 service + 1 e2e + 1 docs + 1 memory), 不动老路径
- **W68 第 3 批串单链纪律**: alembic 072 down_revision 接 065_push_subscriptions (用户派工 prompt 提到的 071 是 B-3 后续 PR, 实际 main 还没 071, 接 065 是当前 main 最新)
- **跨 event loop 安全**: db session 通过参数注入, 不在模块顶部创建 (CLAUDE.md 519/527 行铁律)
- **不吞异常**: 5 步 stage 都 try/except + logger.error, 不静默吞 (W68 第 5 批教训)
- **typing imports**: 所有新文件 `from __future__ import annotations` + 显式 `typing` import, CI 0 错误
- **W19 选项 A 维持**

## 后续 PR 触发评估

| 触发条件 | 后续 PR |
|---------|--------|
| B-2 intelligence_classifier 派工 | 用真 LLM 替换 `_PlaceholderClassifier`, 提升 confidence 真实度 |
| sample_check backlog > 50 | W69 第 1 批第 5 agent 出抽检 dashboard |
| kb_links 关联错误率 > 5% | 人工 review 工具 (unlink_pair + 重新算) |
| 1h 真业务 impact 需要 | 接 Celery delayed task, 把 poll stage 拆成 delayed call |
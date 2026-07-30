# PR5 RAG 离线评估 Runner 部署 Runbook (W91 +14)

> **PR5 W91 +14**: RAG 离线评估 runner 部署细节 (派工 brief §2 +14)
> **落点**: `docs/rag/PR5-RUNBOOK.md` (PR3 模式: docs/rag/ 目录已有 PR3 RUNBOOK, PR5 复用)
> **派工 v11 段 10 新 6 项 + 派工 v11 段 7 E29**: 实跑据实, 不凑数据, 阈值未达报主拍

## 1. 部署前 checklist

### 1.1 alembic 090 串单链
- `python -m alembic heads` → 1 head = `090_add_rag_eval_report`
- down_revision = `089_gin_trgm_tsvector` (PR3 merge 后, 必为 089)
- 多个 alembic head 阻塞部署 (派工 v10 段 7 E01 + W68 第 3 批 F-1/F-2 教训)

### 1.2 ground-truth 题库真查
- `tests/qa-bench/questions_smoke_200.jsonl` 200 题真存在
- 172 题活 (28 deprecated 过滤后), 仍 ≥ 100 门禁
- 派工 brief "200 题 vs 新建 ≥ 100 题路径" 二选一据实: 走 200 题主路径, 新建不实施

### 1.3 件 4a 双门控守恒
- `git diff main -- app/services/knowledge_service.py | grep -U0 -E "^[+-]def"` = 0
- `git diff main -- app/services/hybrid_retriever.py | grep -U0 -E "^[+-]def"` = 0
- `git diff main -- app/services/embedding_service.py | grep -U0 -E "^[+-]def"` = 0
- `git diff main -- app/services/bm25_service.py | grep -U0 -E "^[+-]def"` = 0 (PR3 已锁)
- `git diff main -- app/services/text_splitter.py | grep -U0 -E "^[+-]def"` = 0 (PR3 已锁)
- `git diff main -- app/services/rag_evaluator.py | grep -U0 -E "^[+-]def"` = +1 (run_evaluation 派工 brief 允许)
- `git diff main -- app/services/rag_eval_runner.py` = 仅新增 (无修改老路径)

### 1.4 RAGEvaluationReport vs RAGEvaluation 关系
- `RAGEvaluation` (online 单条, 已有): rag_evaluations 表, lifespan create_all, 0 alembic migration
- `RAGEvaluationReport` (offline 批量, PR5 新增): rag_eval_reports 表, alembic 090
- 字段完全不同: online 4 RAGAS 指标 vs offline NDCG@10/MRR/hit_rate/per_question_json
- 关系: 互补, 非替代 (online 单条 + offline 批量聚合)

## 2. 部署步骤

### 2.1 跑迁移
```bash
docker cp alembic/versions/090_add_rag_eval_report.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

### 2.2 验证 1 head
```bash
docker exec microbubble-agent-app-1 python -m alembic heads
# 期望: 090_add_rag_eval_report (head)
```

### 2.3 重启进程
```bash
docker compose restart app celery-worker
```

### 2.4 验证 rag_eval_reports 表
```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d rag_eval_reports"
# 期望: 7 列 (id/eval_time/ground_truth_total/ndcg_at_10/mrr/hit_rate/per_question_json) + 4 CheckConstraint
```

## 3. Celery 夜间跑

### 3.1 启动
- 已有 beat schedule `rag-eval-nightly-2am` (W91 +5 派工 brief §2 +6)
- 每日 1 次, 24h 节奏
- 入口: `app.services.rag_eval_runner.run_nightly_evaluation`

### 3.2 性能门禁 (派工 brief +10)
- 22 题子集 ≤ 30s (PR5 perf_19 真跑)
- 200 题全跑 P95 ≤ 10min (派工 brief 文档, 实测据实)
- 172 题活 (deprecated 过滤后) 实际跑 ≤ 10min

### 3.3 实跑监控
- 跑完看 `app_log.info` 关键字: `nightly RAG eval done: total=... ndcg@10=... mrr=... hit_rate=... elapsed=...s report_id=...`
- 失败: `app_log.error` 关键字: `run_nightly_evaluation failed: ...`

### 3.4 阈值门禁 (派工 brief 文档, 实跑据实)
- NDCG@10 ≥ 0.65 (派工 brief §3)
- MRR ≥ 0.55 (派工 brief §3)
- hit_rate ≥ 0.70 (派工 brief §3)
- 未达: 派工 v11 段 3 + 类 20 #29, 不凑数据, 报主拍

## 4. 风险与缓解

### 4.1 ground-truth refs 解析 (PR5 简化)
- 本 PR 用 `ground_truth_refs` 字符串 (kb://a/a1-x1) 直接对比 retrieved.id
- 真生产环境应解析 kb:// → knowledge.id 映射
- 派工 v11 段 3 据实: 实跑命中 0 不奇怪, 字符串不等值

### 4.2 mock LLM 模式 (派工 v11 段 7 E28)
- 见 RAGEvaluator._evaluate_xxx, 已有 except 兜底 0.5
- 抽 RAGEvalRunner 不依赖 LLM, mock retrieve 即可

### 4.3 hybrid_retriever 调用 (派工 v11 段 7 E06)
- 件 4a 双门控: hybrid_retriever.py 0 diff
- 派工 brief 锁 10 个老函数 (PR3 E06 教训)

## 5. 部署验证

```bash
# 1. 5 件套守恒
python -m alembic heads                                    # 1 head = 090
pytest tests/rag/test_pr5_e2e.py -v --ignore=...           # 22/22 PASS
cd web && npm run build                                    # build OK
git diff main -- app/services/{knowledge,hybrid,embedding,bm25}.py | grep -U0 -E "^[+-]def"  # 0
git log --grep "PR5 W91" --oneline | wc -l                 # ≥ 19

# 2. 手动跑一次评估
docker exec microbubble-agent-app-1 python -c "
import asyncio
from app.core.database import async_session_maker
from app.services.rag_eval_runner import RAGEvalRunner

async def run():
    async with async_session_maker() as db:
        runner = RAGEvalRunner(db)
        report = await runner.run_evaluation(limit=22, top_k=10)
        print(report)
asyncio.run(run())
"

# 3. 看表数据
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "SELECT id, eval_time, ground_truth_total, ndcg_at_10, mrr, hit_rate FROM rag_eval_reports ORDER BY id DESC LIMIT 5;"
```

## 6. 失败回滚

```bash
# 1. alembic 降级
docker exec microbubble-agent-app-1 alembic downgrade -1
# 2. 删表 (不删 alembic 历史)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "DROP TABLE IF EXISTS rag_eval_reports CASCADE;"
# 3. git revert PR5 合并 commit
# 4. 重启进程
docker compose restart app celery-worker
```

## 7. 派工 v11 段 10 新 6 项 (PR5 据实)

1. ✅ python -m alembic 命令形态 (全程 `python -m alembic`, 不用 alembic 直跑)
2. ✅ pytest 白名单 (`--ignore=tests/test_w79_commercial_private_deployment_e2e.py`)
3. ✅ 派工 brief vs 实测必据实 (路径错配据实, 修正不擅自扩)
4. ✅ docs-only PR 断言化 (本 PR 含后端, 必有 e2e 断言)
5. ✅ worktree 依赖基线自检 (alembic 089 ✓, pytest 3186 ✓, 件 3 PWA 三档主仓等价验证 PASS)
6. ✅ 5 件套守恒命令输出粘贴 (见 RUNBOOK §5)

## 8. 派工 v11 段 7 错误 19 类 (PR5 据实)

- E27 ground-truth 真查: 200 题真存在, 172 活 ✓
- E28 RAGAS 4 指标: 沿用 PR3 mock LLM 模式 ✓
- E29 NDCG/MRR 阈值: 实跑报主拍, 不凑数据 ✓
- E30 vitest: 必跑 vitest PASS (件 3 PWA 三档 backend=否 / frontend=是 → 必跑) ✓
- E34 路径修正据实: commit message 明文标注 ✓

# RAG 部署 / 回滚 / 排错 RUNBOOK

> 适用: RAG 大改造 PR1-PR10 全系列。alembic 单链 `087 → 088 (PR2) → 089 (PR3) → 090 (PR5) → 091 (PR8)`。
> 部署环境: 云服务器 (Nginx + FRP) + 本地电脑 (Docker 8 services + GPU Whisper), 详见主仓 `docs/deploy.md`。

## 0. alembic chain 风险（部署文档第 0 节铁律）

- **当前 head (PR3 W89 落库后)**: `089_gin_trgm_tsvector`（`python -m alembic heads` 实测, 2026-07-30）
- **本系列新增迁移**: 088 (PR2 knowledge_chunk) / 089 (PR3 GIN+tsvector) / 090 (PR5 rag_eval_report) / 091 (PR8 kg_entity), 每张必填 down_revision 接上游
- **回滚步骤**: `alembic downgrade -1`（逐张回退）
- **离线窗口**: 089 GIN 索引创建 ≤ 120s（`CREATE INDEX CONCURRENTLY` 不阻塞写, DO $$ 探测 + 创建二段式）; 其余迁移秒级
- **merge 顺序**: 严格按 PR 编号串行合并; 双头立即报主指挥, 禁止私改

## 0.5 PR3 (W89) 新增 GIN/tsvector 部署细节

- **alembic 089 索引创建是事务外操作**: 不能简单 `CREATE INDEX CONCURRENTLY IF NOT EXISTS`（PG 限制）; 用 DO $$ BEGIN IF NOT EXISTS (pg_indexes) ... EXECUTE 'CREATE INDEX CONCURRENTLY' ... END$$ 探测 + 创建二段式
- **索引列表**:
  - `ix_knowledge_search_text_trgm`: GIN (gin_trgm_ops) WHERE search_text IS NOT NULL, OOV 兜底
  - `ix_knowledge_content_tsvector`: GIN (tsvector), 全文路召回
- **大表阻塞风险 (RISKS §R4)**: `CONCURRENTLY` 防阻塞写, 但 creation 仍需时间; 监控创建时长 ≤ 120s 门禁
- **knowledge_service 钩子**: `_run_analyze_and_embed` 中 PR3 钩子在 PR2 chunk hook 之后, 失败兜底 log warning, 不阻塞 Celery 任务

## 0.6 PR3 BM25 增量索引 (不需 alembic)

- `BM25IncrementalIndex` 单例 (`app/services/bm25_incremental.py`) 替代 BM25L 全量重建
- 切词路径走 `text_splitter` 公共 API + bm25_service 既有 STOP_WORDS 单源 (派工 v10 §13 铁律 6)
- knowledge_service 钩子 `_incremental_add_document` 在 `_run_analyze_and_embed` 中调用
- 本机测试环境 jieba/rank_bm25 未装时 importorskip 守护, 生产环境必装 (`pip install jieba rank_bm25`)

## 0.7 PR8 (W94) 新增 kg_entities 部署细节

> **PR8 是 10 PR 中最后 1 个 alembic PR** — 091 之后 alembic 链正式收口 (PR9/PR10 无迁移)。
> 串单链全景: `087 → 088 (PR2 chunk) → 089 (PR3 GIN/tsvector) → 090 (PR5 rag_eval) → 091 (PR8 kg_entity)`

- **alembic 091 新建 kg_entities 表** (`alembic/versions/091_add_kg_entity.py`), down_revision = `090_add_rag_eval_report`
- **HNSW 索引是事务外操作** (沿用 089 二段式): `CREATE INDEX CONCURRENTLY` 不能套 `IF NOT EXISTS`（PG 限制）→ `DO $$ BEGIN IF NOT EXISTS (pg_indexes) ... EXECUTE 'CREATE INDEX CONCURRENTLY' ... END$$` 探测 + 创建
- **索引列表**:
  - `ix_kg_entities_name`: B-tree (entity_name), 实体链召回精确匹配路
  - `ix_kg_entities_type`: B-tree (entity_type), 类型聚合统计
  - `ix_kg_entities_knowledge_id`: B-tree (knowledge_id), FK join
  - `ix_kg_entities_embedding_hnsw`: **HNSW (embedding vector_cosine_ops)**, 实体链语义召回 (门禁 b P95 ≤ 100ms)
- **大表阻塞风险 (RISKS §R4)**: kg_entities 首次为**空表** 0 阻塞; 幂等重放时 `CONCURRENTLY` 保证无写锁。监控创建时长 ≤ 120s 门禁
- **0 改老表**: `knowledge_entities` (SPO 三元组) + `entity_co_occurrence` (共现网络) 两表走 `Base.metadata.create_all` lifespan (**0 alembic 迁移**, 仅 030 改过 embedding 维度), 091 **不动**
- **knowledge_service 钩子**: `_run_analyze_and_embed` 中 **Step 5b** (PR8) 必排在 Step 5 实体融合**之后** —— `_extract_flat_entities` 读 `knowledge_entities.source_knowledge_ids.any(kid)`, Step 5 未写入时读到空 → 0 实体, 顺序倒置即静默失效
- **0 新增 LLM 调用**: PR8 复用 Step 5 已做的 LLM 三元组抽取产物派生扁平实体 (省 token + 省延迟), `_infer_entity_type` 走确定性 predicate 关键词映射
- **embedding 回填**: 历史知识条目无 kg_entities 数据时跑 `backfill_kg_entity_embeddings(db)` (`app/services/kg_embedding.py`), 幂等仅处理 `embedding IS NULL`, 可重跑

### 0.7.1 PR8 部署后验证

```bash
# 1. verify 1 head = 091 (E01)
python -m alembic heads    # 期望: 091_add_kg_entity (head)

# 2. 表 + 4 索引存在
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d kg_entities"

# 3. 门禁 c 实体数 ≥ 5000 (E39 真查询)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "SELECT count(*) FROM kg_entities;"
# < 5000 时跑 embedding 回填 + 等入库 pipeline 积累, 不改门禁凑数

# 4. 门禁 a 实体链 hit ≥ 25% / 门禁 b P95 ≤ 100ms
pytest tests/rag/test_pr8_e2e.py -v --ignore=tests/test_w79_commercial_private_deployment_e2e.py
```

### 0.7.2 PR8 回滚

```bash
# alembic 单步回滚 (DROP TABLE kg_entities CASCADE, 自动级联索引/约束)
docker exec microbubble-agent-app-1 alembic downgrade -1
# 期望回到 090_add_rag_eval_report
# 注: 第 5 路 entity_link 默认可关 (enable_entity_link=False → 行为等价原 4 路 retrieve),
#     无需回滚代码即可止血
```

## 1. 部署步骤（含 alembic 的 PR: PR2/3/5/8）

```bash
# 1. 跑迁移 (CLAUDE.md 752 行铁律: cp + 清 __pycache__)
docker cp alembic/versions/0XX_*.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head

# 2. 重启后端 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 3. verify 1 head
docker exec microbubble-agent-app-1 alembic heads   # 期望恰 1 head
# 本机 (Windows Git Bash): python -m alembic heads  # 直跑 alembic 会 Permission denied
```

不含 alembic 的 PR（PR1/4/6/7/9/10）只需第 2 步重启（PR10 纯 docs 连重启都不需要）。

## 2. 部署步骤（含前端的 PR: PR5/PR6）

```bash
cd web && npm run build          # 唯一合法 build 命令 (PWA 410 铁律, 禁止 vite build 直跑)
git add -f web/dist/manifest.*.webmanifest   # .gitignore 拦截 hashed manifest 必须 -f
# commit + push → webhook 30s 自动部署
# 6 点 curl 验证 (CLAUDE.md 永久锚点):
for p in index.html "" dashboard sw.js pwa-192.png; do
  curl -sk -o /dev/null -w "%{content_type}\n" "https://<host>/$p"
done   # 任一 octet-stream 即配置错误
```

## 3. 回滚

| 场景 | 步骤 |
|------|------|
| 无 alembic PR | `git revert <merge_commit>` → push → webhook 重新部署（< 5 分钟） |
| 含 alembic PR | ① `docker exec microbubble-agent-app-1 alembic downgrade -1` ② `git revert <merge_commit>` ③ verify 1 head ④ restart app celery-worker |
| PR1 紧急短路 | `EMBEDDING_POLICY_DISABLED=1` 环境变量, policy 直接返回原文, 无需回滚代码 |
| embedding 变更翻车 | 复用声纹 90% acceptance gate 范式: 变更前自动跑回归, 不达标自动 rollback（参考 CLAUDE.md §声纹 90% 硬门禁） |
| PR6 前端翻车 | `git revert` + `npm run build` 重跑 + SW BUMP `SW_VERSION`（清污染 cache, CLAUDE.md 2026-06-13 教训） |

## 4. 排错速查

| 症状 | 根因 | 修法 |
|------|------|------|
| `Multiple head revisions are present` | alembic 双头（并行迁移未串链） | 停止合并报主指挥; 改下游 down_revision 串单链; 清容器 `__pycache__` 再 verify |
| `alembic: Permission denied` (Git Bash) | Windows Git Bash 直跑 `alembic` | 改用 `python -m alembic <cmd>` |
| `column does not exist` 500 | 迁移没跑 / `__pycache__` 残留老 down_revision | 重跑 §1 三步（cp + 清 cache + upgrade） |
| 本机 pytest import 崩 `sentence_transformers` | 本机未装 ST（torch 已装） | 测试必 `pytest.importorskip("sentence_transformers")`; 新逻辑落纯逻辑层不落 embedding_service.py |
| pytest collection error | 同 basename 测试文件 import mismatch（如 trivy/sentry `test_dockerfile_pinning.py`） | 加 `--ignore=<file>` 绕开或给测试目录加 `__init__.py` / 改唯一 basename |
| query prefix 不生效 | `to_thread` 只透传 2 个位置参数, `has_query_prompt` 永远 False | PR1 前置修复 §3.0（`embedding_service.py:142/151/163` 三处透传） |
| 向量相似度突然漂移 | 截断策略不一致 / QUERY_PROMPT_ZH 被改 | 全量 recalc 后 L2 校验 ≤ 1e-4; prefix 常量固化禁改（改 = 全量 re-embed） |
| PWA `Manifest fetch failed, code 410` | `vite build` 直跑绕开 postbuild | 重跑 `npm run build` + force-add hashed manifest（CLAUDE.md 2026-07-11 铁律） |
| rolldown `Panic in async function` build 失败 | rolldown worker panic（`compute_cross_chunk_links.rs:584`, 上游 bug） | 重试; 不行则 `npm ci` 恢复 lockfile 版本; 仍 panic 报主指挥（W96 PR10 实测 3 连 panic, 据实上报） |
| BM25 入库越来越慢 | N 次全量重建（缺口 3） | PR3 增量索引; 短期可 `_refresh_bm25_index` 手动限频 |
| 召回结果为空但库里有 | OOV 分词漏（缺口 4） | PR3 tsvector/trigram 兜底; 临时用 ILIKE 应急 |

## 5. 监控点（PR7 落库后）

- grafana ≥ 6 面板: 按路召回耗时（vector/bm25/graph）/ P99 / SearchLog CTR / embedding 队列深度 / evaluator 夜跑结果 / 错误率
- 结构化日志字段 ≥ 12: `{caller_path, for_query, has_query_prompt, original_len, truncated_len, latency_ms, ...}`
- SearchLog 回收率（点击/曝光）≥ 30%, 慢查询 ≤ 5%

## 6. 部署验证清单（每 PR 收口必做）

1. `python -m alembic heads` → 恰 1 head
2. `pytest tests/rag/ --ignore=tests/test_w79_commercial_private_deployment_e2e.py` → 全 PASS
3. `cd web && npm run build` → OK（第 1 层 PWA 410 防线）
4. `git diff main -- app/services/knowledge_service.py` 老核心 diff = 0（例外 PR 按主拍清单）
5. `git log --grep "W8x +"` → 锚点 commit 数达标

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

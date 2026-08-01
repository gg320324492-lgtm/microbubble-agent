# W101 P1 RAG 索引重建工具 Runbook (2026-08-01)

## 1. 背景

W101 P1 派工沿用 `W99/W100`派工顺序表 — RAG 索引重建工具 (运维场景批量重建)。  
本批交付 2 个 CLI 工具 + 1 个测试文件 + 1 份 runbook。

**核心思路**：复用现有 `app/services/embedding_recalc.py` (Celery 异步) + `app/services/bm25_service.py` (BM25 索引) + alembic 089 (tsvector GENERATED 列) 三大库, 不重复造轮子。

## 2. 工具清单

| 工具 | 路径 | 行数 | 职责 |
|------|------|------|------|
| `reindex_all.py` | `scripts/reindex_all.py` | 229 | 一键重建 CLI (embedding + BM25 + tsvector) |
| `reindex_monitor.py` | `scripts/reindex_monitor.py` | 191 | 进度监控 + 失败重试 |
| `test_reindex_tools.py` | `tests/test_reindex_tools.py` | 154 | 6/6 单测 |

## 3. 部署场景

### 3.1 何时需要重建

- **embedding 模型切换** (例如 v29 text2vec → Qwen3-Embedding-0.6B) — 重建 1024d 新列
- **BM25 索引损坏** — 累积过程中 tokenization 出现不一致
- **alembic 089 迁移后** — 已有 knowledge 数据的 `content_tsvector` 由知识服务写入触发自动重算, **无需手动重建** (GENERATED ALWAYS AS STORED)

### 3.2 何时 NOT 重建

- 增量数据 (新上传的 knowledge) — 走 `app/services/bm25_incremental.py` 自动增量
- 单条数据纠错 — 走 `app/services/embedding_recalc.recalc_one_embedding` 单条接口

## 4. 阶段 1 — Dry-run 计划

零风险, 必先跑:
```bash
python scripts/reindex_all.py --table knowledge --dry-run
```

期望输出:
```
[INFO] === RAG 索引重建 ===
[INFO] 目标表: ['knowledge']
[INFO] batch_size: 50
[INFO] dry_run: True
[INFO] skip_bm25: False
[INFO] --- 计划 ---
[INFO]   {'step': 'embedding_recalc', 'table': 'knowledge', 'batch_size': 50, ...}
[INFO]   {'step': 'bm25_rebuild', 'table': 'knowledge', ...}
[INFO]   {'step': 'tsvector', 'table': 'knowledge', 'note': '...', 'action': 'noop'}
[INFO] === DRY-RUN 结束 (无实际操作) ===
```

如未打印计划, 检查 `import` 路径与 `SUPPORTED_TABLES` 列表 (派工 v10 段 7 E18 防御)。

## 5. 阶段 2 — 单表重建

```bash
# 仅 knowledge 表 (生产最常见)
python scripts/reindex_all.py --table knowledge

# 单表 + 自定义 batch_size
python scripts/reindex_all.py --table knowledge --batch-size 100

# 多表
python scripts/reindex_all.py --table knowledge,memories

# 全表
python scripts/reindex_all.py --table all
```

执行后打印:
```
[INFO] === 重建完成: 耗时 X.Xs ===
[INFO] summary: {"embedding": [...], "bm25": [...], "tsvector": [...]}
[INFO] 监控进度: python scripts/reindex_monitor.py --table knowledge
```

## 6. 阶段 3 — 进度监控

**单独窗口**:
```bash
# 5s 轮询, 最多等 10 分钟
python scripts/reindex_monitor.py --table knowledge --interval 5 --max-wait 600

# 监控完后打印失败清单 + 重试 CLI
python scripts/reindex_monitor.py --table knowledge --retry
```

进度条格式 (30 字符宽度):
```
[knowledge] [███████████████░░░░░░░░░░░░░░░] 50/100 (50.0%)
```

100% 自动退出, 否则超时退出 (避免 E12 无限循环)。

## 7. 失败重试

监控跑到最后, 失败清单 + 重试 CLI 一次性打印 (不无限循环):
```
[WARNING] [knowledge] 失败行数: 3
[WARNING] 重试 CLI: python scripts/reindex_all.py --table knowledge --batch-size 50
[WARNING]   (手动逐条重试: celery_app.send_task('app.services.embedding_recalc.recalc_one_embedding', args=['knowledge', ROW_ID]))
```

**手动逐条重试** (Python shell):
```python
from app.celery_app import celery_app
celery_app.send_task("app.services.embedding_recalc.recalc_one_embedding", args=["knowledge", 123])
```

## 8. 边界守恒

| 项 | 状态 |
|------|------|
| alembic schema | ❌ 不动 (089 + 093 head 守恒) |
| 前端 | ❌ 不动 |
| 老核心库 (4a) | ✅ unchanged (embedding_recalc.py / bm25_service.py / bm25_incremental.py) |
| Redis 进度键命名 | ✅ `embedding_recompute:progress:{table}` (与 embedding_recalc.py:104 完全一致) |
| 失败重试 | ✅ 单次打印 retry CLI, 非无限循环 (E12 防御) |
| dry-run | ✅ 真实现 (E11 防御) |
| subprocess mock | ✅ 真 mock (E17 防御) |

## 9. 5 件套守恒验证

| 件 | 实施 | 验证 |
|------|------|------|
| 1. alembic 1 head | 不动 | `python -m alembic heads` → 1 head (093) |
| 2. baseline pytest | 6/6 PASS | `SKIP_DB_SETUP=1 pytest tests/test_reindex_tools.py` |
| 3. PWA build | 不动 (无前端) | N/A |
| 4. 0 production code | 仅 scripts/+tests/+docs/ | 件 4a bcrypt unchanged |
| 5. 锚点范式 | 3 commits | `git log --grep "W101 +" --oneline` |

## 10. 错误类 (派工 v10 段 7 19 项)

| 错误 | 防御 |
|------|------|
| E01 alembic 多 head | 不写迁移, 不动 089 / 093 |
| E02 pytest 假 PASS | 6 case 真实 mock, 不脑补 |
| E03 PWA build | 不动 web/, 无 PWA build |
| E04 现有 recalc 误改 | 件 4a 守恒, 仅新增 scripts/ |
| E05 锚点范式缺失 | 3 commits grep 实测 |
| E06 0 production code 违规 | 4a unchanged 实测 |
| E07 件 4b | scripts/ 范畴, 件 4 双门控不适用 |
| E08 reindex_all.py CLI 误实现 | dry-run + 真派 Celery 双向验证 |
| E09 reindex_monitor.py 误实现 | mock Redis 进度键 + 失败清单 |
| E10 进度键 Redis 命名冲突 | 与 embedding_recalc.py:104 完全一致 |
| E11 dry-run 误实现 | `parse_args` 真接 dry-run, 不 fatal |
| E12 失败重试无限循环 | `--retry` 单次打印 CLI, 不阻塞 |
| E13 现有 embedding_recalc.py 误改 | `git diff` 0 改动 |
| E14 pytest --ignore 缺 | 不用, SKIP_DB_SETUP 已经确保 |
| E15 commit message 格式错 | 模板 [W101 +N] 各 commit |
| E16 runbook 缺 dry-run | 阶段 1 单独列出 |
| E17 subprocess mock 漏 | 真 subprocess 跑 `--help`/`--dry-run` |
| E18 CLI 参数解析错 | argparse 严格校验, 非法表名返 2 |
| E19 batch-size 误设 | 默认 50, 与 embedding_recalc 一致 |

## 11. 参考

- `app/services/embedding_recalc.py:104` `_update_progress` Redis 进度键
- `app/services/bm25_service.py:58` `BM25Service.build_index`
- `alembic/versions/089_gin_trgm_tsvector.py` tsvector GENERATED 列
- `app/services/bm25_incremental.py:57` `BM25IncrementalIndex` 增量接口
- `memory/w101-p1-reindex-startup-2026-08-01.md` 起步 6 项
- `memory/w101-p1-reindex-closure-2026-08-01.md` 收口汇报

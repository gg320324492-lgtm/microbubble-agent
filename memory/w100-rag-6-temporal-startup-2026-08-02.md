# W100-RAG-6 Temporal Retriever 派工起点 (2026-08-02)

## 派工前提实测

- base ref: `cd2571db56d09cf5cdaee06a8d9763627c9c82c5` (origin/main HEAD)
- 本地 HEAD: `cd2571db` (与 origin/main 同步, 无漂移)
- worktree 分支: `worktree-agent-w100-rag-6`
- worktree 路径: `E:\microbubble-agent\.claude\worktrees\w100-rag-6`
- alembic HEAD: `096_add_rag_multimodal_metrics` (本任务不动 schema)
- TimestampMixin 实测: `app/models/base.py:13` (created_at naive UTC)

## 件 4 六门控起点 (base = cd2571db)

| 门控 | 文件 | 起点 |
|------|------|------|
| A | knowledge_service.py | 0 def diff |
| B | hybrid_retriever.py | 0 def diff |
| C | rag_evaluator.py | 0 def diff |
| D | reranker_service.py | ≤ +1 (W100-RAG-4 ADD) |
| E | hybrid_weight_config.py | 0 def (含 W100-RAG-5 image ADD) |
| F (新) | multimodal_retriever.py | 0 def (W100-RAG-5 新文件) |

## 派工实施清单

- [ ] A. worktree 创建 ✅
- [ ] B. 新增 `app/services/temporal_retriever.py` (~120 行)
- [ ] C. 修改 `app/services/hybrid_weight_config.py` (件 4 门控 E 守恒)
- [ ] D. 修改 `app/services/hybrid_retriever.py` (件 4 门控 B 守恒)
- [ ] E. 修改 `app/rag/config.py` (module-level 开关模式)
- [ ] F. 新增测试套件 (单测 15 + e2e 22)
- [ ] G. 新增文档 (runbook + memory + grand closure)

## 类 20 起点

- 类 20.131 (新): 派工起点必 `git fetch origin` + `git merge-base --is-ancestor`
- 类 20.132 (新): temporal 衰减函数必 `exp(-age/2)` + 仅作最终 score 乘子
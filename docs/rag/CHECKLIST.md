# 派工 v11 检查单（RAG PR 派工速查版）

> 完整模板: [`docs/w72-prompt-paradigm-v11-2027-04.md`](../w72-prompt-paradigm-v11-2027-04.md)（v10 + 6 项新增）。本文件是主指挥派工前 / agent 收口前的一页速查。

## A. 主指挥派工前检查（brief 必填）

- [ ] 段 0: 目标一句话 + 边界（范围/不范围）+ 派工类型（A 调研 / B 实施 / C 清理 / D 收口）+ 锚点区间 `W8x +0 → +N`
- [ ] 段 0: **锚点起点实测**（`git log --grep` 确认未被占用; 被占用即顺延, 禁止让 agent 脑补）
- [ ] 段 1: alembic down_revision 显式（不产迁移也要写"本 PR 不产生迁移"）+ 命令形态 `python -m alembic`（v11 新增 1）
- [ ] 段 2: 新增/修改文件清单精确到行号 + 严禁修改清单（0 production code 例外与否显式声明）
- [ ] 段 3: e2e 目标数字化（N/N PASS）+ 重依赖 importorskip 策略
- [ ] 段 4: pytest 白名单完整 `--ignore` 清单 + baseline collected 数（v11 新增 2）
- [ ] 段 4: 5 件套守恒命令逐条列出
- [ ] 段 8: 起步 6 项含**依赖基线自检**（node_modules / sentence_transformers 等, v11 新增 5）
- [ ] 段 9: commit message 模板含 `[PRn W8x +N]` 锚点数字 + Co-Authored-By

## B. Agent 起步检查（开工前）

- [ ] Read plan 对应 § 全文（禁止只读派工摘要）
- [ ] worktree 建立: `git worktree add .claude/worktrees/<name> -b <branch> main`
- [ ] `python -m alembic heads` → 恰 1 head, 输出粘贴
- [ ] pytest baseline collect, collected 数与 brief 对比, 不符**据实上报差值**（v11 新增 3）
- [ ] `cd web && npm run build` 基线（worktree 无 node_modules 时主仓等价验证 + 上报）
- [ ] 起步 memory 落库 `memory/w8x-<topic>-start-<date>.md`

## C. Agent 收口检查（回报前）

- [ ] 5 件套回报表（v11 新增 6, 每格命令输出原文粘贴, 禁止"应该/大概/估计"）:

| 件 | 命令 | 判定 |
|----|------|------|
| 1 | `python -m alembic heads` | 1 head |
| 2 | `pytest <本 PR e2e> -q` | N/N PASS |
| 3 | `cd web && npm run build` | OK / pre-existing FAIL 据实标注 |
| 4 | `git diff main -- app/ \| wc -l` | 0（非例外 PR） |
| 5 | `git log --grep "W8x +" --oneline \| wc -l` | ≥ 目标 commit 数 |

- [ ] docs-only 门禁已断言化进 pytest（v11 新增 4, 章节数/关键词/链接/diff）
- [ ] 每 commit message 含锚点数字 + Co-Authored-By
- [ ] brief vs 实测偏差清单（0 项也要写"0 偏差"）
- [ ] memory 沉淀 + 主仓 CHANGELOG 条目
- [ ] 未 merge 未 push main（agent 不主动 merge, 主指挥拍板）

## D. 主指挥合并检查

- [ ] 按 PR 编号串行合并（禁止并行 alembic 派工）
- [ ] merge 后立即 `python -m alembic heads` verify 1 head
- [ ] 含前端 PR: `npm run build` + 6 点 curl 验证
- [ ] 收口后回填 plan Status 段（真 commit hash, 部分实施标 partial 不凑 completed）
- [ ] 派工前提错配实例沉淀（类 20 系列）+ CLAUDE.md 锚点段更新

## I. W89 PR3 据实上报锚点 (派生 §C §D 之外)

PR3 BM25 增量 + GIN/tsvector 实施沉淀（CLAUDE.md 严禁改铁律, 故单独章节）:

- [ ] PR3 锚点文档: `docs/rag/W89-PR3-ANCHOR.md` (CLAUDE.md 镜像, 9 节)
- [ ] alembic 089 串单链: `python -m alembic heads` → 恰 1 head `089_gin_trgm_tsvector`, down_revision=`088_add_knowledge_chunk`
- [ ] knowledge_service 钩子: `_run_analyze_and_embed` body 内 +2 try/except 块 (PR2 chunk hook 之后), 件 4a `^[+-]def` = 0
- [ ] bm25_service 钩子: 仅在文件底部新增 +3 module-level 包装函数, 派工 brief 显式允许
- [ ] hybrid_retriever: 0 diff, 派工 brief 锁
- [ ] 22/22 e2e PASS (`tests/rag/test_pr3_e2e.py`): text_splitter 1-5 / bm25_inc 6-10 / BM25L 11-15 / alembic 16-18 / 性能 19-22
- [ ] 性能门禁: 1000 条入库 ≤ 30s (实测 < 5s), 1000 docs 单 query ≤ 500ms (实测 < 100ms)
- [ ] 缺口消化: 缺口 3 (BM25 N 次重建) + 缺口 4 (PG 全文缺失)
- [ ] commit message 锚点范式: 全 commit 带 `[PR3 W89 +N]` 前缀 + Co-Authored-By: Claude Fable 5
- [ ] 类 20 实战 #25/26/27 据实上报 (knowledge_service 0 def + hybrid_retriever 0 diff + bm25_service +3 def 派工 brief 允许)
- [ ] 派工 v11 段 7 错误 19 类据实 (E01/E03/E05/E06/E07/E08/E11/E14/E15/E16/E18/E19/E21/E23/E24/E25 PASS)
- [ ] 派工 v11 段 10 新 6 项据实 (python -m alembic 形态 + pytest 白名单 + brief 据实 + docs-only 断言化 N/A + worktree 依赖基线 + 5 件套回报)

## J. W94 PR8 据实上报锚点 (派生 §I 之后)

PR8 知识图谱深度联动实施沉淀（CLAUDE.md 严禁改铁律，故单独章节）。
**PR8 是 10 PR 中最后 1 个 alembic PR** —— 091 之后 alembic 链正式收口。

- [ ] PR8 锚点文档: `docs/rag/W94-PR8-ANCHOR.md` (CLAUDE.md 镜像, 11 节)
- [ ] alembic 091 串单链: `python -m alembic heads` → 恰 1 head `091_add_kg_entity`, down_revision=`090_add_rag_eval_report`; 全景 `087 → 088 → 089 → 090 → 091` **10 PR 收口**
- [ ] alembic 091 HNSW: `CREATE INDEX CONCURRENTLY` + 089 二段式 `DO $$ 探测 pg_indexes` (E11 大表阻塞); `vector_cosine_ops` 与召回距离度量一致
- [ ] knowledge_service 钩子: `_run_analyze_and_embed` body 内 **Step 5b** (必排 Step 5 实体融合**之后**, 依赖其 SPO 产物, 倒置即静默失效), 件 4a `^[+-]def` = 0, **0 删除行** (+14 insertions 纯追加)
- [ ] hybrid_retriever 钩子: **仅文件底部**新增模块级 `retrieve_with_entity_link` + `count_kg_entities` + `ENTITY_LINK_DEFAULT_WEIGHT` (沿用 PR4 `retrieve_with_weights` 已批模式), `^[+-]def` = 0, 缩进 def = 0, **0 删除行** (+127 insertions)
- [ ] knowledge_graph_service 钩子: **仅文件底部**新增模块级 `_add_entity_links` / `_extract_flat_entities` / `_infer_entity_type` (**0 类方法改**, 不动 `build_relations_for` 类体)
- [ ] 已有 KG 资产 0 改: 5 服务 (`entity_service` 402 / `graph_retriever` 188 / `kg_query_service` 266 / `knowledge_graph_builder` 289 / `knowledge_graph_service` 500 = 1645 行) + 2 老表 (`knowledge_entities` SPO 三元组 / `entity_co_occurrence` 共现网络, 走 lifespan create_all 无 alembic)
- [ ] 22/22 e2e PASS (`tests/rag/test_pr8_e2e.py`): ORM 1-5 / 召回纯逻辑 6-10 / kg_embedding 11-15 / alembic 16-18 / 集成+性能+实体数+漂移 19-22
- [ ] 门禁 a 实体链 hit ≥ 25%: case 10 真算 (3/10=30% PASS, 反例 1/10=10% 判失败), E37
- [ ] 门禁 b 图谱召回 P95 ≤ 100ms: case 20 真计时 20 samples, E38
- [ ] 门禁 c 实体数 ≥ 5000: case 21 `count_entities()` 真调用 + `assert_awaited()`; **真库计数需生产 DB, 按 RUNBOOK §0.7.1 第 3 步跑真 SQL, 不脑补数字**, E39
- [ ] 门禁 d qa-bench ≥ 96%: **按推荐不跑** (沿用 PR1/PR5 处置); 第 5 路默认可关, 对既有 4 路 0 regression (case 22 验证 `enable_entity_link=False` 行为等价原 retrieve)
- [ ] 必复用 PR1 `truncate_for_embedding`: case 11 断言 + **禁止硬编码 `[:6000]`** (plan §1.1 缺口 1 根因)
- [ ] 实体漂移防护: **抽取侧与召回侧必调同一 `normalize_entity_name`** (case 22 断言); 否则 `" 气泡 "` 写入 `"气泡"` 但查 `" 气泡 "` 查不到
- [ ] 0 新增 LLM 调用: 复用 Step 5 三元组产物 + `_infer_entity_type` 确定性 predicate 关键词映射 (召回延迟预算)
- [ ] 缺口消化: 缺口 9 (图谱深度联动) —— 第 5 路 PG 内置, 补齐 `_graph_search` Neo4j 单点依赖短板
- [ ] commit message 锚点范式: 全 commit 带 `[PR8 W94 +N]` 前缀 + Co-Authored-By: Claude Fable 5
- [ ] **类 20 #33/#35 派工 brief 错配 3 处据实上报** (§12.3.4 拦截不擅自改): kg_entity ORM 已有 (互补非替代) + 实体抽取钩子已存在 (改走 Step 5b) + `_graph_search` 已存在 (改走第 5 路)
- [ ] **锚点合并据实**: 模板 21 commits (+0..+20), 实测 17 —— +8/+9/+10/+11 四项全落在 +7 的 22 case 内, **不为凑模板拆无意义 commit** (v11 新增 3: 验证型 0 增量不凑 +1)
- [ ] **e2e 真失败修根因不弱化断言**: case 15 (ST 未装 → `sys.modules` stub, 断言**加强**) + case 19 (gbk codec → `encoding="utf-8"`, 断言不变); **禁止**改阈值/删断言/加 xfail 凑 PASS
- [ ] **件 3 PWA build pre-existing FAIL 据实**: `RAGEvalPanel.vue:24` `"Play"` 未导出, PR5 `cb5c98498` 引入非 PR8 (frontend=否, web/ 0 dirty); v11 新增 5 → 不算本 PR FAIL 也**不顺手修**; 建议主拍 hotfix `Play` → `VideoPlay`
- [ ] **`scripts/check_typing_imports.sh` 超时 fallback** (§F 精神): 2min 内未完成 → 改 5 模块 `importlib.import_module` 实测全 OK (等价验证铁律 2)
- [ ] 派工 v11 段 7 错误 19 类据实 (E01/E03/E05/E06/E07/E08/E11/E19/E21/E37/E38/E39 PASS)
- [ ] 派工 v11 段 10 新 6 项据实 (`python -m alembic` 形态 + pytest 白名单 3208 collected 0 偏差 + brief 据实 3 处 + docs 断言化 + worktree 依赖基线 (node_modules 缺 → 主仓等价) + 5 件套回报表)

## E. 5 件套守恒命令（速查）

详见 §C 表。

## F. verify 脚本未合 main fallback（DERIVE-12）

PR2/3 verify 脚本 (`scripts/rag/verify_alembic_chain.sh` + `verify_dispatch_claim.sh`) 若未合 main:
- 主仓等价验证 + 据实标注 (`python -m alembic heads` + `git log --grep` + `wc -l` 三条手工命令替代)
- 收口回报必标 "未合 main, 主仓等价验证 PASS"

## G. 类 20 实战 #21-#26 整合 (DERIVE-13)

类 20 沉淀统一在 `memory/w88-rag-pr2-full-2026-07-30.md` (PR2 据实) + `memory/w89-rag-pr3-full-2026-07-30.md` (PR3 据实, 含 #25/26/27)

## H. v11 段 13 仓库实情真查 (DERIVE-18)

派工前必查:
- `python -c "import <重依赖>"` (sentence_transformers / jieba / rank_bm25 等)
- brief 列出的接口契约文件 / 仓库实情是否一致
- 不一致时**据实上报**, 不擅自扩也不擅自缩

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

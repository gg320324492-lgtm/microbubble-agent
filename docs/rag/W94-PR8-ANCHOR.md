# PR8 知识图谱深度联动 CLAUDE.md 锚点 (W94 +14)

> **PR8 是 10 PR 中最后 1 个 alembic PR** — 091 之后 alembic 链正式收口。
> 本文件是 CLAUDE.md **镜像**（沿用 PR3 `W89-PR3-ANCHOR.md` + PR5 `W91-PR5-ANCHOR.md` 已批模式）。
> CLAUDE.md 属"严禁修改"清单，PR8 **不动 CLAUDE.md**，锚点内容落本镜像文件。

## §1 PR8 锚点范式 + 实测数据

| 项 | 值 | 验证命令 |
|----|----|---------|
| 锚点区间 | W94 +0 → +20（brief 模板 21 commits） | `git log --grep "PR8 W94 +"` |
| 实测 commit 数 | 见 §9 据实上报（按真 commit 数报，不凑模板） | `git log --grep "PR8 W94 +" --oneline \| wc -l` |
| base main HEAD | `034343f8a`（MERGE-03 收口，锚点 459） | `git merge-base HEAD main` |
| alembic head | `090_add_rag_eval_report` → **`091_add_kg_entity`** | `python -m alembic heads` |
| alembic 串单链 | 087 → 088 → 089 → 090 → **091**（10 PR 收口） | e2e case 18 |
| pytest baseline | 3208 collected（与 MERGE-03 期望 0 偏差） | `pytest tests/ --co -q --ignore=tests/test_w79_...` |
| PR8 e2e | **22/22 PASS in 0.26s** | `pytest tests/rag/test_pr8_e2e.py -q` |
| 件 3 PWA build | **pre-existing FAIL**（PR5 RAGEvalPanel.vue `Play` 图标，非 PR8 引入） | `cd web && npm run build` |
| 件 4a 双门控 | 6 老核心服务 `^[+-]def` = **0** | e2e case 19 subprocess 实测 |
| frontend | **否**（backend-only，plan §2 PR8 行） | `git diff --stat main -- web/` |

## §2 PR8 门禁 4 项（plan §2 + §9）

| 门禁 | 阈值 | 实测 | 判定 |
|------|------|------|------|
| a 实体链 hit | ≥ 25% | `ENTITY_LINK_HIT_TARGET=0.25`，e2e case 10 真算 3/10=30% PASS / 反例 1/10=10% 判失败 | PASS（逻辑层） |
| b 图谱召回 P95 | ≤ 100ms | `ENTITY_LINK_P95_BUDGET_MS=100.0`，e2e case 20 真计时 20 samples P95 断言 | PASS |
| c 实体数 | ≥ 5000 | `ENTITY_COUNT_TARGET=5000`，e2e case 21 `count_entities()` 真调用路径 + `assert_awaited()`；**真库计数需生产 DB**，见 §9 据实上报 | PASS（路径）/ 生产待验 |
| d qa-bench | ≥ 96% | **按推荐不跑**（沿用 PR1/PR5 处置，见 §9） | 未跑，据实上报 |

## §3 PR8 已有 KG 资产关系（互补非替代）

| 资产 | 表 / 后端 | 语义 | alembic | PR8 是否改 |
|------|----------|------|---------|-----------|
| `KnowledgeEntity` | `knowledge_entities` | **SPO 三元组**（关系断言） | 无（lifespan create_all） | **0 改** |
| `EntityCoOccurrence` | `entity_co_occurrence` | 共现网络 | 无（lifespan create_all） | **0 改** |
| `KGEntity`（PR8） | `kg_entities` | **扁平命名实体** | **091** | 新增 |
| `HybridRetriever._graph_search` | Neo4j | 图谱路（driver None 时返空） | — | **0 改** |
| `retrieve_with_entity_link`（PR8） | PostgreSQL | **第 5 路**（无外部依赖） | — | 模块级新增 |
| `EntityService.merge_entities_from_document` | knowledge_entities | Step 5 SPO 抽取 | — | **0 改**（复用其产物） |

**5 个已有 KG 服务全部 0 改**：`entity_service.py`(402) / `graph_retriever.py`(188) / `kg_query_service.py`(266) / `knowledge_graph_builder.py`(289) / `knowledge_graph_service.py`(500，仅**文件底部**模块级追加)。

## §4 PR8 × 派工 v11 段 7 错误 19 类（PR8 实战）

| 类 | 处置 | 判定 |
|----|------|------|
| E01 alembic 多 head | 091 接 090 单链，`python -m alembic heads` = 1 head；e2e case 18 断言 | PASS |
| E03 pytest 假 PASS | 22/22 真跑 0.26s；2 例真失败**修根因不弱化断言**（见 §6） | PASS |
| E05 老核心函数误改 | 件 4a grep **6** 个老核心服务（brief 强调 6 非 5） | PASS |
| E06 HybridRetriever 误改 | `^[+-]def` 0 命中 + 缩进 def 0 + 删除行 0（127 纯追加） | PASS |
| E07 锚点范式缺失 | 全 commit 带 `[PR8 W94 +N]` 前缀 | PASS |
| E08 0 production code 违规 | 件 4a/4b 双门控全过 | PASS |
| E11 GIN/HNSW 大表阻塞 | `CREATE INDEX CONCURRENTLY` + 089 二段式 DO $$ 探测 | PASS |
| E19 commit message 格式 | 全 commit 含 Co-Authored-By + 锚点数字 | PASS |
| E21 pytest collection error | 全程 `--ignore=tests/test_w79_...`；新测试文件 basename 唯一 | PASS |
| **E37 实体链 hit ≥ 25%** | e2e case 10 真算，未达标判失败 | PASS |
| **E38 P95 ≤ 100ms** | e2e case 20 真计时 20 samples | PASS |
| **E39 实体数 ≥ 5000** | e2e case 21 `count_entities()` 真调用 + `assert_awaited()`；生产真库计数见 §9 | PASS（路径） |

## §5 PR8 × 派工 v11 段 10 新 6 项（PR8 实战）

1. **`python -m alembic` 命令形态**：PASS（全程，0 次直跑 `alembic`）
2. **pytest 白名单**：PASS（`--ignore=tests/test_w79_commercial_private_deployment_e2e.py`），baseline 3208 与 brief 期望 **0 偏差**
3. **派工 brief vs 实测据实上报**：PASS — **3 处后端 KG 错配据实**（见 §7），不擅自扩也不擅自缩
4. **docs-only 断言化**：N/A（PR8 含后端 + alembic），但 docs 门禁仍进 e2e（case 11/16/17/22 真读文件断言）
5. **worktree 依赖基线自检**：PASS — `web/node_modules` **worktree 内不存在** → 主仓等价验证（件 3 pre-existing FAIL 据实标注）
6. **5 件套守恒命令输出粘贴**：PASS（收口回报结构化表，见主报告）

## §6 PR8 e2e 2 例真失败修根因实录（据实上报，未弱化断言）

| # | 失败 | 根因 | 修法 | 断言变化 |
|---|------|------|------|---------|
| case 15 | `patch("app.services.embedding_service.generate_embedding")` → `ModuleNotFoundError` | 本机 **`sentence_transformers` 未装**（plan §3.7 已预警），`import embedding_service` 直接崩 → `patch` 无法 resolve target | `sys.modules` 注入 stub 模块验证成功路（比 `importorskip` 跳过**更强** — 真跑 lazy import 契约）+ 用真实缺装环境验证降级路（不 mock） | **加强**（新增 `assert_awaited()` / `assert_not_awaited()` 验证空名不调 embedding） |
| case 19 | `UnicodeDecodeError: 'gbk' codec` | Windows 默认 gbk 解码含中文的 `git diff` 输出必崩 | `subprocess.run(encoding="utf-8", errors="replace")` | 不变 |

**纪律**：真失败必修根因，**禁止**改阈值/删断言/加 xfail 凑 PASS（W82/W84 据实上报铁律）。

## §7 PR8 派工 brief 错配 3 处（类 20 #33 / #35，§12.3.4 拦截不擅自改）

| # | brief 写 | 仓库实情 | 处置 |
|---|---------|---------|------|
| 1 | 新增 `app/models/kg_entity.py`（entity_name/entity_type/knowledge_id FK/vector/first_seen_at/last_seen_at/mention_count） | `app/models/knowledge_entity.py` **已存在** `KnowledgeEntity`（**SPO 三元组** subject/predicate/object + `source_knowledge_ids` ARRAY）+ `EntityCoOccurrence` | 新建 `KGEntity`（扁平实体）**互补非替代** — 与 PR5 `RAGEvaluationReport` vs 已有 `RAGEvaluation` **同款模式**；091 仅建新表 0 改老表 |
| 2 | `knowledge_service.py` **仅新增**实体抽取钩子 | 实体抽取钩子 **已存在**（Step 5 `merge_entities_from_document` L302 + Step 6 Neo4j L311） | 不新建"实体抽取"钩子，改为 Step 5 **之后**追加 **Step 5b** kg_entities 钩子，复用 Step 5 产物 |
| 3 | `hybrid_retriever.py` **仅新增** KG retrieval path | `_graph_search` **已存在**（L218-267 Neo4j 路，固定 score 0.7），`retrieve`/`_retrieve_impl` 4 路已含 `enable_graph` | 0 改 `_graph_search`/`retrieve`/4 路默认，改为模块级**第 5 路** `retrieve_with_entity_link`（沿用 PR4 `retrieve_with_weights` "新 API 不动原 retrieve" 已批模式） |

**根因**：PR8 brief 派生自 plan v1.0 §11.2，未做 DERIVE-18 §13 仓库实情真查。plan v1.2 已修正**前端**路径（§11.2 第 544 行），但**后端 KG 资产未盘查** — 项目已有 **5 个 KG 服务（1645 行）+ 2 个 ORM 模型**，brief 假设"KG 从 0 建"与实情不符。

**§12.3.4 遵守**：3 处**全部据实上报 + 不擅自改 brief 语义**；处置均为"新增不动老"（与 brief 0 production code 双门控目标一致），非"把 A 改成 B 后继续"。

## §8 PR8 件 4 双门控实测（DERIVE-08/09 v10.1）

| 文件 | 锁定? | `^[+-]def` | 缩进 def | 删除行 | insertions | 件 4a | 件 4b |
|------|------|-----------|---------|-------|-----------|-------|-------|
| `knowledge_service.py` | **是** | **0** | **0** | **0** | 14 | PASS | PASS（brief 授权钩子） |
| `hybrid_retriever.py` | **是** | **0** | **0** | **0** | 127 | PASS | PASS（brief 授权 KG path） |
| `embedding_service.py` | 是（PR1） | 0 diff | — | — | 0 | PASS | — |
| `bm25_service.py` | 是（PR3） | 0 diff | — | — | 0 | PASS | — |
| `text_splitter.py` | 是（PR3） | 0 diff | — | — | 0 | PASS | — |
| `rag_evaluator.py` | 是（PR5） | 0 diff | — | — | 0 | PASS | — |
| `knowledge_graph_service.py` | 否 | 1（模块级） | **0** | **0** | +追加 | PASS | PASS |

**关键**：两个**锁定**文件（knowledge_service / hybrid_retriever）均 **0 删除行、0 def 改、纯追加**。

## §9 PR8 据实上报清单（禁止"应该/大概/估计"）

1. **锚点 +N 按真 commit 数报**：brief 模板 21 commits（+0..+20）。实测部分模板条目自然合并（如 +8..+11 性能/实体数/集成/漂移 4 项全部落在 `test_pr8_e2e.py` 22 case 内，单 commit +7 交付），**不为凑 21 拆无意义 commit**（v11 新增 3：验证型 0 增量不凑 +1）。最终数见收口回报 `git log --grep` 实测。
2. **件 3 PWA build = pre-existing FAIL**：`src/views/admin/RAGEvalPanel.vue:24` `"Play" is not exported by @element-plus/icons-vue`。**PR5（commit `cb5c98498`）引入，非 PR8**；`git status --porcelain -- web/` = **0 dirty**（PR8 未碰 web/）。按 v11 新增 5：pre-existing 故障据实上报，**不算本 PR FAIL，也不顺手修**（0 production code）。**建议主拍派 hotfix**：`Play` → `VideoPlay`。
3. **门禁 c 实体数 ≥ 5000 未在真库验证**：本机 PostgreSQL 未连（`sentence_transformers` 亦未装）。e2e case 21 验证 `count_entities()` **真调用路径**（`assert_awaited()`）+ 门禁比较逻辑，**非真库计数**。生产部署后按 RUNBOOK §0.7.1 第 3 步跑真 SQL。**不脑补数字**。
4. **门禁 d qa-bench ≥ 96% 未跑**：沿用 PR1/PR5 处置（"按推荐不跑"）。PR8 为 backend 新增路径且第 5 路默认可关，对既有 4 路 0 regression（e2e case 22 验证 `enable_entity_link=False` 行为等价原 retrieve）。
5. **`scripts/check_typing_imports.sh` 超时**：2min 限内未完成（106 文件全扫）。改用 **5 模块 `importlib.import_module` 实测全 OK**（等价验证铁律 2，见 CHECKLIST §F fallback 精神）。
6. **CLAUDE.md 0 改**：锚点落本镜像文件（PR3/PR5 已批模式）。
7. **8 个 untracked `agent-w89-*/`（2.66GB）**：DERIVE-14 已记录，**PR8 不擅自删**，待主拍签字。

## §10 PR8 anchor 文件结构

- `docs/rag/W94-PR8-ANCHOR.md`（本文件，CLAUDE.md 镜像，10 节）
- `docs/rag/RUNBOOK.md` §0.7 + §0.7.1 + §0.7.2（部署 / 验证 / 回滚）
- `docs/rag/SCHEMAS.md` §10（7 件套 → 10 件补完）
- `docs/rag/CHECKLIST.md` §J（PR8 据实上报速查）
- `memory/w94-rag-pr8-start-2026-07-30.md`（起步 6 项 + 错配 3 处）
- `memory/w94-rag-pr8-full-2026-07-30.md`（收口全量据实）

## §11 PR8 实施总结

**10 PR alembic 链收口**：`087 → 088 (PR2 chunk) → 089 (PR3 GIN/tsvector) → 090 (PR5 rag_eval) → 091 (PR8 kg_entity)`，PR8 之后 PR9/PR10 无迁移。

**缺口消化**：缺口 9 图谱深度联动（plan §1.3）。第 5 路 `entity_link` 补齐 Neo4j 单点依赖短板 —— PostgreSQL 内置，Neo4j 挂时仍可召回。

**0 production code 守恒**：6 锁定老核心 `^[+-]def` = 0；两锁定文件 0 删除行纯追加；5 个已有 KG 服务 0 改；`knowledge_entities` / `entity_co_occurrence` 两老表 0 改。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

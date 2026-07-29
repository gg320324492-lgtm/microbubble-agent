# RAG 7 件套 Schema 完整文档

> 7 件套 = RAG 大改造系列跨 PR 的 7 个核心 schema/policy 模块。每件含: 归属 PR / 文件路径 / 接口签名 / 字段 schema / 约束 / 测试锚点。
> 纪律: 所有 dataclass/Pydantic 必须完整 type hint (`from typing import ...`), 新加字段 keyword-only + Optional 默认 None (派工 v10 §2)。

---

## 1. truncation_policy（PR1）

- **路径**: `app/services/embedding_truncation_policy.py`
- **定位**: 单一截断策略, 消灭 3 档截断不一致（6000 / 无 / 500）。纯逻辑层, 只依赖标准库, 可被单测直接 import。

```python
MAX_EMBED_INPUT_CHARS: int = 6000            # 唯一截断常量, 全库统一

def truncate_for_embedding(text: str) -> str:
    """入库/重算/查询 embedding 前的唯一截断入口。<= 6000 原样返回, > 6000 截到 6000。"""

EMBEDDING_HAS_QUERY_PROMPT: bool             # 按 MODEL_NAME 前缀推断 (Qwen/BGE/bge → True)
```

- **约束**: `embedding_service.py` 顶部 + `embedding_recalc.py:145` + PR2 chunking 预处理必须统一走此入口; snippet 500 字符截断是展示截断非向量截断（`knowledge_service.py:842/878` 仅注释 WHY）。
- **测试锚点**: 边界 0 / 5999 / 6000 / 6001 / 10000 字符（PR1 e2e case 1-5）。

## 2. query_policy（PR1）

- **路径**: `app/services/embedding_query_policy.py`
- **定位**: query prefix 路径白名单, 让 `QUERY_PROMPT_ZH`（`embedding_prompts.py:16`）真正生效。

```python
def should_use_query_prefix(caller_path: str) -> bool:
    """路径白名单: kb_qa / hybrid / semantic_search → True; 其余 (auto_research 等) → False。"""
```

- **前置依赖**: `embedding_service.py:142/151/163` `has_query_prompt` 透传修复（不修 = 零效果, 详见 plan §3.0）。
- **约束**: query 侧精确调用点仅 2 行（`knowledge_service.py:812` + `memory_service.py:195` 加 `for_query=True`）; 紧急短路 `EMBEDDING_POLICY_DISABLED=1`。
- **门禁**: `for_query=True` 检索路径占比 ≥ 80%（日志 grep `embedding_for_query=true`）。

## 3. consistency_check（PR1）

- **路径**: `app/services/embedding_consistency_check.py`
- **定位**: CI/开发期自检, 扫所有 embedding caller 必须过 policy, 防止绕过截断/prefix 入口的野调用。

```python
def run() -> ConsistencyReport:
    """扫 8 个 caller path, 逐一校验: 走 truncate_for_embedding + 走 should_use_query_prefix。
    返回 report: {caller_path: str, passed: bool, violation: Optional[str]}[]"""
```

- **约束**: 全过才 PASS（PR1 e2e case 12）; 集成到 CI 与 `scripts/check_production_code_diff.sh` 同级。
- **门禁**: recalc 后全库向量 L2 漂移 ≤ 1e-4。

## 4. hybrid_weight（PR4）

- **路径**: `app/services/hybrid_weight_config.py`
- **定位**: HybridRetriever 四路（vector / bm25 / tsvector / graph）权重可配化（yaml + DB 双源）, 不改 `hybrid_retriever.py:25-104` 原函数签名。

```python
class HybridWeightConfig(BaseModel):
    vector_weight: float = 0.4
    bm25_weight: float = 0.3
    tsvector_weight: float = 0.2
    graph_weight: float = 0.1
    rrf_k: int = 60                          # RRF 归一化常数
    rerank_enabled: bool = True              # CrossEncoder rerank 开关
    rerank_keep_ratio: float = 0.7           # rerank 后保留比例 ≥ 70%

def load_weights(db: AsyncSession) -> HybridWeightConfig:
    """优先 DB 覆盖, 缺省回落 yaml, 再缺省回落上述默认值。"""
```

- **约束**: 权重和不强制 = 1（RRF 归一化后合并）; reranker 异常自动回退向量 + BM25 双路（风险 R3）; A/B 灰度走权重快照。

## 5. synonym_dict（PR4）

- **路径**: `app/services/synonym_dict.py`
- **定位**: 领域同义词典（微纳米气泡领域 ≥ 200 条）, query 扩展与 BM25/tsvector 召回增强。

```python
class SynonymEntry(BaseModel):
    term: str                                # 主词, 如 "微纳米气泡"
    synonyms: List[str]                      # 同义词组, 如 ["MNB", "micro-nano bubble", "超细气泡"]
    domain: Optional[str] = None             # 子领域标签
    enabled: bool = True

def expand_query(query: str) -> List[str]:
    """返回 query + 同义扩展项（去重, 上限防爆炸）。"""
```

- **约束**: 词典条目 ≥ 200（PR4 门禁）; 扩展仅作用于稀疏路（BM25/tsvector）, 不污染向量路; 词典变更走 review 不走运行时写。

## 6. recall_observability（PR7）

- **路径**: `app/services/recall_observability.py`
- **定位**: 全链路召回可观测, 从 `search_log.py:50-101` 埋点样板扩展（禁止新写埋点框架）。

```python
class RecallTraceRecord(BaseModel):
    trace_id: str
    query: str
    caller_path: str
    route_latency_ms: Dict[str, float]       # {"vector": .., "bm25": .., "tsvector": .., "graph": ..} 按路 100% 覆盖
    total_latency_ms: float
    result_count: int
    top_score: Optional[float] = None
    for_query: bool = False
    has_query_prompt: bool = False
    truncated: bool = False
    error: Optional[str] = None
```

- **约束**: 结构化日志字段 ≥ 12; grafana ≥ 6 面板消费; P99 ≤ 200ms 门禁; 埋点失败 best-effort 不阻塞召回（复用 chat 持久化铁律 5）。

## 7. auto_research_v2（PR9）

- **路径**: `app/services/auto_research_v2.py`（配套 `app/services/dedup_cross_doc.py`）
- **定位**: 自主研究引擎升级 — 联网结果入 KB 前质量门 + 跨文档去重 + 同义改写检索。

```python
class ResearchCandidate(BaseModel):
    source_url: str
    title: str
    extracted_content: str
    judge_score: float                        # LLM-as-judge 质量分, 入 KB 门槛
    dedup_hash: Optional[str] = None          # 跨文档去重指纹
    accepted: bool = False
    reject_reason: Optional[str] = None

def dedup_cross_doc(candidates: List[ResearchCandidate]) -> List[ResearchCandidate]:
    """embedding 余弦 + 指纹双通道去重, 去重率 ≥ 95%。"""
```

- **约束**: 自动入 KB ≥ 70% + 人工抽检（风险 R10: 联网误入必须 LLM-as-judge 前置）; 质量门必确定性, LLM 最多解释歧义不得越过门禁（复用声纹 B 方案铁律 2）; 入库必走 `_run_analyze_and_embed` 样板禁止另起炉灶。

---

## 跨件约束总表

| 约束 | 适用件 | 来源 |
|------|-------|------|
| 纯逻辑层可单测 import（无 ST 重依赖） | 1/2/3 | plan §3.7 |
| 不改原函数签名, 只扩展 | 4/6 | plan §6 必复用资产 |
| 确定性门禁, LLM 不越权 | 7 | CLAUDE.md 声纹铁律 2 |
| keyword-only + Optional 默认 None | 全部 | 派工 v10 §2 |
| 埋点/持久化 best-effort | 6 | CLAUDE.md chat 铁律 5 |
| 常量固化（截断 6000 / QUERY_PROMPT_ZH） | 1/2 | `embedding_prompts.py` 铁律 |

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

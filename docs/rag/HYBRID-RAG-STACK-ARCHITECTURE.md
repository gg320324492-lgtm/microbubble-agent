# Hybrid RAG Stack — 4 层架构图 + 回退路径图 (2026-07-31)

> **配套**: [HYBRID-RAG-STACK.md](HYBRID-RAG-STACK.md) (全览) / [W98-HYBRID-RAG-STACK-ANCHOR.md](W98-HYBRID-RAG-STACK-ANCHOR.md) (CLAUDE.md 镜像)

## 1. 4 层架构总图 (文字版)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  调用方: knowledge_qa_service / chunking_service / 前端 RAG 端点             │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 3 回退门控  (app/rag/gate.py — framework_gate 装饰器, 自研)          │
│    ┌ 开关关闭 ──→ 直接走回退路径                                            │
│    ┌ ImportError ──→ logger.warning + 回退 (框架依赖未安装)                  │
│    ┌ 运行时异常 ──→ logger.error + 回退 (框架调用失败降级)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 2 框架层  (app/rag/ 8 文件, LangChain + LlamaIndex + LangFuse)      │
│    lc_tracing / query_translator / multi_hop_engine / agent_retriever       │
│    dense_sparse_routing / semantic_chunker / multimodal_parser / gate       │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 1 手写层  (app/services/, 7 服务, 0 修改)                            │
│    knowledge_qa_service / hybrid_retriever / bm25_service / embedding_service│
│    chunking_service / file_parser_service / knowledge_graph_service         │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 4 基础设施  (PostgreSQL + pgvector HNSW + SQLAlchemy async +         │
│    langfuse 自托管 docker-compose 端口 3000, trace 落自有 PostgreSQL)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. 8 能力调用链 + 回退路径

### 能力 1: LangFuse Tracing (`app/rag/lc_tracing.py`)

```
调用链: get_langfuse_handler(name) → langfuse.CallbackHandler
        → trace_retrieval(query, handler) async with span → hybrid_retriever.retrieve()
开关:   LC_TRACING_ENABLED (默认 1, 且需 LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY 非空)
        LANGFUSE_TRACE_ENABLED = LC_TRACING_ENABLED and (公钥 and 私钥)
回退:   handler 返回 None → 走 recall_observability 既有日志; ImportError / 初始化失败 → logger 记录禁用
```

### 能力 2: Query 翻译 (`app/rag/query_translator.py`)

```
调用链: QueryTranslator.translate(query) → LangChain 三件套:
        ① MultiQueryRetriever (1 问 → 3-5 路同义改写, 中文微纳米气泡领域 prompt)
        ② HyDE (LLM 生成假设文档 → 嵌入假设文档检索, recall +15-25%)
        ③ QueryDecomposition (复杂问题 → 2-4 子问题)
        → 并行调 hybrid_retriever.retrieve → 合并去重 (复用 _merge_results 模式)
开关:   QUERY_TRANSLATION_ENABLED (默认 1)
回退:   translate 失败/门控关闭返回 None → 原 query 直传 (结果 = 单路原 query 检索)
```

### 能力 3: Multi-hop (`app/rag/multi_hop_engine.py`)

```
调用链: MultiHopEngine.retrieve(question) → LlamaIndex SubQuestionQueryEngine
        → 自动分解复杂问题为子问题 → 逐跳检索 (只读复用 knowledge.embedding HNSW, 不建新表)
        → 逐层聚合子结果合成最终答案
开关:   MULTI_HOP_ENABLED (默认 1)
回退:   framework_gate 异常 → _fallback_single_hop → knowledge_qa_service.answer_question() 单轮检索
```

### 能力 4: Agent Router (`app/rag/agent_retriever.py`)

```
调用链: AgentRetriever.retrieve(query) → LangChain AgentExecutor + 4 个 Tool:
        vector_search (概念/方法/术语) / bm25_search (精确关键词/代码/编号)
        graph_search (实体关系/人物/项目依赖) / web_search (缺知识兜底, 搜狗微信+必应)
        → LLM (ChatAnthropic, AGENT_INTENT_MODEL 优先, 默认 claude-haiku-4-5) 动态选检索器
开关:   AGENT_ROUTER_ENABLED (默认 1) / AGENT_ROUTER_MAX_CALLS_PER_REQUEST (默认 1)
回退:   ① 开关关闭 → gate 返回 None (不擅自降级, fallback_fn=None)
        ② ImportError → gate 返回 None
        ③ LLM 路由解析失败 → vector 单路 (最大召回面)
        ④ 任一工具执行异常 → hybrid 4 路并发 (retrieve 内部 try/except)
```

### 能力 5: Dense/Sparse 一层切换 (`app/rag/dense_sparse_routing.py`)

```
调用链: DenseSparseRetriever.retrieve(query) → env RAG_RETRIEVAL_MODE 切换:
        dense-only → LlamaIndex VectorStoreIndex (pgvector HNSW 复用 knowledge.embedding)
        sparse-only → BM25Retriever (复用 bm25_service)
        hybrid     → 两者融合 (默认)
        设计约束: PGVectorStore perform_setup=False 只读复用 — 不建表/不建索引/不 UPSERT, 0 alembic
开关:   DENSE_SPARSE_ROUTING_ENABLED (默认 1)
回退:   llama_index 未装 / 老表列结构不匹配 / embedding 模型不可用 → hybrid_retriever.retrieve()
        开关关闭 → 返回 None (fallback_fn=None)
```

### 能力 6: Semantic Chunker (`app/rag/semantic_chunker.py`)

```
调用链: semantic_chunk(text, min_chunk_size=200, breakpoint_percentile=95)
        → LangChain SemanticChunker (embedding 余弦 gap 检测语义边界)
        → 中文句读显式注入 SENTENCE_SPLIT_REGEX = (?<=[。！？!?；;])\s* (LangChain 默认只覆盖英文标点)
        → semantic_score = chunk 内连续句子 embedding 余弦相似度均值 (单句 chunk = 1.0, 失败 = 0.0)
开关:   SEMANTIC_CHUNKER_ENABLED (默认 1)
回退:   ImportError / 运行时异常 → _fallback_rule_chunks → chunking_service 3 规则策略 (并列不替换)
```

### 能力 7: 跨模态解析 (`app/rag/multimodal_parser.py`)

```
调用链: parse_document_enhanced(file_path, file_type) → LlamaIndex Readers 三选一:
        PDFReader (layout 分析 + 表格结构化 + 图表描述) / ImageReader (图片描述)
        UnstructuredReader (PDF/DOCX/PPTX 混合) → {"text", "tables", "images", "metadata"}
        Fig./Figure N + Table/表格 N 引用模式与 file_parser_service 锚点搜索对齐
开关:   MULTIMODAL_PARSER_ENABLED (默认 1)
回退:   ImportError / 运行时异常 → _fallback_parse → file_parser_service (fitz 抽文字) + OCR 通道
```

### 能力 8: 回退门控 (`app/rag/gate.py`, 自研)

```
framework_gate(feature_flag, fallback_fn=None) 装饰器:
  wrapper(*args, **kwargs):
    if not feature_flag:          → fallback_fn 存在则 await 之, 否则 None
    try: return await func(...)   → 开关开启走框架路径
    except ImportError:           → logger.warning (依赖未安装) → 回退
    except Exception:             → logger.error (exc_info=True) → 回退
    fallback_fn 存在则 await 之, 否则 None
设计语义: fallback_fn=None 时不擅自降级 — 调用方自行决定 (与 RAG-FW-01 gate 语义一致)
```

## 3. 回退路径总图

```
                    ┌────────── 开关关闭 / ImportError / 运行时异常 ──────────┐
                    │                                                       │
  8 能力调用 ──→ framework_gate ──→ 框架实现 (Layer 2) ──失败──→ 手写回退 (Layer 1)
                    │                                                       │
                    └── fallback_fn=None 语义: 返回 None, 调用方自行决定 ────┘

  能力          框架实现                 手写回退目标
  1 Tracing     LangFuse handler         recall_observability 日志
  2 Query 翻译  MultiQuery/HyDE/Decomp   原 query 直传 hybrid_retriever
  3 Multi-hop   SubQuestionQueryEngine   knowledge_qa_service 单轮
  4 AgentRouter AgentExecutor 4 tools    vector 单路 → hybrid 4 路
  5 Dense/Sparse VectorStoreIndex+BM25   hybrid_retriever 4 路
  6 Chunker     SemanticChunker          chunking_service 3 规则
  7 Multimodal  PDF/Image/Unstructured   file_parser_service + OCR
```

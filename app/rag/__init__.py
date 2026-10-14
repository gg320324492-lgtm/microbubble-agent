"""app/rag — Hybrid RAG Stack 框架能力层

在现有手写 RAG 栈 (app/services/knowledge_qa_service.py 等 Layer 1)
之上新增一组框架能力层, 全部 On by default (激进模式)。

⚠️ 本层**不依赖 LangChain** —— langchain 四包已于 2026-10-12 整体移除
(见 requirements.txt「LangChain 家族」段), `app/` 下零 import。
**LlamaIndex 仍在用**: dense_sparse_routing.py (VectorStoreIndex / BM25Retriever)
与 multimodal_parser.py (PDFReader 等) 以函数内延迟 import 方式引用。
早期 docstring 里的「LangChain + LlamaIndex 框架能力层」只有后一半还成立。

模块:
- config.py — 8 项框架能力开关 + 框架配置 (LangFuse / PGVector / Agent Router)
- gate.py   — 框架门控回退装饰器 (开关关闭或异常时自动回退到 Layer 1 手写实现)
"""

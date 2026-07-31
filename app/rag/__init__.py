"""app/rag — Hybrid RAG Stack 框架能力层

在现有手写 RAG 栈 (app/services/knowledge_qa_service.py 等 Layer 1)
之上新增 LangChain + LlamaIndex 框架能力层, 全部 On by default (激进模式)。

模块:
- config.py — 8 项框架能力开关 + 框架配置 (LangFuse / PGVector / Agent Router)
- gate.py   — 框架门控回退装饰器 (开关关闭或异常时自动回退到 Layer 1 手写实现)
"""

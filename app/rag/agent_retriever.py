"""app/rag/agent_retriever.py — Agent 自主选择检索器

LangChain AgentExecutor + Tool:
- 每个检索器暴露为 tool (vector_search / bm25_search / graph_search / web_search)
- LLM 根据 query 类型动态决定调哪个
- 数据类 query → vector/BM25 优先
- 关系类 query → graph 优先
- 缺知识 → web_search 兜底

与 agentic_loop.py Phase 0 共存:
- Phase 0 决定"搜不搜" (固定 tool 列表)
- Agent Router 决定"怎么搜" (检索器级路由)

分层回退 (全链路 framework_gate 包裹):
1. 开关关闭 (AGENT_ROUTER_ENABLED=False) → gate 返回 None (框架路径不启用, 调用方自行决定,
   与 RAG-FW-01 gate 语义一致: fallback_fn=None 时不擅自降级)
2. LangChain 依赖缺失 (ImportError) → gate 返回 None (同上)
3. LLM 路由解析失败 → vector 单路 (最大召回面, 不浪费往返)
4. 任一工具执行异常 → hybrid 4 路并发 (retrieve 内部 try/except)
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.rag.config import AGENT_ROUTER_ENABLED, AGENT_ROUTER_MAX_CALLS_PER_REQUEST
from app.rag.gate import framework_gate

logger = logging.getLogger("microbubble.rag.agent_retriever")

# 检索器 tool 描述 — 给 LangChain AgentExecutor 的 LLM 做工具选择
ROUTER_PROMPT = """你是检索路由助手。根据用户问题类型，选择最合适的检索方式:
- vector: 概念/方法/术语类问题 (默认)
- bm25: 精确关键词/代码/编号类问题
- graph: 实体关系/人物/项目依赖类问题
- web: 知识库中没有的新知识/最新信息

用户问题: {query}

只输出一个词: vector / bm25 / graph / web"""

_VALID_ROUTES = ("vector", "bm25", "graph", "web")


class AgentRetriever:
    """LangChain AgentExecutor 包装 — 动态检索器路由

    Args:
        db: AsyncSession (与 HybridRetriever 同源)
        llm: 可选注入 LLMClient (测试/容器场景); None 时用 app.core.llm.LLMClient()
        hybrid_retriever: 可选注入 HybridRetriever 实例; None 时 lazy 创建
    """

    def __init__(self, db=None, llm=None, hybrid_retriever=None):
        self.db = db
        self.llm = llm
        self._hybrid = hybrid_retriever
        self._executor = None  # lazy init

    # ====================================================================
    # LangChain AgentExecutor 构建 (只 import, 不改任何 app/services 老文件)
    # ====================================================================

    async def _init_executor(self):
        """初始化 LangChain AgentExecutor

        - tools: vector_search / bm25_search / graph_search / web_search
        - 每个 tool 内部调用现有手写 service (只 import 不改)
        - 限速: AGENT_ROUTER_MAX_CALLS_PER_REQUEST = 1 (单请求最多 1 次 Agent 决策)
        """
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain.tools import Tool
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_anthropic import ChatAnthropic

        # LLM 未注入时复用 app.core.llm 的单例工厂 (跨 event loop 安全: 按需实例化)
        # 注: ChatAnthropic 是 langchain 自有客户端, 不能复用 LLMClient (SDK 层包装,
        # 非 langchain BaseChatModel), 必须从 settings 构造
        if self.llm is None:
            from app.core.llm import LLMClient

            self.llm = LLMClient()

        # 每个检索器暴露为 tool — 只 import 现有 service, 不改老文件
        tools = [
            Tool(
                name="vector_search",
                description=(
                    "语义向量检索知识库 (pgvector). 概念/方法/术语类问题优先. "
                    "参数: query(检索问题), top_k(返回条数, 默认 5)"
                ),
                coroutine=self._vector_only,
            ),
            Tool(
                name="bm25_search",
                description=(
                    "关键词精确检索知识库 (BM25). 精确关键词/代码/编号/型号类问题优先. "
                    "参数: query(检索问题), top_k(返回条数, 默认 5)"
                ),
                coroutine=self._bm25_only,
            ),
            Tool(
                name="graph_search",
                description=(
                    "实体关系图谱检索 (Neo4j). 实体关系/人物/项目依赖/关联知识类问题优先. "
                    "参数: query(检索问题), top_k(返回条数, 默认 5)"
                ),
                coroutine=self._graph_only,
            ),
            Tool(
                name="web_search",
                description=(
                    "联网搜索 (搜狗微信 + 必应双引擎). 知识库中没有的新知识/最新信息兜底. "
                    "参数: query(检索问题), top_k(返回条数, 默认 5)"
                ),
                coroutine=self._web_search,
            ),
        ]

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是检索路由 Agent。根据问题类型选择最合适的检索工具。"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        # LangChain 自有 ChatAnthropic — 从 settings 构造 (model 三件套, key 缺省走 env)
        from app.config import settings

        agent_llm_kwargs: Dict[str, Any] = {
            "model": getattr(settings, "AGENT_INTENT_MODEL", None)
            or settings.CLAUDE_MODEL
            or "claude-haiku-4-5-20251001",
            "temperature": 0.0,
            "max_tokens": 50,
        }
        if settings.CLAUDE_API_KEY:
            agent_llm_kwargs["api_key"] = settings.CLAUDE_API_KEY
        if settings.CLAUDE_BASE_URL:
            agent_llm_kwargs["base_url"] = settings.CLAUDE_BASE_URL
        agent_llm = ChatAnthropic(**agent_llm_kwargs)

        agent = create_tool_calling_agent(agent_llm, tools, prompt)
        self._executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=AGENT_ROUTER_MAX_CALLS_PER_REQUEST,
            handle_parsing_errors=True,
            verbose=False,
        )
        logger.info("AgentRetriever: LangChain AgentExecutor 初始化完成 (max_iterations=%s)",
                    AGENT_ROUTER_MAX_CALLS_PER_REQUEST)
        return self._executor

    async def _route(self, query: str) -> str:
        """轻量路由 — 先用小模型快速判断检索方式

        - 复用 app.core.llm.LLMClient (唯一 LLM 客户端, 30+ caller 同源)
        - claude-haiku 级别模型 (快且便宜), max_tokens=50
        - 文本解析失败回退 "vector" (最大召回面, 不浪费往返)
        """
        llm = self.llm
        if llm is None:
            from app.core.llm import LLMClient

            llm = LLMClient()
            self.llm = llm

        from app.config import settings
        from app.core.llm import extract_text_from_response

        try:
            resp = await llm.complete(
                messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
                model=getattr(settings, "AGENT_INTENT_MODEL", None) or "claude-haiku-4-5-20251001",
                max_tokens=50,
                temperature=0.0,
                # 思考型模型 (mimo-v2.5) 必须显式禁用 thinking, 否则只返 thinking block 不返 text
                thinking={"type": "disabled"},
            )
            text = extract_text_from_response(resp).strip().lower()
        except Exception as e:
            logger.warning(f"Agent Router _route LLM 调用失败, 回退 vector: {e}")
            return "vector"

        # 解析: 优先全词匹配, 兼容 "vector." / "vector " / markdown 包裹
        for route in _VALID_ROUTES:
            if re.search(rf"\b{route}\b", text):
                return route
        logger.warning(f"Agent Router _route 解析失败 ({text!r}), 回退 vector")
        return "vector"

    # ====================================================================
    # 单路检索 — 只 import 现有 service, 不改老文件
    # ====================================================================

    async def _vector_only(self, query: str, top_k: int = 5) -> List[Dict]:
        """向量单路 — 复用 HybridRetriever._vector_search (KnowledgeService.search_semantic)"""
        if self._hybrid is None:
            from app.services.hybrid_retriever import HybridRetriever

            self._hybrid = HybridRetriever(self.db)
        return await self._hybrid._vector_search(query, top_k, None)

    async def _bm25_only(self, query: str, top_k: int = 5) -> List[Dict]:
        """BM25 单路 — 复用现有 bm25_service (只 import 不改)"""
        from app.services.bm25_service import get_bm25_service

        bm25 = get_bm25_service()
        if bm25._corpus_size == 0 and self.db is not None:
            # 索引为空时从数据库刷新 (复用 HybridRetriever._refresh_bm25_index)
            if self._hybrid is None:
                from app.services.hybrid_retriever import HybridRetriever

                self._hybrid = HybridRetriever(self.db)
            await self._hybrid._refresh_bm25_index(bm25)
        return bm25.search(query, top_k=top_k)

    async def _graph_only(self, query: str, top_k: int = 5) -> List[Dict]:
        """图谱单路 — 复用 graph_retriever.retrieve_by_entities (只 import 不改)"""
        from app.services.graph_retriever import get_graph_retriever

        return await get_graph_retriever().retrieve_by_entities(query, top_k=top_k)

    async def _web_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """联网单路 — 复用 search_service (搜狗微信 + 必应双引擎, 只 import 不改)

        返回结果转成与本地检索一致的 dict 列表 (id 为 None, 由调用方按 web 语义消费).
        """
        from app.services.search_service import SearchService

        resp = await SearchService().search(query, max_results=top_k)
        results = resp.get("results", []) or []
        return [
            {
                "id": None,
                "title": r.get("title", ""),
                "content": r.get("snippet", ""),
                "url": r.get("url", ""),
                "score": 1.0 / (i + 1),
                "retrieval_method": "web",
            }
            for i, r in enumerate(results)
        ]

    # ====================================================================
    # 主入口 — 全链路 framework_gate 包裹
    # ====================================================================

    @framework_gate(
        feature_flag=AGENT_ROUTER_ENABLED,
        fallback_fn=None,
    )
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> List[Dict]:
        """动态检索 — 失败自动回退到 hybrid_retriever 4 路并发

        Args:
            query: 检索问题
            top_k: 返回条数
            **kwargs: 透传给单路检索器 (保留扩展位, 当前无消费方)

        Returns:
            List[dict] — 形状与 HybridRetriever.retrieve 一致
            (id/title/content/score/retrieval_method; vector 路带 normalized_score)
        """
        try:
            route = await self._route(query)
            if route == "vector":
                return await self._vector_only(query, top_k)
            elif route == "bm25":
                return await self._bm25_only(query, top_k)
            elif route == "graph":
                return await self._graph_only(query, top_k)
            elif route == "web":
                return await self._web_search(query, top_k)
            # _route 已保证合法值, 未知值兜底 hybrid
            logger.warning(f"Agent Router 未知 route={route!r}, 回退 hybrid")
            return await self._hybrid_retrieve(query, top_k)
        except Exception as e:
            logger.error(f"Agent Router 失败, 回退 hybrid: {e}", exc_info=True)
            return await self._hybrid_retrieve(query, top_k)

    async def _hybrid_retrieve(self, query: str, top_k: int) -> List[Dict]:
        """回退: 现有 hybrid_retriever.retrieve() 4 路并发"""
        from app.services.hybrid_retriever import HybridRetriever

        if self._hybrid is None:
            self._hybrid = HybridRetriever(self.db)
        return await self._hybrid.retrieve(query, top_k=top_k)


# 全局单例 (lazy, 模块级无副作用 — P0-1 铁律: 禁止 import-time 构造客户端)
_agent_retriever: Optional[AgentRetriever] = None


def get_agent_retriever(db=None, llm=None, hybrid_retriever=None) -> AgentRetriever:
    """获取 AgentRetriever 实例

    未初始化时创建; 已存在时复用 (传入的 db/llm 仅在首次创建时生效,
    与 get_hybrid_retriever / get_graph_retriever 同模式).
    """
    global _agent_retriever
    if _agent_retriever is None:
        _agent_retriever = AgentRetriever(
            db=db, llm=llm, hybrid_retriever=hybrid_retriever
        )
    return _agent_retriever

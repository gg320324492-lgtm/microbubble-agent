from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class KnowledgeBase(BaseModel):
    """知识库基础信息"""
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    related_topics: Optional[List[str]] = None
    knowledge_type: Optional[str] = None


class KnowledgeCreate(KnowledgeBase):
    """创建知识"""
    source: Optional[str] = None
    source_type: Optional[str] = None


class KnowledgeUpdate(BaseModel):
    """更新知识"""
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeResponse(KnowledgeBase):
    """知识响应"""
    id: int
    source: Optional[str] = None
    source_type: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    summary: Optional[str] = None
    analysis_status: Optional[str] = None
    auto_researched: Optional[bool] = False
    quality_score: Optional[float] = None
    entities: Optional[list] = None
    needs_review: Optional[bool] = False
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeList(BaseModel):
    """知识列表"""
    items: List[KnowledgeResponse]
    total: int


class KnowledgeSearchResult(BaseModel):
    """知识搜索结果"""
    id: int
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    score: float


class RelatedKnowledge(BaseModel):
    """关联知识"""
    id: int
    title: str
    category: Optional[str] = None
    summary: Optional[str] = None
    relation_type: str
    score: float
    reason: Optional[str] = None


class GraphNode(BaseModel):
    """知识图谱节点"""
    id: int
    title: str
    category: str
    size: float


class GraphEdge(BaseModel):
    """知识图谱边"""
    source: int
    target: int
    type: str
    score: float


class KnowledgeGraph(BaseModel):
    """知识图谱"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class DynamicCategory(BaseModel):
    """动态分类"""
    name: str
    count: int


class TagCloudItem(BaseModel):
    """标签云条目"""
    name: str
    count: int


class KnowledgeStats(BaseModel):
    """知识库统计"""
    total: int
    types: dict
    analysis_status: dict
    relations: int
    auto_researched: int


# ── RAG QA Schemas ──

class QASource(BaseModel):
    """QA 引用来源"""
    id: int
    title: str
    relevance: float


class QAResponse(BaseModel):
    """QA 响应"""
    answer: str
    sources: List[QASource]
    confidence: str  # high/medium/low
    research_triggered: bool = False
    research_queries: Optional[List[str]] = None
    search_results: Optional[dict] = None
    related_knowledge: Optional[List[int]] = None


# ── Auto-Research Schemas ──

class ResearchResultItem(BaseModel):
    """研究结果条目"""
    title: str
    url: str
    snippet: str
    ingested: bool
    knowledge_id: Optional[int] = None


class ResearchResponse(BaseModel):
    """研究响应"""
    query: str
    results: List[ResearchResultItem]
    new_knowledge_count: int
    message: str


class ReasonRequest(BaseModel):
    """多跳推理请求"""
    question: str
    max_hops: int = 2
    top_k: int = 6


class ReasonResponse(BaseModel):
    """多跳推理响应"""
    answer: str
    reasoning_chain: List[str]
    confidence: str
    gap_description: str = ""
    hops_used: int
    nodes_used: int


class ReviewQueueItem(BaseModel):
    """待审阅条目"""
    id: int
    title: str
    category: Optional[str] = None
    needs_review: bool
    analysis_status: str


class ReviewQueueResponse(BaseModel):
    """待审阅队列"""
    items: List[ReviewQueueItem]
    total: int

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
    formatted_content: Optional[str] = None
    analysis_status: Optional[str] = None
    auto_researched: Optional[bool] = False
    quality_score: Optional[float] = None
    entities: Optional[list] = None
    needs_review: Optional[bool] = False
    topic: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeListItem(BaseModel):
    """知识列表项（轻量版，不含完整 content，用 snippet 代替卡片预览）"""
    id: int
    title: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    related_topics: Optional[List[str]] = None
    knowledge_type: Optional[str] = None
    source: Optional[str] = None
    source_type: Optional[str] = None
    summary: Optional[str] = None
    snippet: Optional[str] = None  # content 前 200 字符，卡片预览用
    analysis_status: Optional[str] = None
    quality_score: Optional[float] = None
    needs_review: Optional[bool] = False
    topic: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # 2026-06-19 Phase 7: 多模态摘要（首图缩略图 + 图片数）
    thumbnail_url: Optional[str] = None
    image_count: int = 0

    class Config:
        from_attributes = True


class KnowledgeList(BaseModel):
    """知识列表"""
    items: List[KnowledgeListItem]
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


# ── Entity-Level Knowledge Graph Schemas ──

class EntityItem(BaseModel):
    id: int
    subject: str
    predicate: str
    object: str
    condition: Optional[str] = None
    confidence: float
    source_count: int
    occurrence_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EntityList(BaseModel):
    items: List[EntityItem]
    total: int
    page: int
    page_size: int


class EntityGraph(BaseModel):
    nodes: List[EntityItem]
    edges: List[dict]


class EntityDetail(EntityItem):
    sources: List[dict] = []


# ── Hypothesis Schemas ──

class HypothesisItem(BaseModel):
    id: int
    statement: str
    rationale: Optional[str] = None
    suggested_experiment: Optional[str] = None
    supporting_entity_ids: List[int] = []
    confidence: float
    priority: str
    status: str
    tags: List[str] = []
    validated_at: Optional[str] = None
    created_at: Optional[str] = None


class HypothesisList(BaseModel):
    items: List[HypothesisItem]
    total: int
    page: int
    page_size: int


# ── Formula / Quantitative Reasoning Schemas ──

class FormulaCategoryItem(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    children: List["FormulaCategoryItem"] = []
    formula_count: int = 0


class FormulaCategoryTree(BaseModel):
    categories: List[FormulaCategoryItem]


class FormulaItem(BaseModel):
    id: int
    knowledge_id: Optional[int] = None
    name: str
    formula_latex: Optional[str] = None
    variables: dict = {}
    result_unit: Optional[str] = None
    conditions: Optional[str] = None
    domain: Optional[str] = None
    confidence: float
    source_type: str = "extracted"
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None


class FormulaList(BaseModel):
    items: List[FormulaItem]
    total: int
    page: int
    page_size: int


# ── Multimodal Extraction Schemas (Phase 7) ──


class KnowledgeImageItem(BaseModel):
    """提取的图片（含 OCR + v28 结构化结果）"""
    id: int
    knowledge_id: int
    page_number: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    image_url: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    ocr_text: Optional[str] = None
    ocr_status: str  # pending/done/failed/skipped
    ocr_error: Optional[str] = None
    ocr_model: Optional[str] = None
    ocr_at: Optional[str] = None
    created_at: Optional[str] = None

    # ── v28 step 4: vision 模型输出的结构化字段 ──
    figure_no: Optional[str] = None  # "Fig. 2" / "Fig. S2" / "Table 1"
    figure_type: Optional[str] = None  # chart / scheme / cover / logo / publisher / mechanism
    is_core_figure: Optional[bool] = None
    is_publisher_image: Optional[bool] = None
    is_supporting_figure: Optional[bool] = None
    section_hint: Optional[str] = None
    visual_summary: Optional[str] = None
    anchor_paragraph_index: Optional[int] = None
    anchor_text: Optional[str] = None
    vision_confidence: Optional[float] = None
    vision_model_used: Optional[str] = None
    vision_analyzed_at: Optional[str] = None

    class Config:
        from_attributes = True


class KnowledgeImageList(BaseModel):
    """图片列表（含聚合统计）"""
    items: List[KnowledgeImageItem]
    total: int
    ocr_done: int
    ocr_failed: int
    ocr_pending: int


class ExtractionItem(BaseModel):
    """统一提取物（公式/表格/图表/图片-OCR 块）"""
    id: int
    knowledge_id: int
    source_image_id: Optional[int] = None
    kind: str  # formula/table/chart/image_block
    page_number: Optional[int] = None
    data: Optional[dict] = None
    content_text: Optional[str] = None
    confidence: float
    model_used: Optional[str] = None
    source: str = "auto"
    is_active: bool = True
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
        # 2026-06-19: model_used 触发 pydantic protected namespace 警告，
        # 显式置空允许以 model_ 开头的字段名
        protected_namespaces = ()


class ExtractionList(BaseModel):
    """提取物列表"""
    items: List[ExtractionItem]
    total: int
    by_kind: dict  # {formula: N, table: N, chart: N, image_block: N}


class MultimodalExtractResponse(BaseModel):
    """触发多模态提取响应（手动重跑用）"""
    ok: bool
    skipped: bool = False
    reason: Optional[str] = None
    knowledge_id: Optional[int] = None
    images_total: Optional[int] = None
    images_ocr_ok: Optional[int] = None
    extractions: Optional[dict] = None
    error: Optional[str] = None


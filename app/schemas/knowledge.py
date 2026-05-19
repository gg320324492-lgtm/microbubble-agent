from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class KnowledgeBase(BaseModel):
    """知识库基础信息"""
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None


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

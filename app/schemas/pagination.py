"""统一分页参数和响应模型"""

from pydantic import BaseModel, Field
from typing import TypeVar, Generic, List
from math import ceil

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页查询参数"""
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def skip(self) -> int:
        """计算 SQL OFFSET"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """SQL LIMIT"""
        return self.page_size


class PaginationMeta(BaseModel):
    """分页元数据"""
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应"""
    items: List[T]
    pagination: PaginationMeta

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        """工厂方法：自动计算 total_pages"""
        return cls(
            items=items,
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=ceil(total / page_size) if page_size > 0 else 0,
            ),
        )

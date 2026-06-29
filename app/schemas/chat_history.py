"""#043 账号持久化聊天历史 Pydantic schemas

Pydantic V2 + 完整字段校验（max_length / ge / le / Optional）

约束模式：
- Create*: 用户入参，必填字段必填，可选字段 Optional
- Update*: 增量更新（PATCH），所有字段 Optional
- Out*: API 返回，datetime 序列化为 ISO 8601 字符串
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ====== ChatSession ======

class ChatSessionCreate(BaseModel):
    """创建会话（前端 POST /chat/sessions）"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题，缺省时前端用首条消息自动生成")
    first_message: Optional[str] = Field(None, max_length=10000, description="首条 user 消息（同时创建一条 user 消息记录）")
    client_session_id: Optional[str] = Field(None, max_length=64, description="前端生成 session_id（localStorage 兼容），缺省时后端生成")


class ChatSessionUpdate(BaseModel):
    """更新会话元信息（PATCH /chat/sessions/{id}）"""
    title: Optional[str] = Field(None, max_length=200)
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None
    tags: Optional[List[str]] = Field(None, max_length=20, description="标签数组，单标签 max 20 字符")


class ChatSessionOut(BaseModel):
    """会话出参（GET /chat/sessions/{id} 包含完整 messages）"""
    id: str
    user_id: int
    title: str
    preview: str
    is_pinned: bool
    is_archived: bool
    tags: List[str]
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    messages: Optional[List["ChatMessageOut"]] = None  # 仅 GET /sessions/{id} 时填充

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListItem(BaseModel):
    """会话列表项（GET /chat/sessions 不含 messages 全文）"""
    id: str
    title: str
    preview: str
    is_pinned: bool
    is_archived: bool
    tags: List[str]
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListResponse(BaseModel):
    """会话列表分页响应"""
    items: List[ChatSessionListItem]
    total: int
    page: int
    page_size: int


# ====== ChatMessage ======

class ChatMessageCreate(BaseModel):
    """写入单条消息（POST /chat/sessions/{id}/messages）"""
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str = Field(..., max_length=1048576, description="1MB 软上限，超过会警告")
    rich_blocks: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tool_trace: Optional[Dict[str, Any]] = Field(default_factory=dict)
    message_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata", description="model / usage / intent_category")
    is_partial: Optional[bool] = False
    client_msg_id: Optional[str] = Field(None, max_length=64, description="幂等键")

    model_config = ConfigDict(populate_by_name=True)  # 同时接受 metadata 和 message_metadata


class ChatMessageOut(BaseModel):
    """消息出参"""
    id: int
    session_id: str
    role: str
    content: str
    rich_blocks: List[Dict[str, Any]]
    tool_trace: Dict[str, Any]
    # 注意: 不用 alias="metadata" 因为 SQLAlchemy ORM 对象有内置 .metadata 属性
    # (sqlalchemy.MetaData 类), 会导致 Pydantic from_attributes 误读
    # 改用 validation_alias 直接读 ORM 的 message_metadata 属性
    message_metadata: Dict[str, Any] = Field(validation_alias="message_metadata", serialization_alias="metadata")
    is_partial: bool
    is_deleted: bool
    client_msg_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatMessagesPage(BaseModel):
    """消息分页（GET /chat/sessions/{id}/messages）"""
    items: List[ChatMessageOut]
    has_more: bool
    next_after_id: Optional[int] = None


# ====== ChatShare ======

class ChatShareCreate(BaseModel):
    """创建分享（POST /chat/sessions/{id}/share）"""
    permission: Optional[str] = Field(default="read", pattern="^(read|read_write)$")
    expires_hours: Optional[int] = Field(None, ge=1, le=8760, description="过期小时数（1-8760，即 1h-365d），None 永不过期")


class ChatShareOut(BaseModel):
    """分享出参（含完整 share_url）"""
    id: str
    session_id: str
    shared_by: Optional[int]
    permission: str
    expires_at: Optional[datetime]
    view_count: int
    created_at: datetime
    share_url: str = Field("", description="完整分享 URL（前端可直接复制）")

    model_config = ConfigDict(from_attributes=True)


# ====== /chat/sync (旧数据迁移) ======

class ChatSyncLocalMessage(BaseModel):
    """localStorage 单条消息迁移"""
    client_msg_id: str = Field(..., max_length=64)
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str = Field(..., max_length=1048576)
    rich_blocks: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tool_trace: Optional[Dict[str, Any]] = Field(default_factory=dict)
    message_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata")
    created_at: Optional[datetime] = None
    client_msg_id_dedup: Optional[str] = None  # 别名（防前端写错）


class ChatSyncLocalSession(BaseModel):
    """localStorage 单个会话迁移"""
    id: str = Field(..., max_length=64)
    title: str = Field(..., max_length=200)
    preview: Optional[str] = ""
    is_pinned: Optional[bool] = False
    is_archived: Optional[bool] = False
    tags: Optional[List[str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    messages: List[ChatSyncLocalMessage] = Field(default_factory=list)


class ChatSyncRequest(BaseModel):
    """POST /chat/sync 入参"""
    local_sessions: List[ChatSyncLocalSession]
    last_synced_at: Optional[datetime] = None


class ChatSyncResponse(BaseModel):
    """POST /chat/sync 出参"""
    ok: bool
    server_sessions: List[ChatSessionListItem] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="冲突会话 [{session_id, reason}]")
    deleted_sids: List[str] = Field(default_factory=list, description="服务端已删除但客户端还存在的 sids")
    migrated_count: int = 0


# ====== /chat/sessions/search ======

class ChatSearchResultItem(BaseModel):
    """跨会话搜索单条结果"""
    session_id: str
    session_title: str
    message_id: int
    role: str
    snippet: str = Field(..., description="匹配片段，前后各 50 字符")
    created_at: datetime


class ChatSearchResponse(BaseModel):
    """跨会话搜索响应"""
    items: List[ChatSearchResultItem]
    total: int
    query: str
    page: int
    page_size: int


# ====== /chat/shares/{token} 公开端点 ======

class ChatSharePublicOut(BaseModel):
    """公开分享出参（匿名只读）"""
    id: str
    title: str
    preview: str
    created_at: datetime
    messages: List[ChatMessageOut]


# 解决 Pydantic 前向引用
ChatSessionOut.model_rebuild()

"""chat_experience_fixtures — W98 P2-E2E 5 铁证共享 fixtures

提供 pytest fixtures:
- mock_chat_db: AsyncMock SQLAlchemy session (含 Feedback + ChatMessage)
- mock_redis_empty: fakeredis / AsyncMock, 模拟 Redis flush 后状态
- test_session: 唯一 session_id (per-test, 保证隔离)
- test_user_id: 固定 user_id = 1
- mock_llm_client: 不调真 LLM, 返固定响应 (用模板替代)
- sample_messages: 12 轮预制对话历史

E2E 5 铁证覆盖:
1. 铁证 2 (续讲): _match_follow_up + _build_follow_up_context mock
2. 铁证 3 (自洽): mock intent_classifier + mock LLM 双轮
3. 重启铁证: mock Redis flushall + 真 _fetch_pg_messages path
4. 反馈铁证: FastAPI TestClient + mock db 落 Feedback
5. consistency 铁证: 抽样 5 题 + std + 实体重叠计算

不依赖真 DB / 真 Redis / 真 LLM.
所有外部 IO 全部 mock.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List, Optional, Tuple
import asyncio


# ============================================================================
# Constants
# ============================================================================

TEST_USER_ID = 1
TEST_SESSION_ID_PREFIX = "w98-p2-e2e-sess"


# ============================================================================
# Mock DB
# ============================================================================

@pytest.fixture
def mock_chat_db() -> AsyncMock:
    """Mock SQLAlchemy AsyncSession

    模拟:
    - execute(SELECT) → scalar_one_or_none / fetchall
    - add(obj) → 记录到内部 list
    - commit() → AsyncMock
    - refresh(obj) → 设置 obj.id
    """
    db = AsyncMock()

    # 默认 commit / refresh 不抛
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 1))

    # 默认 execute 返空结果
    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    empty_result.fetchall.return_value = []
    db.execute = AsyncMock(return_value=empty_result)

    # 记录 add 的对象 (供测试断言落库条数)
    db.added_objects: List[Any] = []
    db.add = MagicMock(side_effect=lambda obj: db.added_objects.append(obj))

    return db


# ============================================================================
# Mock Redis
# ============================================================================

@pytest.fixture
def mock_redis_empty() -> AsyncMock:
    """模拟 Redis flush 后状态: lrange 返回空"""
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.rpush = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.get = AsyncMock(return_value=None)
    redis.pipeline = MagicMock()
    return redis


@pytest.fixture
def mock_redis_with_messages() -> AsyncMock:
    """模拟 Redis 有缓存: lrange 返回预制 JSON 字符串"""
    import json
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[json.dumps(m, ensure_ascii=False) for m in msgs])
    redis.rpush = AsyncMock(return_value=len(msgs) + 1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.pipeline = MagicMock()
    return redis


# ============================================================================
# Test Session / User
# ============================================================================

@pytest.fixture
def test_session_id() -> str:
    """每测试一个唯一 session_id (避免跨测试污染)"""
    import uuid
    return f"{TEST_SESSION_ID_PREFIX}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_user_id() -> int:
    return TEST_USER_ID


# ============================================================================
# Sample Data
# ============================================================================

@pytest.fixture
def sample_chat_messages() -> List[Any]:
    """12 轮预制对话历史 (24 条消息), 覆盖 user / assistant"""
    from app.models.chat_history import ChatMessage
    msgs = []
    contents = [
        ("user", "介绍一下课题组近况"),
        ("assistant", "课题组有 18 人, 张三是博士"),
        ("user", "张三在做什么"),
        ("assistant", "张三博士研究方向是微纳米气泡稳定性"),
        ("user", "那他还在做这个吗"),
        ("assistant", "是的, 他继续在微气泡稳定性方向深耕"),
        ("user", "项目进展怎么样"),
        ("assistant", "国家自然科学基金面上项目 N0.1234 已结题"),
        ("user", "最近开了哪些会议"),
        ("assistant", "2026.7.28 例会讨论了声纹识别进展"),
        ("user", "知识库有什么新内容"),
        ("assistant", "本周新增 5 篇文献, 涉及微气泡应用"),
    ]
    for i, (role, content) in enumerate(contents, start=1):
        m = MagicMock(spec=ChatMessage)
        m.id = i
        m.role = role
        m.content = content
        m.is_partial = False
        m.is_deleted = False
        m.session_id = f"sess-{i // 2}"
        msgs.append(m)
    return msgs


@pytest.fixture
def sample_feedback_records() -> List[Dict[str, Any]]:
    """3 条预制 feedback (供一致性 / 反馈铁证复用)"""
    return [
        {"user_id": 1, "rating": 1, "comment": "helpful", "session_id": "s1"},
        {"user_id": 1, "rating": -1, "comment": "wrong", "session_id": "s2"},
        {"user_id": 1, "rating": 1, "comment": "good", "session_id": "s3"},
    ]


# ============================================================================
# Mock LLM Client
# ============================================================================

@pytest.fixture
def mock_llm_client():
    """Mock LLMClient - 不调真 API"""
    client = AsyncMock()
    client.complete = AsyncMock(return_value={
        "content": "我是小气助手, 课题组有 18 人",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    })
    return client


# ============================================================================
# Helper: 构造 FastAPI test app with mock db
# ============================================================================

def make_test_app_with_db(mock_db, mock_user=None):
    """构造带 mock db + 可选 mock user 的 FastAPI app

    与 tests/test_chat_feedback_api.py 模式一致 (W98 P1-D3 实战沉淀)
    """
    from fastapi import FastAPI
    from app.core.database import get_db
    from app.core.security import get_current_user_optional
    from app.api.v1.chat_feedback import router as chat_feedback_router

    app = FastAPI()

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    if mock_user is not None:
        async def _override_user():
            return mock_user
        app.dependency_overrides[get_current_user_optional] = _override_user

    app.include_router(chat_feedback_router, prefix="/api/v1")
    return app


# ============================================================================
# Helper: 实体重叠率计算 (consistency 铁证)
# ============================================================================

# 关键实体词典 (微纳米气泡课题组场景, 与 sample_chat_messages 对齐)
ENTITY_KEYWORDS = [
    "张三", "李四", "王五",
    "微纳米气泡", "微气泡", "稳定性",
    "课题组", "博士", "硕士",
    "国家自然科学基金", "国自然", "面上项目", "结题",
    "例会", "声纹",
    "知识库", "文献",
    "18 人",
]


def entity_overlap_ratio(text_a: str, text_b: str) -> float:
    """计算两段文本的关键实体重叠率 (基于领域关键词词典)

    用于 consistency 铁证 + 续讲铁证:
    - 双轮回答的实体覆盖率 (round 1 关键词 / round 2 关键词)
    - 续讲上下文的实体覆盖率 (上轮 / 上下文)
    - 阈值 > 0.5 视为一致

    词典优先 (避免 2-4 字切分稀释), 退化回 2-3 字中文片段.
    """
    def extract_entities(text: str) -> set:
        entities = set()
        # 1. 优先匹配词典
        for kw in ENTITY_KEYWORDS:
            if kw in text:
                entities.add(kw)
        # 2. 退化: 抽取 3-4 字中文片段 (不含标点)
        if not entities:
            import re
            words = re.findall(r'[一-鿿]{3,4}', text)
            entities = set(words)
        return entities

    a = extract_entities(text_a)
    b = extract_entities(text_b)
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0

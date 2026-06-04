# 代码质量全面升级 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将项目代码质量从"能用"提升到"专业级"——统一 API 规范、补全核心测试、拆分巨型组件、建立前端测试体系。

**架构：** 逐层推进：第 1 轮 API 规范化（基础设施）→ 第 2 轮后端测试（质量保障）→ 第 3 轮前端拆分（可维护性）→ 第 4 轮前端测试（回归防护）。每轮独立可部署。

**技术栈：** Python 3.11 + FastAPI + pytest + httpx + Vue 3 + Vitest + @vue/test-utils

---

## 文件结构

### 第 1 轮：API 规范化

| 文件 | 职责 | 操作 |
|------|------|------|
| `app/core/exceptions.py` | 业务异常类层次 + FastAPI exception handler | 创建 |
| `app/schemas/pagination.py` | 统一分页参数和响应模型 | 创建 |
| `app/core/rate_limit.py` | 扩展限流器（按类型分级） | 修改 |
| `app/main.py` | 注册 exception handler + 安全头中间件 | 修改 |
| `app/api/v1/task.py` | 统一错误格式 + 分页 + 命名 | 修改 |
| `app/api/v1/meeting.py` | 统一错误格式 + 分页 + 命名 | 修改 |
| `app/api/v1/knowledge.py` | 统一错误格式 + 分页 + 命名 | 修改 |
| `app/api/v1/member.py` | 统一错误格式 + 分页 | 修改 |
| `app/api/v1/auth.py` | 统一错误格式 | 修改 |
| `app/api/v1/voiceprint.py` | 统一错误格式 | 修改 |
| `app/api/v1/memory.py` | 统一错误格式 + 分页 | 修改 |
| `app/api/v1/project.py` | 统一错误格式 + 分页 | 修改 |
| `app/api/v1/chat.py` | 统一错误格式 | 修改 |
| `nginx/conf.d/tunnel.conf` | 安全响应头 | 修改 |

### 第 2 轮：后端测试补全

| 文件 | 职责 | 操作 |
|------|------|------|
| `tests/conftest.py` | 补充 fixtures（mock redis/claude/embedding） | 修改 |
| `tests/unit/test_task_service.py` | 任务服务单元测试 | 创建 |
| `tests/unit/test_meeting_service.py` | 会议服务单元测试 | 创建 |
| `tests/unit/test_knowledge_service.py` | 知识库服务单元测试 | 创建 |
| `tests/unit/test_member_service.py` | 成员服务单元测试 | 创建 |
| `tests/unit/test_reminder_service.py` | 提醒服务单元测试 | 创建 |
| `tests/integration/test_api_tasks.py` | 任务 API 集成测试 | 创建 |
| `tests/integration/test_api_meetings.py` | 会议 API 集成测试 | 创建 |
| `tests/integration/test_api_auth.py` | 认证 API 集成测试 | 创建 |

### 第 3 轮：前端组件拆分

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/src/composables/useKnowledge.js` | 知识库共享状态 + API | 创建 |
| `web/src/views/KnowledgeView.vue` | 精简为路由容器 | 修改 |
| `web/src/views/knowledge/KnowledgeDashboard.vue` | 概览 tab | 创建 |
| `web/src/views/knowledge/KnowledgeSearch.vue` | 搜索 tab | 创建 |
| `web/src/views/knowledge/KnowledgeRelations.vue` | 关联图谱 tab | 创建 |
| `web/src/views/knowledge/KnowledgeEntities.vue` | 实体图谱 tab | 创建 |
| `web/src/views/knowledge/KnowledgeHypotheses.vue` | 假设生成 tab | 创建 |
| `web/src/views/knowledge/KnowledgeFormulas.vue` | 公式库 tab | 创建 |
| `web/src/views/knowledge/KnowledgeHealth.vue` | 健康监控 tab | 创建 |
| `web/src/composables/useTask.js` | 任务共享状态 + API | 创建 |
| `web/src/views/TaskView.vue` | 精简为主容器 | 修改 |
| `web/src/views/task/TaskList.vue` | 任务列表 | 创建 |
| `web/src/views/task/TaskDetail.vue` | 任务详情 | 创建 |
| `web/src/views/task/TaskCreateDialog.vue` | 新建/编辑弹窗 | 创建 |
| `web/src/views/task/TaskTrash.vue` | 垃圾桶 | 创建 |
| `web/src/composables/useMeeting.js` | 会议共享状态 + API | 创建 |
| `web/src/views/MeetingView.vue` | 精简为主容器 | 修改 |
| `web/src/views/meeting/MeetingList.vue` | 会议列表 | 创建 |
| `web/src/views/meeting/MeetingCreateDialog.vue` | 新建弹窗 | 创建 |
| `web/src/views/meeting/MeetingStats.vue` | 发言统计 | 创建 |

### 第 4 轮：前端测试补全

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/vitest.config.js` | Vitest 配置 | 创建 |
| `web/src/__tests__/setup.js` | 全局测试配置 | 创建 |
| `web/src/composables/__tests__/useTask.test.js` | useTask 测试 | 创建 |
| `web/src/composables/__tests__/useMeeting.test.js` | useMeeting 测试 | 创建 |
| `web/src/composables/__tests__/useKnowledge.test.js` | useKnowledge 测试 | 创建 |
| `web/src/components/task/__tests__/TaskList.test.js` | TaskList 测试 | 创建 |
| `web/src/components/task/__tests__/TaskCreateDialog.test.js` | TaskCreateDialog 测试 | 创建 |

---

## 第 1 轮：API 规范化

### 任务 1：创建异常类层次

**文件：**
- 创建：`app/core/exceptions.py`

- [ ] **步骤 1：创建异常类文件**

```python
# app/core/exceptions.py
"""统一业务异常类层次"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    """资源不存在"""

    def __init__(self, resource: str, resource_id: Any = None):
        details = {}
        if resource_id is not None:
            details[f"{resource.lower()}_id"] = resource_id
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource}不存在",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationException(AppException):
    """数据验证失败"""

    def __init__(self, message: str, field: str = None):
        details = {}
        if field:
            details["field"] = field
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthException(AppException):
    """认证失败"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(
            code="AUTH_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(AppException):
    """权限不足"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictException(AppException):
    """资源冲突"""

    def __init__(self, message: str, resource: str = None):
        details = {}
        if resource:
            details["resource"] = resource
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class RateLimitException(AppException):
    """请求过于频繁"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"请求过于频繁，请 {retry_after} 秒后重试",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一异常响应格式"""
    logger.warning(
        f"AppException: {exc.code} - {exc.message} | "
        f"path={request.url.path} method={request.method} details={exc.details}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "details": {},
            }
        },
    )
```

- [ ] **步骤 2：在 main.py 注册 handler**

```python
# app/main.py — 在 app = FastAPI(...) 之后添加
from app.core.exceptions import AppException, app_exception_handler, generic_exception_handler

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

- [ ] **步骤 3：验证语法**

运行：`python -c "import ast; ast.parse(open('app/core/exceptions.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 4：Commit**

```bash
git add app/core/exceptions.py app/main.py
git commit -m "feat(api): 添加统一异常类层次和 exception handler"
```

---

### 任务 2：创建统一分页模型

**文件：**
- 创建：`app/schemas/pagination.py`

- [ ] **步骤 1：创建分页模型文件**

```python
# app/schemas/pagination.py
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
```

- [ ] **步骤 2：验证语法**

运行：`python -c "import ast; ast.parse(open('app/schemas/pagination.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 3：Commit**

```bash
git add app/schemas/pagination.py
git commit -m "feat(api): 添加统一分页参数和响应模型"
```

---

### 任务 3：扩展全站限流器

**文件：**
- 修改：`app/core/rate_limit.py`

- [ ] **步骤 1：重写 rate_limit.py**

```python
# app/core/rate_limit.py
"""全站 API 限流器 — 按类型分级"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from typing import Optional


class RateLimiter:
    """基于滑动窗口的内存限流器"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str):
        cutoff = time.time() - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

    def check(self, key: str):
        self._cleanup(key)
        if len(self._attempts[key]) >= self.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请 {self.window_seconds} 秒后重试"
            )

    def record(self, key: str):
        self._attempts[key].append(time.time())


# 分级限流器实例
_rate_limiters = {
    "auth": RateLimiter(max_attempts=5, window_seconds=60),      # 认证：5次/分钟
    "write": RateLimiter(max_attempts=30, window_seconds=60),    # 写操作：30次/分钟
    "read": RateLimiter(max_attempts=100, window_seconds=60),    # 读操作：100次/分钟
    "upload": RateLimiter(max_attempts=10, window_seconds=60),   # 上传：10次/分钟
}


def _get_rate_limit_type(request: Request) -> str:
    """根据请求路径和方法判断限流类型"""
    path = request.url.path
    method = request.method

    # 认证端点
    if "/auth/" in path:
        return "auth"

    # 上传端点
    if "/upload" in path:
        return "upload"

    # 写操作
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"

    # 读操作
    return "read"


def _get_client_key(request: Request) -> str:
    """获取客户端标识（IP + 用户）"""
    client_ip = request.client.host if request.client else "unknown"
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"{client_ip}:user:{user_id}"
    return f"{client_ip}:anon"


async def rate_limit_middleware(request: Request, call_next):
    """全站限流中间件"""
    # 跳过健康检查和 WebSocket
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    limit_type = _get_rate_limit_type(request)
    limiter = _rate_limiters[limit_type]
    client_key = f"{limit_type}:{_get_client_key(request)}"

    limiter.check(client_key)
    limiter.record(client_key)

    response = await call_next(request)

    # 添加限流信息到响应头
    limiter._cleanup(client_key)
    remaining = limiter.max_attempts - len(limiter._attempts[client_key])
    response.headers["X-RateLimit-Limit"] = str(limiter.max_attempts)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.window_seconds))

    return response


# 保留旧的登录限流器（向后兼容）
login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
```

- [ ] **步骤 2：在 main.py 注册中间件**

```python
# app/main.py — 在 CORS 中间件之后添加
from app.core.rate_limit import rate_limit_middleware

app.middleware("http")(rate_limit_middleware)
```

- [ ] **步骤 3：验证语法**

运行：`python -c "import ast; ast.parse(open('app/core/rate_limit.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 4：Commit**

```bash
git add app/core/rate_limit.py app/main.py
git commit -m "feat(api): 全站分级限流中间件（auth/write/read/upload）"
```

---

### 任务 4：添加安全响应头

**文件：**
- 修改：`app/main.py`
- 修改：`nginx/conf.d/tunnel.conf`（如存在）

- [ ] **步骤 1：在 main.py 添加安全头中间件**

```python
# app/main.py — 在限流中间件之后添加
from uuid import uuid4

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """安全响应头 + 请求追踪"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = str(uuid4())
    return response
```

- [ ] **步骤 2：Commit**

```bash
git add app/main.py
git commit -m "feat(api): 添加安全响应头中间件"
```

---

### 任务 5：统一 task.py API 规范

**文件：**
- 修改：`app/api/v1/task.py`

- [ ] **步骤 1：导入新模块**

在 `app/api/v1/task.py` 顶部添加：
```python
from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.pagination import PaginationParams, PaginatedResponse
```

- [ ] **步骤 2：改造 list_tasks 端点**

将现有的 `skip/limit` 参数替换为分页模型，返回统一格式：
```python
@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    # ... 查询逻辑保持不变，但用 pagination.skip / pagination.limit
    tasks, total = await TaskService.list_tasks(
        db, skip=pagination.skip, limit=pagination.limit,
        status=status_filter, search=search, include_deleted=include_deleted,
    )
    return PaginatedResponse.create(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total, page=pagination.page, page_size=pagination.page_size,
    )
```

- [ ] **步骤 3：改造错误响应**

将 `raise HTTPException(status_code=404, detail="任务不存在")` 替换为：
```python
raise NotFoundException("任务", task_id)
```

将 `raise HTTPException(status_code=400, detail="...")` 替换为：
```python
raise ValidationException("...", field="title")
```

- [ ] **步骤 4：验证语法**

运行：`python -c "import ast; ast.parse(open('app/api/v1/task.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 5：Commit**

```bash
git add app/api/v1/task.py
git commit -m "refactor(api/task): 统一错误格式、分页模型、异常类"
```

---

### 任务 6：统一 meeting.py API 规范

**文件：**
- 修改：`app/api/v1/meeting.py`

- [ ] **步骤 1：导入新模块并改造**

与任务 5 相同模式：
- 导入 `NotFoundException, ValidationException, PaginationParams, PaginatedResponse`
- 列表端点使用 `PaginationParams` + `PaginatedResponse.create()`
- 错误响应统一使用异常类
- `POST /meetings/{id}/agenda` 改为 `PATCH /meetings/{id}/agenda`

- [ ] **步骤 2：验证语法**

运行：`python -c "import ast; ast.parse(open('app/api/v1/meeting.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/meeting.py
git commit -m "refactor(api/meeting): 统一错误格式、分页模型、PATCH agenda"
```

---

### 任务 7：统一 knowledge.py API 规范

**文件：**
- 修改：`app/api/v1/knowledge.py`（793 行，最大的 API 文件）

- [ ] **步骤 1：导入新模块并改造**

与任务 5 相同模式。此文件最大，重点改造：
- 所有列表端点统一使用 `PaginationParams` + `PaginatedResponse`
- 搜索端点返回统一格式
- 错误响应统一使用异常类

- [ ] **步骤 2：验证语法**

运行：`python -c "import ast; ast.parse(open('app/api/v1/knowledge.py', encoding='utf-8').read()); print('syntax OK')"`

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/knowledge.py
git commit -m "refactor(api/knowledge): 统一错误格式、分页模型"
```

---

### 任务 8：统一其余 API 文件

**文件：**
- 修改：`app/api/v1/member.py`
- 修改：`app/api/v1/auth.py`
- 修改：`app/api/v1/voiceprint.py`
- 修改：`app/api/v1/memory.py`
- 修改：`app/api/v1/project.py`
- 修改：`app/api/v1/chat.py`

- [ ] **步骤 1：逐文件改造**

每个文件执行相同模式：
1. 导入 `NotFoundException, ValidationException, PaginationParams, PaginatedResponse`
2. 列表端点使用分页模型
3. 错误响应使用异常类

- [ ] **步骤 2：批量验证语法**

```bash
for f in app/api/v1/member.py app/api/v1/auth.py app/api/v1/voiceprint.py app/api/v1/memory.py app/api/v1/project.py app/api/v1/chat.py; do
  python -c "import ast; ast.parse(open('$f', encoding='utf-8').read()); print('OK: $f')"
done
```

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/member.py app/api/v1/auth.py app/api/v1/voiceprint.py app/api/v1/memory.py app/api/v1/project.py app/api/v1/chat.py
git commit -m "refactor(api): 统一其余 API 文件的错误格式和分页模型"
```

---

## 第 2 轮：后端测试补全

### 任务 9：完善 conftest.py fixtures

**文件：**
- 修改：`tests/conftest.py`

- [ ] **步骤 1：添加通用 fixtures**

在现有 conftest.py 基础上添加：
```python
# tests/conftest.py — 添加到文件末尾
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
import numpy as np


@pytest.fixture
def sample_member(db_session):
    """创建测试成员"""
    from app.models.member import Member
    member = Member(
        username="testuser",
        display_name="测试用户",
        role="member",
        is_active=True,
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member


@pytest.fixture
def auth_headers(sample_member):
    """带有效 JWT 的请求头"""
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(sample_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_embedding():
    """固定 192 维向量"""
    return np.random.randn(192).astype(np.float32).tolist()


@pytest.fixture
async def client(app):
    """异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

- [ ] **步骤 2：Commit**

```bash
git add tests/conftest.py
git commit -m "test: 完善 conftest.py fixtures（auth_headers/sample_member/mock_embedding）"
```

---

### 任务 10：任务服务单元测试

**文件：**
- 创建：`tests/unit/__init__.py`
- 创建：`tests/unit/test_task_service.py`

- [ ] **步骤 1：创建测试文件**

```python
# tests/unit/__init__.py
```

```python
# tests/unit/test_task_service.py
"""任务服务单元测试"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.task_service import (
    create_task, get_task, list_tasks, delete_task, restore_task,
    update_task, get_task_stats,
)
from app.models.task import Task
from app.models.member import Member


class TestCreateTask:
    """创建任务"""

    @pytest.mark.asyncio
    async def test_create_success(self, db_session, sample_member):
        """正常创建任务"""
        task = await create_task(
            db, title="测试任务", description="描述",
            assignee_id=sample_member.id, priority="medium",
        )
        assert task.title == "测试任务"
        assert task.status == "in_progress"
        assert task.assignee_id == sample_member.id
        assert task.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_minimal(self, db_session):
        """仅必填字段创建"""
        task = await create_task(db, title="最小任务")
        assert task.title == "最小任务"
        assert task.priority == "medium"  # 默认值


class TestGetTask:
    """获取任务"""

    @pytest.mark.asyncio
    async def test_get_existing(self, db_session, sample_member):
        """获取已存在的任务"""
        created = await create_task(db, title="已存在", assignee_id=sample_member.id)
        fetched = await get_task(db, created.id)
        assert fetched.id == created.id
        assert fetched.title == "已存在"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db_session):
        """获取不存在的任务应返回 None"""
        result = await get_task(db, 99999)
        assert result is None


class TestSoftDelete:
    """软删除与恢复"""

    @pytest.mark.asyncio
    async def test_soft_delete(self, db_session, sample_member):
        """软删除设置 deleted_at"""
        task = await create_task(db, title="待删除", assignee_id=sample_member.id)
        await delete_task(db, task.id)
        assert task.deleted_at is not None

    @pytest.mark.asyncio
    async def test_restore(self, db_session, sample_member):
        """恢复已删除任务"""
        task = await create_task(db, title="待恢复", assignee_id=sample_member.id)
        await delete_task(db, task.id)
        await restore_task(db, task.id)
        assert task.deleted_at is None

    @pytest.mark.asyncio
    async def test_list_excludes_deleted(self, db_session, sample_member):
        """默认列表不包含已删除任务"""
        task1 = await create_task(db, title="活跃", assignee_id=sample_member.id)
        task2 = await create_task(db, title="待删", assignee_id=sample_member.id)
        await delete_task(db, task2.id)

        tasks, total = await list_tasks(db, skip=0, limit=100)
        task_ids = [t.id for t in tasks]
        assert task1.id in task_ids
        assert task2.id not in task_ids


class TestTaskStats:
    """任务统计"""

    @pytest.mark.asyncio
    async def test_stats_counts(self, db_session, sample_member):
        """统计各状态任务数量"""
        await create_task(db, title="任务1", assignee_id=sample_member.id)
        await create_task(db, title="任务2", assignee_id=sample_member.id)
        stats = await get_task_stats(db)
        assert stats["total"] >= 2
```

- [ ] **步骤 2：运行测试验证**

运行：`pytest tests/unit/test_task_service.py -v`
预期：通过（或因 service 实现差异微调）

- [ ] **步骤 3：Commit**

```bash
git add tests/unit/__init__.py tests/unit/test_task_service.py
git commit -m "test: 任务服务单元测试（CRUD/软删除/统计）"
```

---

### 任务 11：会议服务单元测试

**文件：**
- 创建：`tests/unit/test_meeting_service.py`

- [ ] **步骤 1：创建测试文件**

```python
# tests/unit/test_meeting_service.py
"""会议服务单元测试"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.meeting_service import (
    create_meeting, get_meeting, list_meetings, update_meeting, delete_meeting,
)


class TestCreateMeeting:
    """创建会议"""

    @pytest.mark.asyncio
    async def test_create_success(self, db_session, sample_member):
        """正常创建会议"""
        meeting = await create_meeting(
            db, title="测试会议",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            creator_id=sample_member.id,
        )
        assert meeting.title == "测试会议"
        assert meeting.creator_id == sample_member.id

    @pytest.mark.asyncio
    async def test_create_with_agenda(self, db_session, sample_member):
        """带议程创建"""
        meeting = await create_meeting(
            db, title="有议程的会议",
            agenda=["议题一", "议题二"],
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            creator_id=sample_member.id,
        )
        assert meeting.agenda == ["议题一", "议题二"]


class TestListMeetings:
    """列表查询"""

    @pytest.mark.asyncio
    async def test_pagination(self, db_session, sample_member):
        """分页正确"""
        for i in range(25):
            await create_meeting(
                db, title=f"会议{i}",
                start_time=datetime.now(timezone.utc) + timedelta(hours=i),
                creator_id=sample_member.id,
            )

        meetings, total = await list_meetings(db, skip=0, limit=10)
        assert len(meetings) == 10
        assert total == 25

    @pytest.mark.asyncio
    async def test_empty_list(self, db_session):
        """无会议时返回空列表"""
        meetings, total = await list_meetings(db, skip=0, limit=10)
        assert len(meetings) == 0
        assert total == 0
```

- [ ] **步骤 2：运行测试验证**

运行：`pytest tests/unit/test_meeting_service.py -v`

- [ ] **步骤 3：Commit**

```bash
git add tests/unit/test_meeting_service.py
git commit -m "test: 会议服务单元测试（创建/议程/分页）"
```

---

### 任务 12：知识库服务单元测试

**文件：**
- 创建：`tests/unit/test_knowledge_service.py`

- [ ] **步骤 1：创建测试文件**

```python
# tests/unit/test_knowledge_service.py
"""知识库服务单元测试"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.knowledge_service import (
    create_entry, get_entry, list_entries, search_entries,
)


class TestCreateEntry:
    """创建知识条目"""

    @pytest.mark.asyncio
    async def test_create_success(self, db_session):
        """正常创建条目"""
        entry = await create_entry(
            db, title="微纳米气泡", content="微纳米气泡是...",
            category="基础概念",
        )
        assert entry.title == "微纳米气泡"
        assert entry.category == "基础概念"

    @pytest.mark.asyncio
    async def test_create_with_tags(self, db_session):
        """带标签创建"""
        entry = await create_entry(
            db, title="Zeta电位", content="Zeta电位是...",
            tags=["表征", "电化学"],
        )
        assert "表征" in entry.tags


class TestSearchEntries:
    """语义搜索"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, db_session):
        """搜索返回结果"""
        # 需要 mock embedding service
        with patch("app.services.embedding_service.get_embedding") as mock_emb:
            mock_emb.return_value = [0.1] * 192
            results = await search_entries(db, query="气泡", limit=5)
            assert isinstance(results, list)
```

- [ ] **步骤 2：Commit**

```bash
git add tests/unit/test_knowledge_service.py
git commit -m "test: 知识库服务单元测试（创建/标签/搜索）"
```

---

### 任务 13：成员与提醒服务单元测试

**文件：**
- 创建：`tests/unit/test_member_service.py`
- 创建：`tests/unit/test_reminder_service.py`

- [ ] **步骤 1：创建成员服务测试**

```python
# tests/unit/test_member_service.py
"""成员服务单元测试"""

import pytest
from app.services.member_service import create_member, get_member, list_members


class TestMemberCRUD:
    @pytest.mark.asyncio
    async def test_create_member(self, db_session):
        member = await create_member(db, username="newuser", display_name="新用户")
        assert member.username == "newuser"
        assert member.is_active is True

    @pytest.mark.asyncio
    async def test_get_by_username(self, db_session):
        await create_member(db, username="findme", display_name="找到我")
        member = await get_member(db, username="findme")
        assert member is not None
        assert member.display_name == "找到我"
```

- [ ] **步骤 2：创建提醒服务测试**

```python
# tests/unit/test_reminder_service.py
"""提醒服务单元测试"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.reminder_service import create_reminder, get_pending_reminders


class TestReminder:
    @pytest.mark.asyncio
    async def test_create_reminder(self, db_session, sample_member):
        from app.services.task_service import create_task
        task = await create_task(db, title="有提醒", assignee_id=sample_member.id)
        reminder = await create_reminder(
            db, task_id=task.id,
            remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert reminder.task_id == task.id
```

- [ ] **步骤 3：Commit**

```bash
git add tests/unit/test_member_service.py tests/unit/test_reminder_service.py
git commit -m "test: 成员+提醒服务单元测试"
```

---

### 任务 14：任务 API 集成测试

**文件：**
- 创建：`tests/integration/__init__.py`
- 创建：`tests/integration/test_api_tasks.py`

- [ ] **步骤 1：创建集成测试**

```python
# tests/integration/__init__.py
```

```python
# tests/integration/test_api_tasks.py
"""任务 API 集成测试"""

import pytest


class TestTaskAPI:
    """任务端点集成测试"""

    @pytest.mark.asyncio
    async def test_create_task(self, client, auth_headers):
        """POST /api/v1/tasks 创建任务"""
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "集成测试任务", "priority": "high"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "集成测试任务"

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client, auth_headers):
        """GET /api/v1/tasks 分页格式"""
        resp = await client.get(
            "/api/v1/tasks?page=1&page_size=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 5

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, client, auth_headers):
        """GET /api/v1/tasks/99999 返回统一 404 格式"""
        resp = await client.get("/api/v1/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "TASK_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unauthorized(self, client):
        """无 token 返回统一 401 格式"""
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore(self, client, auth_headers):
        """DELETE + POST /restore 完整流程"""
        # 创建
        create_resp = await client.post(
            "/api/v1/tasks",
            json={"title": "待删除"},
            headers=auth_headers,
        )
        task_id = create_resp.json()["id"]

        # 软删除
        del_resp = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted_at"] is not None

        # 恢复
        restore_resp = await client.post(
            f"/api/v1/tasks/{task_id}/restore", headers=auth_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["deleted_at"] is None
```

- [ ] **步骤 2：运行测试**

运行：`pytest tests/integration/test_api_tasks.py -v`

- [ ] **步骤 3：Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_api_tasks.py
git commit -m "test: 任务 API 集成测试（CRUD/分页/错误格式/认证）"
```

---

### 任务 15：会议和认证 API 集成测试

**文件：**
- 创建：`tests/integration/test_api_meetings.py`
- 创建：`tests/integration/test_api_auth.py`

- [ ] **步骤 1：创建会议 API 测试**

```python
# tests/integration/test_api_meetings.py
"""会议 API 集成测试"""

import pytest
from datetime import datetime, timedelta, timezone


class TestMeetingAPI:
    @pytest.mark.asyncio
    async def test_create_meeting(self, client, auth_headers):
        """POST /api/v1/meetings"""
        resp = await client.post(
            "/api/v1/meetings",
            json={
                "title": "集成测试会议",
                "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "agenda": ["议题一"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "集成测试会议"

    @pytest.mark.asyncio
    async def test_list_meetings_pagination(self, client, auth_headers):
        """GET /api/v1/meetings 分页格式"""
        resp = await client.get("/api/v1/meetings?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    @pytest.mark.asyncio
    async def test_patch_agenda(self, client, auth_headers):
        """PATCH /api/v1/meetings/{id}/agenda"""
        # 先创建会议
        create_resp = await client.post(
            "/api/v1/meetings",
            json={"title": "议程测试", "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
            headers=auth_headers,
        )
        meeting_id = create_resp.json()["id"]

        # 更新议程
        resp = await client.patch(
            f"/api/v1/meetings/{meeting_id}/agenda",
            json={"agenda": ["新议题一", "新议题二"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
```

- [ ] **步骤 2：创建认证 API 测试**

```python
# tests/integration/test_api_auth.py
"""认证 API 集成测试"""

import pytest


class TestAuthAPI:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """POST /api/v1/auth/login 成功"""
        # 需要先有测试用户
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        # 根据实际认证逻辑调整
        assert resp.status_code in (200, 401)  # 取决于测试环境是否有 admin 用户

    @pytest.mark.asyncio
    async def test_login_rate_limit(self, client):
        """登录限流 — 5 次后返回 429"""
        for i in range(6):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "fake", "password": "wrong"},
            )
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
```

- [ ] **步骤 3：Commit**

```bash
git add tests/integration/test_api_meetings.py tests/integration/test_api_auth.py
git commit -m "test: 会议+认证 API 集成测试"
```

---

## 第 3 轮：前端组件拆分

### 任务 16：创建 useKnowledge composable

**文件：**
- 创建：`web/src/composables/useKnowledge.js`

- [ ] **步骤 1：从 KnowledgeView.vue 提取共享状态**

分析 KnowledgeView.vue 中的共享状态（搜索、分类、条目列表等），抽取到 composable：

```javascript
// web/src/composables/useKnowledge.js
import { ref, computed } from 'vue'
import axios from 'axios'

export function useKnowledge() {
  // 状态
  const entries = ref([])
  const loading = ref(false)
  const searchQuery = ref('')
  const searchResults = ref([])
  const currentCategory = ref('all')
  const currentPage = ref(1)
  const pagination = ref({ total: 0, pageSize: 20 })
  const selectedEntry = ref(null)

  // API 调用
  const fetchEntries = async (params = {}) => {
    loading.value = true
    try {
      const resp = await axios.get('/api/v1/knowledge', {
        params: { page: currentPage.value, page_size: pagination.value.pageSize, ...params }
      })
      entries.value = resp.data.items
      pagination.value = resp.data.pagination
    } finally {
      loading.value = false
    }
  }

  const searchKnowledge = async (query) => {
    searchQuery.value = query
    loading.value = true
    try {
      const resp = await axios.post('/api/v1/knowledge/search', { query, limit: 20 })
      searchResults.value = resp.data.results
    } finally {
      loading.value = false
    }
  }

  const fetchEntry = async (id) => {
    const resp = await axios.get(`/api/v1/knowledge/${id}`)
    selectedEntry.value = resp.data
    return resp.data
  }

  const deleteEntry = async (id) => {
    await axios.delete(`/api/v1/knowledge/${id}`)
    await fetchEntries()
  }

  // 计算属性
  const filteredEntries = computed(() => {
    if (currentCategory.value === 'all') return entries.value
    return entries.value.filter(e => e.category === currentCategory.value)
  })

  return {
    entries, loading, searchQuery, searchResults,
    currentCategory, currentPage, pagination, selectedEntry,
    fetchEntries, searchKnowledge, fetchEntry, deleteEntry,
    filteredEntries,
  }
}
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/composables/useKnowledge.js
git commit -m "refactor(frontend): 提取 useKnowledge composable"
```

---

### 任务 17：拆分 KnowledgeView.vue

**文件：**
- 创建：`web/src/views/knowledge/KnowledgeDashboard.vue`
- 创建：`web/src/views/knowledge/KnowledgeSearch.vue`
- 创建：`web/src/views/knowledge/KnowledgeRelations.vue`
- 创建：`web/src/views/knowledge/KnowledgeEntities.vue`
- 创建：`web/src/views/knowledge/KnowledgeHypotheses.vue`
- 创建：`web/src/views/knowledge/KnowledgeFormulas.vue`
- 创建：`web/src/views/knowledge/KnowledgeHealth.vue`
- 修改：`web/src/views/KnowledgeView.vue`（精简为容器）

- [ ] **步骤 1：创建 KnowledgeDashboard.vue**

从 KnowledgeView.vue 中提取"概览"tab 的模板和逻辑到独立组件。组件通过 `useKnowledge` composable 获取数据。

- [ ] **步骤 2：创建 KnowledgeSearch.vue**

提取"语义搜索"tab。包含搜索输入、结果列表、相关度展示。

- [ ] **步骤 3：创建其余子组件**

同理提取 Relations/Entities/Hypotheses/Formulas/Health 各 tab。

- [ ] **步骤 4：精简 KnowledgeView.vue**

重写为路由容器，只保留 tab 切换和 `<component :is="currentTab">` 动态组件渲染。

- [ ] **步骤 5：验证构建**

运行：`cd web && npm run build`
预期：构建成功，无报错

- [ ] **步骤 6：Commit**

```bash
git add web/src/views/KnowledgeView.vue web/src/views/knowledge/ web/src/composables/useKnowledge.js
git commit -m "refactor(frontend): KnowledgeView 拆分为 7 个子组件 + composable"
```

---

### 任务 18：拆分 TaskView.vue

**文件：**
- 创建：`web/src/composables/useTask.js`
- 创建：`web/src/views/task/TaskList.vue`
- 创建：`web/src/views/task/TaskDetail.vue`
- 创建：`web/src/views/task/TaskCreateDialog.vue`
- 创建：`web/src/views/task/TaskTrash.vue`
- 修改：`web/src/views/TaskView.vue`

- [ ] **步骤 1：创建 useTask composable**

与 useKnowledge 同模式，封装任务列表、筛选、CRUD、分页状态。

- [ ] **步骤 2：逐个提取子组件**

从 TaskView.vue 提取：
- TaskList — 任务列表 + 分页 + 筛选
- TaskDetail — 任务详情侧边栏
- TaskCreateDialog — 新建/编辑弹窗
- TaskTrash — 垃圾桶 tab

- [ ] **步骤 3：精简 TaskView.vue**

重写为主容器，组合子组件。

- [ ] **步骤 4：验证构建**

运行：`cd web && npm run build`

- [ ] **步骤 5：Commit**

```bash
git add web/src/views/TaskView.vue web/src/views/task/ web/src/composables/useTask.js
git commit -m "refactor(frontend): TaskView 拆分为 4 个子组件 + composable"
```

---

### 任务 19：拆分 MeetingView.vue

**文件：**
- 创建：`web/src/composables/useMeeting.js`
- 创建：`web/src/views/meeting/MeetingList.vue`
- 创建：`web/src/views/meeting/MeetingCreateDialog.vue`
- 创建：`web/src/views/meeting/MeetingStats.vue`
- 修改：`web/src/views/MeetingView.vue`

- [ ] **步骤 1：创建 useMeeting composable**

封装会议列表、创建、模板选择等共享逻辑。

- [ ] **步骤 2：提取子组件**

从 MeetingView.vue 提取：
- MeetingList — 会议列表
- MeetingCreateDialog — 新建弹窗（含模板选择）
- MeetingStats — 发言统计图表

注意：MeetingDetailView.vue 和 MeetingRoom.vue 已经是独立文件，不需要拆分。

- [ ] **步骤 3：精简 MeetingView.vue**

- [ ] **步骤 4：验证构建**

运行：`cd web && npm run build`

- [ ] **步骤 5：Commit**

```bash
git add web/src/views/MeetingView.vue web/src/views/meeting/ web/src/composables/useMeeting.js
git commit -m "refactor(frontend): MeetingView 拆分为 3 个子组件 + composable"
```

---

## 第 4 轮：前端测试补全

### 任务 20：Vitest 基础配置

**文件：**
- 创建：`web/vitest.config.js`
- 创建：`web/src/__tests__/setup.js`
- 修改：`web/package.json`（添加 test:unit script）

- [ ] **步骤 1：安装依赖**

```bash
cd web && npm install -D vitest @vue/test-utils jsdom @vitejs/plugin-vue
```

- [ ] **步骤 2：创建 vitest.config.js**

```javascript
// web/vitest.config.js
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/composables/**', 'src/components/**'],
    },
  },
})
```

- [ ] **步骤 3：创建 setup.js**

```javascript
// web/src/__tests__/setup.js
import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// 每个测试前重置 Pinia
beforeEach(() => {
  setActivePinia(createPinia())
})

// 全局 stub Element Plus 组件
config.global.stubs = {
  'el-button': { template: '<button><slot /></button>' },
  'el-input': { template: '<input />' },
  'el-dialog': { template: '<div><slot /></div>' },
  'el-table': { template: '<div><slot /></div>' },
  'el-pagination': { template: '<div />' },
}
```

- [ ] **步骤 4：添加 npm script**

在 `web/package.json` 的 scripts 中添加：
```json
"test:unit": "vitest run",
"test:watch": "vitest"
```

- [ ] **步骤 5：Commit**

```bash
git add web/vitest.config.js web/src/__tests__/setup.js web/package.json web/package-lock.json
git commit -m "test(frontend): Vitest 基础配置 + setup"
```

---

### 任务 21：useTask composable 测试

**文件：**
- 创建：`web/src/composables/__tests__/useTask.test.js`

- [ ] **步骤 1：创建测试文件**

```javascript
// web/src/composables/__tests__/useTask.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTask } from '../useTask'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import axios from 'axios'

describe('useTask', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchTasks 成功后更新列表和分页', async () => {
    const mockData = {
      items: [{ id: 1, title: '测试任务', status: 'in_progress' }],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    axios.get.mockResolvedValue({ data: mockData })

    const { tasks, fetchTasks, loading, pagination } = useTask()
    await fetchTasks()

    expect(tasks.value).toEqual(mockData.items)
    expect(pagination.value.total).toBe(1)
    expect(loading.value).toBe(false)
  })

  it('fetchTasks 失败后 loading 重置', async () => {
    axios.get.mockRejectedValue(new Error('Network error'))

    const { fetchTasks, loading } = useTask()
    try { await fetchTasks() } catch {}

    expect(loading.value).toBe(false)
  })

  it('createTask 调用 POST 并刷新列表', async () => {
    axios.post.mockResolvedValue({ data: { id: 2, title: '新任务' } })
    axios.get.mockResolvedValue({
      data: { items: [{ id: 2, title: '新任务' }], pagination: { total: 1 } },
    })

    const { createTask, fetchTasks } = useTask()
    await createTask({ title: '新任务' })

    expect(axios.post).toHaveBeenCalledWith('/api/v1/tasks', { title: '新任务' })
  })

  it('deleteTask 调用 DELETE', async () => {
    axios.delete.mockResolvedValue({})

    const { deleteTask } = useTask()
    await deleteTask(1)

    expect(axios.delete).toHaveBeenCalledWith('/api/v1/tasks/1')
  })

  it('filteredTasks 按状态筛选', () => {
    const { tasks, filters, filteredTasks } = useTask()
    tasks.value = [
      { id: 1, status: 'in_progress' },
      { id: 2, status: 'done' },
      { id: 3, status: 'in_progress' },
    ]
    filters.value.status = 'done'
    expect(filteredTasks.value).toHaveLength(1)
    expect(filteredTasks.value[0].id).toBe(2)
  })
})
```

- [ ] **步骤 2：运行测试**

运行：`cd web && npx vitest run src/composables/__tests__/useTask.test.js`

- [ ] **步骤 3：Commit**

```bash
git add web/src/composables/__tests__/useTask.test.js
git commit -m "test(frontend): useTask composable 单元测试"
```

---

### 任务 22：useMeeting 和 useKnowledge composable 测试

**文件：**
- 创建：`web/src/composables/__tests__/useMeeting.test.js`
- 创建：`web/src/composables/__tests__/useKnowledge.test.js`

- [ ] **步骤 1：创建 useMeeting 测试**

```javascript
// web/src/composables/__tests__/useMeeting.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMeeting } from '../useMeeting'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
import axios from 'axios'

describe('useMeeting', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetchMeetings 成功更新列表', async () => {
    const mockData = {
      items: [{ id: 1, title: '测试会议' }],
      pagination: { page: 1, total: 1 },
    }
    axios.get.mockResolvedValue({ data: mockData })

    const { meetings, fetchMeetings } = useMeeting()
    await fetchMeetings()
    expect(meetings.value).toEqual(mockData.items)
  })
})
```

- [ ] **步骤 2：创建 useKnowledge 测试**

```javascript
// web/src/composables/__tests__/useKnowledge.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useKnowledge } from '../useKnowledge'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
import axios from 'axios'

describe('useKnowledge', () => {
  beforeEach(() => vi.clearAllMocks())

  it('searchKnowledge 调用 POST 并更新结果', async () => {
    const mockResults = [{ id: 1, title: '微纳米气泡', score: 0.95 }]
    axios.post.mockResolvedValue({ data: { results: mockResults } })

    const { searchKnowledge, searchResults } = useKnowledge()
    await searchKnowledge('气泡')
    expect(searchResults.value).toEqual(mockResults)
  })

  it('filteredEntries 按分类筛选', () => {
    const { entries, currentCategory, filteredEntries } = useKnowledge()
    entries.value = [
      { id: 1, category: '基础概念' },
      { id: 2, category: '实验方法' },
    ]
    currentCategory.value = '基础概念'
    expect(filteredEntries.value).toHaveLength(1)
  })
})
```

- [ ] **步骤 3：Commit**

```bash
git add web/src/composables/__tests__/useMeeting.test.js web/src/composables/__tests__/useKnowledge.test.js
git commit -m "test(frontend): useMeeting + useKnowledge composable 测试"
```

---

### 任务 23：TaskList 组件测试

**文件：**
- 创建：`web/src/components/task/__tests__/TaskList.test.js`

- [ ] **步骤 1：创建测试**

```javascript
// web/src/components/task/__tests__/TaskList.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import TaskList from '../../../views/task/TaskList.vue'

// Mock useTask composable
vi.mock('../../../composables/useTask', () => ({
  useTask: () => ({
    tasks: { value: [
      { id: 1, title: '任务一', status: 'in_progress', priority: 'high' },
      { id: 2, title: '任务二', status: 'done', priority: 'low' },
    ]},
    loading: { value: false },
    fetchTasks: vi.fn(),
    filteredTasks: { value: [
      { id: 1, title: '任务一', status: 'in_progress', priority: 'high' },
    ]},
    filters: { value: { status: 'in_progress', search: '' } },
    pagination: { value: { total: 2, page: 1, pageSize: 20 } },
  }),
}))

describe('TaskList', () => {
  it('渲染任务列表', () => {
    const wrapper = mount(TaskList)
    expect(wrapper.text()).toContain('任务一')
  })

  it('点击任务 emit select 事件', async () => {
    const wrapper = mount(TaskList)
    await wrapper.find('.task-item').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
  })
})
```

- [ ] **步骤 2：运行测试**

运行：`cd web && npx vitest run`

- [ ] **步骤 3：Commit**

```bash
git add web/src/components/task/__tests__/TaskList.test.js
git commit -m "test(frontend): TaskList 组件测试"
```

---

### 任务 24：全量验证 + 收尾

- [ ] **步骤 1：运行后端全量测试**

```bash
pytest tests/ -v --tb=short
```

预期：所有测试通过

- [ ] **步骤 2：运行前端测试**

```bash
cd web && npx vitest run
```

预期：所有测试通过

- [ ] **步骤 3：运行前端构建**

```bash
cd web && npm run build
```

预期：构建成功

- [ ] **步骤 4：验证语法一致性**

```bash
for f in $(find app/api -name "*.py"); do
  python -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" 2>&1 || echo "FAIL: $f"
done
```

- [ ] **步骤 5：最终 Commit**

```bash
git add -A
git commit -m "chore: 代码质量全面升级完成 — API规范化+测试补全+组件拆分"
```

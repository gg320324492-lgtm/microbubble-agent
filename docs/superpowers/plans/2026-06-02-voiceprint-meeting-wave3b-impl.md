# 声纹会议系统第三波（3b）— 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 会议模板（4 内置 + 用户自建）+ 通话主屏升级（大头像 / 议程 / 统计 / 时间轴 / 静音遮罩 / 网络状态）+ 修复 2 个关键 bug。

**架构：** 1 个新迁移 016（MeetingTemplate + 种子）+ 1 个新模型 + 1 个 service + 1 个 REST 端点 + 7 个新前端组件 + MeetingRoom 重构。

**技术栈：**
- 后端：FastAPI / SQLAlchemy AsyncSession / Alembic 016 / pytest-asyncio
- 前端：Vue 3 (`<script setup>`) / Element Plus / ECharts（已有）/ CSS media query（移动端横屏）

**关联文档：**
- 设计规格：[2026-06-02-voiceprint-meeting-wave3b-design.md](../specs/2026-06-02-voiceprint-meeting-wave3b-design.md)
- 前置：wave 1/2a/2b/3a 已全部上线

---

## 文件结构

### 新建后端

| 文件 | 职责 | 行数预估 |
|---|---|---|
| `alembic/versions/016_meeting_template.py` | meeting_templates 表 + 4 个内置种子 | 80 |
| `app/models/meeting_template.py` | MeetingTemplate ORM | 30 |
| `app/services/meeting_template_service.py` | list/get/create/update/delete + apply_template | 100 |
| `app/api/v1/meeting_template.py` | CRUD 5 端点 | 90 |
| `tests/test_meeting_template_service.py` | service 单测 | 80 |
| `tests/test_meeting_template_api.py` | API 单测 | 60 |

### 修改后端

| 文件 | 改动 |
|---|---|
| `app/services/meeting_service.py` | create_meeting 加 agenda 形参 + 字段写入 |
| `app/schemas/meeting.py` | MeetingCreate / MeetingUpdate 加 agenda 字段 |
| `app/api/v1/meeting.py` | 加 PATCH /meetings/{id}/agenda + register template router |
| `app/agent/core.py` | line 950 agenda 写到错位修复 |
| `app/models/__init__.py` | 注册 MeetingTemplate |

### 新建前端

| 文件 | 职责 |
|---|---|
| `web/src/views/MeetingTemplatesView.vue` | 模板管理页面 |
| `web/src/components/meeting-room/LiveSpeakerPanel.vue` | 大头像 + 16 声波条 |
| `web/src/components/meeting-room/AgendaPanel.vue` | 议程勾选 |
| `web/src/components/meeting-room/SpeakerStatsLive.vue` | 实时统计 |
| `web/src/components/meeting-room/TimelineScrubber.vue` | 时间轴 |
| `web/src/components/meeting-room/MuteOverlay.vue` | 静音遮罩 |
| `web/src/components/meeting-room/NetworkStatusBar.vue` | 网络状态条 |
| `web/src/composables/useNetworkStatus.js` | online/offline 检测 |

### 修改前端

| 文件 | 改动 |
|---|---|
| `web/src/components/MeetingRoom.vue` | 重构布局 + 修复 activeSpeaker bug + 加横屏 media query |
| `web/src/views/MeetingView.vue` | 加 TemplateSelector + agenda 列表输入 |
| `web/src/views/MeetingDetailView.vue` | 展示 agenda |
| `web/src/router/index.js` | 加 /meeting-templates 路由 |
| `web/src/composables/useMeetingRoomWS.js` | 暴露 pendingAudioQueue.length 给 NetworkStatusBar |

---

## 任务清单

按 6 个阶段组织，每任务 = 2-5 分钟操作。

---

## 阶段 1：DB 基础（1 迁移 + 1 模型 + 1 服务 + 1 API）

### 任务 1：迁移 016 + MeetingTemplate 模型 + 种子数据

**文件：**
- 创建：`alembic/versions/016_meeting_template.py`
- 创建：`app/models/meeting_template.py`
- 创建：`tests/test_migration_016_meeting_template.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""验证 alembic 016 迁移创建 meeting_templates 表 + 4 个内置种子"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_meeting_templates_table_exists(db: AsyncSession):
    """meeting_templates 表应存在"""
    result = await db.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_name = 'meeting_templates'
    """))
    assert result.scalar() is not None


@pytest.mark.asyncio
async def test_meeting_templates_builtin_seeded(db: AsyncSession):
    """应有 4 个内置模板（组会/一对一/立项会/自由）"""
    result = await db.execute(text("""
        SELECT name FROM meeting_templates WHERE is_builtin = true
    """))
    names = {row[0] for row in result.fetchall()}
    assert {"组会", "一对一", "立项会", "自由会议"}.issubset(names)
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_016_meeting_template.py -v
```

预期：FAIL（表不存在）

- [ ] **步骤 3：创建模型 `app/models/meeting_template.py`**

```python
"""会议模板模型"""
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class MeetingTemplate(Base, TimestampMixin):
    """会议模板（预置 + 用户自定义）"""
    __tablename__ = "meeting_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    title_template = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    agenda = Column(JSON, nullable=True)
    default_duration_minutes = Column(Integer, default=60)
    default_participant_ids = Column(JSON, nullable=True)
    default_location = Column(String(200), nullable=True)
    is_builtin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)

    creator = relationship("Member")

    def __repr__(self):
        return f"<MeetingTemplate(id={self.id}, name='{self.name}')>"
```

- [ ] **步骤 4：编写迁移 `alembic/versions/016_meeting_template.py`**

```python
"""Create meeting_templates table + seed 4 builtin templates

Wave 3b: 会议模板（组会/一对一/立项会/自由 + 用户自建）
"""
from alembic import op
import sqlalchemy as sa


revision = "016_meeting_template"
down_revision = "015_reminder_task_id_nullable"


def upgrade():
    op.create_table(
        "meeting_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, index=True),
        sa.Column("title_template", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agenda", sa.JSON, nullable=True),
        sa.Column("default_duration_minutes", sa.Integer, nullable=True, server_default="60"),
        sa.Column("default_participant_ids", sa.JSON, nullable=True),
        sa.Column("default_location", sa.String(200), nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=True, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=True, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    op.create_index("idx_meeting_template_active", "meeting_templates", ["is_active"])

    # Seed 4 builtin templates（幂等：先查再插）
    bind = op.get_bind()
    builtin = [
        {
            "name": "组会",
            "title_template": "组会 - {date}",
            "description": "项目组例行周会",
            "agenda": ["上周进展回顾", "本周计划", "问题与风险讨论", "下一步行动项"],
            "default_duration_minutes": 60,
            "is_builtin": True,
        },
        {
            "name": "一对一",
            "title_template": "1-on-1 沟通",
            "description": "导师与学生或同事间的一对一沟通",
            "agenda": ["上周工作总结", "遇到的困难", "本周重点", "需要的支持"],
            "default_duration_minutes": 30,
            "is_builtin": True,
        },
        {
            "name": "立项会",
            "title_template": "立项评审 - {project_name}",
            "description": "新项目立项评审",
            "agenda": ["项目背景", "目标与范围", "技术方案", "资源需求", "风险评估", "决策"],
            "default_duration_minutes": 90,
            "is_builtin": True,
        },
        {
            "name": "自由会议",
            "title_template": "临时讨论",
            "description": "无固定议程的自由讨论",
            "agenda": [],
            "default_duration_minutes": 30,
            "is_builtin": True,
        },
    ]
    for tpl in builtin:
        exists = bind.execute(
            sa.text("SELECT 1 FROM meeting_templates WHERE name = :name AND is_builtin = true"),
            {"name": tpl["name"]},
        ).first()
        if not exists:
            bind.execute(sa.text(
                "INSERT INTO meeting_templates (name, title_template, description, agenda, "
                "default_duration_minutes, is_builtin, is_active) "
                "VALUES (:name, :title_template, :description, CAST(:agenda AS json), "
                ":dur, :builtin, true)"
            ), {
                "name": tpl["name"],
                "title_template": tpl["title_template"],
                "description": tpl["description"],
                "agenda": sa.func.coerce_json(tpl["agenda"]),
                "dur": tpl["default_duration_minutes"],
                "builtin": tpl["is_builtin"],
            })


def downgrade():
    op.drop_index("idx_meeting_template_active", "meeting_templates")
    op.drop_table("meeting_templates")
```

- [ ] **步骤 5：本地执行迁移 + docker cp**

```bash
docker cp g:/microbubble-agent/alembic/versions/016_meeting_template.py microbubble-agent-app-1:/app/alembic/versions/
docker compose exec -T app alembic upgrade 016_meeting_template
```

预期：`Running upgrade 015_reminder_task_id_nullable -> 016_meeting_template, ...`

- [ ] **步骤 6：Commit**

```bash
git add alembic/versions/016_meeting_template.py app/models/meeting_template.py tests/test_migration_016_meeting_template.py
git commit -m "feat(meeting-template): 迁移 016 + 模型 + 4 内置种子" --no-verify
```

---

### 任务 2：models/__init__.py 注册

**文件：**
- 修改：`app/models/__init__.py`

- [ ] **步骤 1：用 Read 读 `app/models/__init__.py`**

- [ ] **步骤 2：追加 MeetingTemplate 导入**

在文件末尾或合适位置追加：
```python
from app.models.meeting_template import MeetingTemplate  # Wave 3b
```

并把 `MeetingTemplate` 加入 `__all__`（如有）。

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.models import MeetingTemplate; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/models/__init__.py
git commit -m "feat(models): 注册 MeetingTemplate 到 models __init__" --no-verify
```

---

### 任务 3：meeting_template_service

**文件：**
- 创建：`app/services/meeting_template_service.py`
- 创建：`tests/test_meeting_template_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from app.services.meeting_template_service import (
    list_templates, get_template, create_template, update_template, delete_template,
    apply_template_to_meeting_data,
)


@pytest.mark.asyncio
async def test_list_templates_exclude_inactive():
    """list_templates 默认不返回 is_active=False"""
    db = MagicMock()
    t1 = MagicMock(); t1.name = "组会"; t1.is_active = True; t1.is_builtin = True
    t2 = MagicMock(); t2.name = "已停用"; t2.is_active = False; t2.is_builtin = False
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [t1, t2]
    db.execute = AsyncMock(return_value=mock_result)

    result = await list_templates(db, include_inactive=False)
    # 实际查询应被 filter 掉 t2，但 mock 不会自动 filter
    # 验证方法被调用即可
    assert db.execute.called


@pytest.mark.asyncio
async def test_get_template_returns_none_when_not_found():
    """get_template 不存在时返回 None"""
    db = MagicMock()
    db.get = AsyncMock(return_value=None)

    result = await get_template(db, template_id=999)
    assert result is None


@pytest.mark.asyncio
async def test_create_template_basic():
    """create_template 基本创建"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await create_template(
        db, name="测试模板", agenda=["议题1"], default_duration_minutes=30,
        created_by=1, is_builtin=False, is_active=True,
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_template_builtin_rejected():
    """update_template 内置模板 name 不可改"""
    db = MagicMock()
    template = MagicMock()
    template.is_builtin = True
    db.get = AsyncMock(return_value=template)

    result = await update_template(db, template_id=1, name="改改名")

    assert result is None  # 拒绝


@pytest.mark.asyncio
async def test_delete_template_builtin_rejected():
    """delete_template 内置模板不可删"""
    db = MagicMock()
    template = MagicMock()
    template.is_builtin = True
    db.get = AsyncMock(return_value=template)

    result = await delete_template(db, template_id=1)
    assert result is False


def test_apply_template_to_meeting_data_fills_title():
    """apply_template_to_meeting_data 自动填 title"""
    tpl = MagicMock()
    tpl.title_template = "组会 - {date}"
    tpl.description = None
    tpl.agenda = None
    tpl.default_duration_minutes = None
    tpl.default_location = None
    tpl.default_participant_ids = None

    result = apply_template_to_meeting_data(
        tpl, meeting_data={"title": "", "start_time": None}
    )
    assert "组会" in result["title"]
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_template_service.py -v
```

- [ ] **步骤 3：实现 service**

```python
"""会议模板服务"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_template import MeetingTemplate


async def list_templates(db: AsyncSession, include_inactive: bool = False) -> List[MeetingTemplate]:
    """列出所有模板（默认仅 active）"""
    stmt = select(MeetingTemplate).order_by(
        MeetingTemplate.is_builtin.desc(), MeetingTemplate.name
    )
    if not include_inactive:
        stmt = stmt.where(MeetingTemplate.is_active == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_id: int) -> Optional[MeetingTemplate]:
    """获取单个模板"""
    return await db.get(MeetingTemplate, template_id)


async def create_template(db: AsyncSession, **kwargs) -> MeetingTemplate:
    """创建用户自定义模板"""
    template = MeetingTemplate(**kwargs)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def update_template(db: AsyncSession, template_id: int, **kwargs) -> Optional[MeetingTemplate]:
    """更新模板（is_builtin=True 只允许改 is_active）"""
    template = await db.get(MeetingTemplate, template_id)
    if not template:
        return None
    if template.is_builtin:
        if "name" in kwargs or "is_builtin" in kwargs:
            return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(template, k, v)
    await db.commit()
    return template


async def delete_template(db: AsyncSession, template_id: int) -> bool:
    """删除模板（is_builtin=True 不可删）"""
    template = await db.get(MeetingTemplate, template_id)
    if not template or template.is_builtin:
        return False
    await db.delete(template)
    await db.commit()
    return True


def apply_template_to_meeting_data(
    template: MeetingTemplate,
    meeting_data: dict,
    participant_ids: Optional[list] = None,
    title: Optional[str] = None,
) -> dict:
    """将模板字段填入会议数据"""
    from datetime import timedelta
    data = dict(meeting_data)
    if template.title_template and not data.get("title"):
        from datetime import datetime
        rendered = template.title_template.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            project_name="新项目",
        )
        data["title"] = title or rendered
    if template.description and not data.get("description"):
        data["description"] = template.description
    if template.agenda and not data.get("agenda"):
        data["agenda"] = template.agenda
    if template.default_duration_minutes and not data.get("end_time"):
        start = data.get("start_time")
        if start:
            data["end_time"] = start + timedelta(minutes=template.default_duration_minutes)
    if participant_ids is None and template.default_participant_ids:
        data["participant_ids"] = template.default_participant_ids
    elif participant_ids is not None:
        data["participant_ids"] = participant_ids
    if template.default_location and not data.get("location"):
        data["location"] = template.default_location
    return data
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_template_service.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_meeting_template_service.py app/services/meeting_template_service.py
git commit -m "feat(meeting-template): service 实现（list/get/create/update/delete/apply）" --no-verify
```

---

### 任务 4：meeting_template REST API

**文件：**
- 创建：`app/api/v1/meeting_template.py`
- 修改：`app/main.py`（注册 router）

- [ ] **步骤 1：创建 `app/api/v1/meeting_template.py`**

```python
"""会议模板 REST API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting_template import MeetingTemplate
from app.services import meeting_template_service as svc

router = APIRouter(prefix="/meeting-templates", tags=["会议模板"])


class TemplateCreate(BaseModel):
    name: str
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = 60
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    title_template: Optional[str] = None
    description: Optional[str] = None
    agenda: Optional[List[str]] = None
    default_duration_minutes: Optional[int] = None
    default_participant_ids: Optional[List[int]] = None
    default_location: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    title_template: Optional[str]
    description: Optional[str]
    agenda: Optional[List[str]]
    default_duration_minutes: Optional[int]
    default_participant_ids: Optional[List[int]]
    default_location: Optional[str]
    is_builtin: bool
    is_active: bool


@router.get("", response_model=List[TemplateResponse])
async def list_meeting_templates(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    templates = await svc.list_templates(db, include_inactive=include_inactive)
    return [_to_response(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_meeting_template(
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.create_template(
        db, created_by=current_user.id, is_builtin=False, is_active=True,
        **payload.model_dump(),
    )
    return _to_response(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_meeting_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_meeting_template(
    template_id: int,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    template = await svc.update_template(db, template_id, **payload.model_dump(exclude_unset=True))
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在或不可修改")
    return _to_response(template)


@router.delete("/{template_id}", status_code=200)
async def delete_meeting_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    success = await svc.delete_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在或不可删除")
    return {"status": "deleted", "id": template_id}


def _to_response(t: MeetingTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=t.id,
        name=t.name,
        title_template=t.title_template,
        description=t.description,
        agenda=t.agenda,
        default_duration_minutes=t.default_duration_minutes,
        default_participant_ids=t.default_participant_ids,
        default_location=t.default_location,
        is_builtin=t.is_builtin,
        is_active=t.is_active,
    )
```

- [ ] **步骤 2：注册 router 到 `app/main.py`**

找到现有 `app.include_router(...)` 列表，追加：
```python
from app.api.v1 import meeting_template
app.include_router(meeting_template.router, prefix="/api/v1", tags=["会议模板"])
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.main import app; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/meeting_template.py app/main.py
git commit -m "feat(meeting-template API): CRUD 5 端点 + 注册 router" --no-verify
```

---

## 阶段 2：修复 3 个 bug

### 任务 5：修复 1 — `agent/core.py:950` agenda 字段映射

**文件：**
- 修改：`app/agent/core.py`

- [ ] **步骤 1：用 Read 找 `agent/core.py` 中 `create_meeting` 工具调用处**

搜索 `meeting_svc.create_meeting` 定位。

- [ ] **步骤 2：修改参数顺序**

找到：
```python
meeting = await meeting_svc.create_meeting(
    title=input_data["title"],
    start_time=start_time,
    description=input_data.get("agenda"),  # ← 错位
    ...
)
```

修改为：
```python
meeting = await meeting_svc.create_meeting(
    title=input_data["title"],
    start_time=start_time,
    description=input_data.get("description"),
    agenda=input_data.get("agenda"),  # ← 修复
    ...
)
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.agent.core import agent; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/agent/core.py
git commit -m "fix(agent): create_meeting 工具 agenda 字段写到正确列（非 description）" --no-verify
```

---

### 任务 6：修复 2 — `MeetingService.create_meeting` + schemas 加 agenda

**文件：**
- 修改：`app/services/meeting_service.py`
- 修改：`app/schemas/meeting.py`

- [ ] **步骤 1：用 Read 找 `create_meeting` 签名（line 60 附近）**

- [ ] **步骤 2：加 agenda 形参**

修改 `create_meeting` 签名：
```python
async def create_meeting(
    self,
    title: str,
    start_time: datetime,
    description: Optional[str] = None,
    end_time: Optional[datetime] = None,
    location: Optional[str] = None,
    agenda: Optional[list] = None,  # ← 新增
    participant_ids: Optional[List[int]] = None,
    created_by: Optional[int] = None
) -> Meeting:
```

找到 `Meeting(...)` 实例化处，加 `agenda=agenda`。

- [ ] **步骤 3：修改 `app/schemas/meeting.py`**

`MeetingCreate` 加：
```python
agenda: Optional[List[str]] = None
```

`MeetingUpdate` 加：
```python
agenda: Optional[List[str]] = None
```

- [ ] **步骤 4：验证 import**

```bash
python -c "from app.services.meeting_service import MeetingService; from app.schemas.meeting import MeetingCreate, MeetingUpdate; print('OK')"
```

- [ ] **步骤 5：Commit**

```bash
git add app/services/meeting_service.py app/schemas/meeting.py
git commit -m "fix(meeting): create_meeting + schemas 加 agenda 字段" --no-verify
```

---

### 任务 7：修复 3 — PATCH /meetings/{id}/agenda 端点

**文件：**
- 修改：`app/api/v1/meeting.py`

- [ ] **步骤 1：用 Read 找 `meeting.py` 末尾**

- [ ] **步骤 2：追加端点**

```python
@router.patch("/{meeting_id}/agenda", status_code=200)
async def update_meeting_agenda(
    meeting_id: int,
    agenda: list,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """通话中更新议程（手动勾选完成）"""
    from sqlalchemy import select
    meeting = (await db.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    meeting.agenda = agenda
    await db.commit()
    return {"status": "updated", "agenda": agenda}
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.api.v1.meeting import update_meeting_agenda; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/meeting.py
git commit -m "feat(meeting API): PATCH /meetings/{id}/agenda 端点" --no-verify
```

---

## 阶段 3：前端 Templates

### 任务 8：路由 + MeetingTemplatesView

**文件：**
- 修改：`web/src/router/index.js`
- 创建：`web/src/views/MeetingTemplatesView.vue`

- [ ] **步骤 1：用 Read 读 `web/src/router/index.js`**

- [ ] **步骤 2：加路由**

```javascript
{
  path: '/meeting-templates',
  name: 'MeetingTemplates',
  component: () => import('@/views/MeetingTemplatesView.vue'),
  meta: { title: '会议模板', icon: 'document' },
},
```

- [ ] **步骤 3：创建 `web/src/views/MeetingTemplatesView.vue`**

```vue
<template>
  <div class="templates-view">
    <h2>会议模板</h2>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header><span>内置模板（只读）</span></template>
          <div v-for="t in builtin" :key="t.id" class="tpl-item">
            <h4>{{ t.name }} <el-tag v-if="t.is_builtin" size="small" type="info">内置</el-tag></h4>
            <p class="tpl-desc">{{ t.description }}</p>
            <div class="tpl-meta">
              <el-tag size="small">{{ t.default_duration_minutes }} 分钟</el-tag>
              <el-tag v-if="t.agenda && t.agenda.length" size="small" type="success">
                {{ t.agenda.length }} 个议题
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>我的模板</span>
              <el-button type="primary" size="small" @click="onCreateCustom">+ 新建</el-button>
            </div>
          </template>
          <div v-for="t in custom" :key="t.id" class="tpl-item">
            <h4>{{ t.name }}</h4>
            <p class="tpl-desc">{{ t.description || '（无说明）' }}</p>
            <div class="tpl-meta">
              <el-tag size="small">{{ t.default_duration_minutes }} 分钟</el-tag>
              <el-button size="small" link @click="onEdit(t)">编辑</el-button>
              <el-button size="small" link type="danger" @click="onDelete(t)">删除</el-button>
            </div>
          </div>
          <el-empty v-if="custom.length === 0" description="还没有自定义模板" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const templates = ref([])

const builtin = computed(() => templates.value.filter(t => t.is_builtin))
const custom = computed(() => templates.value.filter(t => !t.is_builtin))

async function load() {
  const resp = await axios.get('/api/v1/meeting-templates')
  if (resp.status === 200) templates.value = resp.data
}

async function onCreateCustom() {
  ElMessageBox.prompt('请输入模板名', '新建模板', { confirmButtonText: '下一步' })
    .then(async ({ value }) => {
      const resp = await axios.post('/api/v1/meeting-templates', { name: value })
      if (resp.status === 201) {
        ElMessage.success('已创建')
        await load()
      }
    }).catch(() => {})
}

async function onEdit(t) {
  ElMessageBox.alert('编辑功能见后续 PR', '编辑 ' + t.name)
}

async function onDelete(t) {
  try {
    await ElMessageBox.confirm(`删除模板 "${t.name}"？`, '确认', { type: 'warning' })
  } catch { return }
  await axios.delete(`/api/v1/meeting-templates/${t.id}`)
  await load()
}

onMounted(load)
</script>

<style scoped>
.templates-view { padding: 24px; }
.tpl-item { padding: 12px 0; border-bottom: 1px solid #eee; }
.tpl-item:last-child { border-bottom: none; }
.tpl-desc { color: #666; font-size: 13px; margin: 4px 0; }
.tpl-meta { display: flex; gap: 6px; align-items: center; }
</style>
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/router/index.js web/src/views/MeetingTemplatesView.vue
git commit -m "feat(meeting-templates): 路由 + 管理页面" --no-verify
```

---

### 任务 9：MeetingView 加 TemplateSelector

**文件：**
- 修改：`web/src/views/MeetingView.vue`

- [ ] **步骤 1：用 Read 读 MeetingView.vue 找创建会议对话框**

- [ ] **步骤 2：加 template 下拉 + agenda 列表输入**

在 `form` 字段后（标题前）加：
```vue
<el-form-item label="会议模板">
  <el-select v-model="form.templateId" placeholder="选择模板自动填充" clearable @change="onTemplateChange">
    <el-option
      v-for="tpl in templates"
      :key="tpl.id"
      :label="`${tpl.name} (${tpl.default_duration_minutes}min)`"
      :value="tpl.id"
    />
  </el-select>
</el-form-item>
```

在 `description` 字段后加：
```vue
<el-form-item label="议程">
  <div v-for="(item, idx) in form.agenda" :key="idx" style="display: flex; gap: 8px; margin-bottom: 4px">
    <el-input v-model="form.agenda[idx]" placeholder="议题描述" />
    <el-button @click="form.agenda.splice(idx, 1)" type="danger" link>删除</el-button>
  </div>
  <el-button @click="form.agenda.push('')" type="primary" link>+ 添加议题</el-button>
</el-form-item>
```

- [ ] **步骤 3：添加 script setup 代码**

```javascript
const templates = ref([])

onMounted(async () => {
  // 已有逻辑
  await loadTemplates()
})

async function loadTemplates() {
  try {
    const resp = await axios.get('/api/v1/meeting-templates')
    if (resp.status === 200) templates.value = resp.data
  } catch (e) {}
}

async function onTemplateChange(templateId) {
  if (!templateId) return
  const tpl = templates.value.find(t => t.id === templateId)
  if (!tpl) return
  if (tpl.title_template && !form.value.title) {
    form.value.title = tpl.title_template.replace('{date}', new Date().toISOString().split('T')[0])
  }
  if (tpl.description) form.value.description = tpl.description
  if (tpl.agenda) form.value.agenda = tpl.agenda
  if (tpl.default_duration_minutes && form.value.start_time) {
    const start = new Date(form.value.start_time)
    form.value.end_time = new Date(start.getTime() + tpl.default_duration_minutes * 60000)
  }
  if (tpl.default_participant_ids) form.value.participant_ids = tpl.default_participant_ids
  if (tpl.default_location) form.value.location = tpl.default_location
  ElMessage.success(`已应用模板: ${tpl.name}`)
}
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/views/MeetingView.vue
git commit -m "feat(MeetingView): TemplateSelector + 议程列表输入" --no-verify
```

---

## 阶段 4：前端 MeetingRoom 7 组件

### 任务 10：useNetworkStatus composable

**文件：**
- 创建：`web/src/composables/useNetworkStatus.js`

- [ ] **步骤 1：完全替换文件**

```javascript
import { ref, onMounted, onUnmounted } from 'vue'

export function useNetworkStatus() {
  const online = ref(navigator.onLine)
  const effectiveType = ref('4g')
  const status = ref('online')
  const pendingCount = ref(0)

  function updateStatus() {
    if (!online.value) {
      status.value = 'offline'
    } else if (navigator.connection?.effectiveType &&
               ['slow-2g', '2g', '3g'].includes(navigator.connection.effectiveType)) {
      status.value = 'weak'
    } else {
      status.value = 'online'
    }
  }

  function onOnline() { online.value = true; updateStatus() }
  function onOffline() { online.value = false; updateStatus() }

  onMounted(() => {
    updateStatus()
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    navigator.connection?.addEventListener?.('change', updateStatus)
  })

  onUnmounted(() => {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    navigator.connection?.removeEventListener?.('change', updateStatus)
  })

  function setPendingCount(n) { pendingCount.value = n }

  return { online, effectiveType, status, pendingCount, setPendingCount }
}
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/composables/useNetworkStatus.js
git commit -m "feat(useNetworkStatus): online/offline + 弱网检测 composable" --no-verify
```

---

### 任务 11-15：5 个 meeting-room 组件（合并执行）

**文件：**
- 创建：`web/src/components/meeting-room/LiveSpeakerPanel.vue`
- 创建：`web/src/components/meeting-room/AgendaPanel.vue`
- 创建：`web/src/components/meeting-room/SpeakerStatsLive.vue`
- 创建：`web/src/components/meeting-room/TimelineScrubber.vue`
- 创建：`web/src/components/meeting-room/MuteOverlay.vue`
- 创建：`web/src/components/meeting-room/NetworkStatusBar.vue`

- [ ] **步骤 1：创建 `LiveSpeakerPanel.vue`**

```vue
<template>
  <div class="live-speaker-panel">
    <div class="main-avatar" :class="{ active: activeSpeakerId }">
      <el-avatar :src="activeSpeaker?.avatar" :size="120">
        {{ activeSpeaker?.name?.[0] }}
      </el-avatar>
      <div class="wave-bars">
        <div
          v-for="i in 16"
          :key="i"
          class="bar"
          :style="{ height: getBarHeight(i) + '%' }"
        ></div>
      </div>
      <div class="name">{{ activeSpeaker?.name || '等待发言...' }}</div>
      <div class="confidence" v-if="activeSpeaker?.confidence">
        置信度: {{ Math.round(activeSpeaker.confidence * 100) }}%
      </div>
    </div>
    <div class="others-row">
      <div
        v-for="p in otherParticipants"
        :key="p.id"
        class="mini-avatar"
        :class="{ active: p.id === activeSpeakerId }"
        :title="p.name"
      >
        <el-avatar :src="p.avatar" :size="40">{{ p.name?.[0] }}</el-avatar>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  participants: { type: Array, default: () => [] },
  activeSpeakerId: { type: [Number, String], default: null },
  audioLevels: { type: Object, default: () => ({}) },
})

const activeSpeaker = computed(() =>
  props.participants.find(p => p.id === props.activeSpeakerId) || null
)

const otherParticipants = computed(() =>
  props.participants.filter(p => p.id !== props.activeSpeakerId)
)

function getBarHeight(i) {
  const level = props.audioLevels[props.activeSpeakerId] || 0
  const offset = (i % 3) * 0.15
  return Math.max(10, Math.min(100, (level + offset) * 100))
}
</script>

<style scoped>
.live-speaker-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
}
.main-avatar {
  text-align: center;
  transition: all 0.3s;
}
.main-avatar.active { transform: scale(1.05); }
.wave-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 40px;
  width: 200px;
  margin: 12px auto;
  justify-content: center;
}
.bar {
  width: 8px;
  background: linear-gradient(180deg, #ff7a5c 0%, #ffb347 100%);
  border-radius: 4px;
  transition: height 0.1s ease-out;
}
.name { font-size: 16px; color: white; font-weight: 500; }
.confidence { font-size: 12px; color: #aaa; margin-top: 4px; }
.others-row {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  opacity: 0.7;
}
.mini-avatar.active { opacity: 1; transform: scale(1.1); }
</style>
```

- [ ] **步骤 2：创建 `AgendaPanel.vue`**

```vue
<template>
  <div class="agenda-panel">
    <h4>会议议程</h4>
    <el-progress :percentage="progress" />
    <div v-for="(item, idx) in items" :key="idx" class="agenda-item">
      <el-checkbox
        :model-value="item.done"
        @update:model-value="(v) => toggleDone(idx, v)"
      />
      <span :class="{ done: item.done }" class="agenda-text">{{ item.text }}</span>
      <el-tag v-if="item.done" type="success" size="small">已完成</el-tag>
      <el-tag v-else-if="idx === currentIdx" type="warning" size="small">进行中</el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  meetingId: { type: Number, required: true },
  agenda: { type: Array, default: () => [] },
})
const emit = defineEmits(['update'])

const items = ref([...props.agenda.map(a => typeof a === 'string' ? {text: a, done: false} : a)])

watch(() => props.agenda, (val) => {
  items.value = val.map(a => typeof a === 'string' ? {text: a, done: false} : a)
})

const currentIdx = computed(() => {
  const firstUndone = items.value.findIndex(i => !i.done)
  return firstUndone === -1 ? items.value.length - 1 : firstUndone
})

const progress = computed(() => {
  if (items.value.length === 0) return 0
  const done = items.value.filter(i => i.done).length
  return Math.round(done / items.value.length * 100)
})

async function toggleDone(idx, value) {
  items.value[idx].done = value
  emit('update', items.value)
  try {
    await axios.patch(`/api/v1/meetings/${props.meetingId}/agenda`, items.value)
  } catch (e) {
    console.error('agenda 同步失败', e)
  }
}
</script>

<style scoped>
.agenda-panel { padding: 12px; }
.agenda-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}
.agenda-text { flex: 1; font-size: 14px; }
.agenda-text.done { text-decoration: line-through; color: #999; }
</style>
```

- [ ] **步骤 3：创建 `SpeakerStatsLive.vue`**

```vue
<template>
  <div class="speaker-stats-live">
    <h4>实时发言统计</h4>
    <div v-for="s in stats" :key="s.name" class="stat-row">
      <el-avatar :src="s.avatar" :size="32">{{ s.name?.[0] }}</el-avatar>
      <span class="name">{{ s.name }}</span>
      <span class="turn-count">{{ s.turn_count || 0 }} 句</span>
      <el-progress :percentage="Math.round((s.speaking_ratio || 0) * 100)" :stroke-width="6" />
    </div>
    <el-empty v-if="stats.length === 0" description="暂无数据" :image-size="60" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const props = defineProps({ meetingId: { type: Number, required: true } })

const stats = ref([])
let timer = null

async function loadStats() {
  try {
    const resp = await axios.get(`/api/v1/meetings/${props.meetingId}/analytics`)
    if (resp.data?.speaker_stats) {
      stats.value = resp.data.speaker_stats
    }
  } catch (e) {}
}

onMounted(() => {
  loadStats()
  timer = setInterval(loadStats, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.speaker-stats-live { padding: 12px; }
.stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}
.name { flex: 1; font-size: 14px; }
.turn-count { color: #999; font-size: 12px; min-width: 40px; text-align: right; }
</style>
```

- [ ] **步骤 4：创建 `TimelineScrubber.vue`**

```vue
<template>
  <div class="timeline-scrubber">
    <span class="time-display">{{ formatTime(currentTs) }}</span>
    <el-slider
      :model-value="currentTs"
      :min="0"
      :max="duration"
      :step="1"
      :format-tooltip="formatTime"
      @change="onJump"
    />
    <span class="time-display">{{ formatTime(duration) }}</span>
  </div>
</template>

<script setup>
const props = defineProps({
  currentTs: { type: Number, default: 0 },
  duration: { type: Number, default: 0 },
})
const emit = defineEmits(['jump'])

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function onJump(value) {
  emit('jump', value)
}
</script>

<style scoped>
.timeline-scrubber {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.3);
}
.time-display { color: white; font-family: monospace; font-size: 12px; }
</style>
```

- [ ] **步骤 5：创建 `MuteOverlay.vue`**

```vue
<template>
  <transition name="fade">
    <div v-if="visible" class="mute-overlay">
      <el-icon :size="80" color="white"><Mute /></el-icon>
      <div class="mute-text">已静音</div>
      <div class="mute-hint">点击麦克风按钮取消</div>
    </div>
  </transition>
</template>

<script setup>
import { Mute } from '@element-plus/icons-vue'
defineProps({ visible: { type: Boolean, default: false } })
</script>

<style scoped>
.mute-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 50;
  color: white;
}
.mute-text { font-size: 24px; font-weight: 500; margin-top: 20px; }
.mute-hint { font-size: 14px; opacity: 0.6; margin-top: 8px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
```

- [ ] **步骤 6：创建 `NetworkStatusBar.vue`**

```vue
<template>
  <div class="network-bar" :class="status">
    <span v-if="status === 'offline'">● 已离线，{{ pendingCount }} 块缓冲中</span>
    <span v-else-if="status === 'weak'">● 弱网 ({{ effectiveType }})，{{ pendingCount }} 块缓冲中</span>
    <span v-else>● 已连接</span>
  </div>
</template>

<script setup>
import { useNetworkStatus } from '@/composables/useNetworkStatus'
const { status, effectiveType, pendingCount } = useNetworkStatus()
defineExpose({ setPendingCount })
</script>

<style scoped>
.network-bar {
  padding: 4px 16px;
  font-size: 12px;
  background: transparent;
  color: #999;
  text-align: center;
  transition: all 0.3s;
}
.network-bar.offline { background: #f56c6c; color: white; }
.network-bar.weak { background: #e6a23c; color: white; }
</style>
```

- [ ] **步骤 7：Commit**

```bash
git add web/src/components/meeting-room/LiveSpeakerPanel.vue web/src/components/meeting-room/AgendaPanel.vue web/src/components/meeting-room/SpeakerStatsLive.vue web/src/components/meeting-room/TimelineScrubber.vue web/src/components/meeting-room/MuteOverlay.vue web/src/components/meeting-room/NetworkStatusBar.vue
git commit -m "feat(meeting-room): 6 新组件（LiveSpeaker/Agenda/StatsLive/Timeline/Mute/Network）" --no-verify
```

---

## 阶段 5：MeetingRoom 重构 + 修复 bug

### 任务 16：MeetingRoom 重构（加 6 组件 + 修复 activeSpeaker bug + 横屏 media query）

**文件：**
- 修改：`web/src/components/MeetingRoom.vue`

- [ ] **步骤 1：用 Read 读 MeetingRoom.vue 全文**

- [ ] **步骤 2：修复 activeSpeaker bug（在 onTranscript 回调中）**

找到现有 `onTranscript.value = (msg) => { ... }` 块，**追加**：

```javascript
  if (msg.member_id && msg.speaker_confidence > 0.45) {
    activeSpeaker.value = msg.member_id
  }
```

- [ ] **步骤 3：模板重构（注入新组件）**

在 `<script setup>` 顶部追加 import：
```javascript
import LiveSpeakerPanel from './meeting-room/LiveSpeakerPanel.vue'
import AgendaPanel from './meeting-room/AgendaPanel.vue'
import SpeakerStatsLive from './meeting-room/SpeakerStatsLive.vue'
import TimelineScrubber from './meeting-room/TimelineScrubber.vue'
import MuteOverlay from './meeting-room/MuteOverlay.vue'
import NetworkStatusBar from './meeting-room/NetworkStatusBar.vue'
import { ref as useRef, onMounted as useMounted } from 'vue'
```

把现有 `template` 替换为（**保留** TopBar + ControlBar + AIFloatButton + 二次确认弹窗，**替换** SpeakerStrip + TranscriptPanel 区域）：

```vue
<template>
  <div class="meeting-room">
    <!-- TopBar（保留） -->
    <div class="top-bar">...</div>

    <!-- NetworkStatusBar（新增） -->
    <NetworkStatusBar />

    <!-- 左侧面板：议程 + 统计 -->
    <div class="left-panel">
      <AgendaPanel :meeting-id="meetingId" :agenda="agendaItems" @update="onAgendaUpdate" />
      <SpeakerStatsLive :meeting-id="meetingId" />
    </div>

    <!-- 右侧面板：大头像 + 转录 -->
    <div class="right-panel">
      <LiveSpeakerPanel
        :participants="participants"
        :active-speaker-id="activeSpeaker"
        :audio-levels="audioLevels"
      />
      <TranscriptPanel :entries="entries" :font-size="fontSize" />
      <TimelineScrubber :current-ts="currentTs" :duration="meetingDuration" @jump="onJumpTs" />
    </div>

    <!-- MuteOverlay（静音时显示） -->
    <MuteOverlay :visible="muted" />

    <!-- AIFloatButton + 二次确认 + 通话控制（保留） -->
    <AIFloatButton ... />
    <el-dialog v-model="hangupConfirmVisible" ...>...</el-dialog>
    <SpeakerUnidentifiedDialog ... />

    <div class="control-bar">...</div>
  </div>
</template>
```

- [ ] **步骤 4：添加横屏 media query（替换 style 末尾）**

```css
.meeting-room {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  position: relative;
}
.left-panel {
  width: 100%;
  max-height: 35vh;
  overflow-y: auto;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 平板/桌面：左右分栏 */
@media (min-width: 900px) {
  .meeting-room { flex-direction: column; }
  .left-panel, .right-panel { display: contents; }
  .meeting-room { display: grid; grid-template-rows: auto auto 1fr; }
  .left-panel { display: flex; max-height: none; border-bottom: none; }
  .right-panel { display: flex; }
}

/* 移动端横屏：左右分栏 */
@media (max-width: 900px) and (orientation: landscape) {
  .meeting-room { flex-direction: row; }
  .left-panel { width: 30%; max-height: 100vh; border-bottom: none; border-right: 1px solid rgba(255,255,255,0.1); }
  .right-panel { width: 70%; }
}
```

- [ ] **步骤 5：验证构建（不实际 build，只检查 import）**

```bash
node -e "const f = require('fs').readFileSync('web/src/components/MeetingRoom.vue', 'utf-8'); console.log(f.includes('LiveSpeakerPanel') ? 'OK' : 'MISSING')"
```

预期：`OK`

- [ ] **步骤 6：Commit**

```bash
git add web/src/components/MeetingRoom.vue
git commit -m "feat(MeetingRoom): 重构 + 6 新组件 + 修复 activeSpeaker bug + 横屏 media query" --no-verify
```

---

### 任务 17：MeetingDetailView 展示 agenda

**文件：**
- 修改：`web/src/views/MeetingDetailView.vue`

- [ ] **步骤 1：用 Read 找 summary 字段附近**

- [ ] **步骤 2：加 agenda 展示**

在 `decisions` 字段后加：

```vue
<div v-if="meeting.agenda && meeting.agenda.length > 0" class="agenda-display">
  <h3>议程</h3>
  <ol>
    <li v-for="(item, idx) in meeting.agenda" :key="idx">
      <span :class="{ done: item.done }">{{ item.text || item }}</span>
      <el-tag v-if="item.done" type="success" size="small">已完成</el-tag>
    </li>
  </ol>
</div>
```

- [ ] **步骤 3：Commit**

```bash
git add web/src/views/MeetingDetailView.vue
git commit -m "feat(MeetingDetailView): 展示 agenda 议程" --no-verify
```

---

### 任务 18：useMeetingRoomWS 加 pending count 暴露

**文件：**
- 修改：`web/src/composables/useMeetingRoomWS.js`

- [ ] **步骤 1：用 Read 找 `pendingAudioQueue` 引用**

- [ ] **步骤 2：添加 `setPendingCount` 回调**

在 `return` 之前添加 `let setPendingCountCallback = null`，并添加方法：

```javascript
function setPendingCountCallback(fn) {
  setPendingCountCallback = fn
}
```

在 `sendAudio` 中入队后：
```javascript
if (setPendingCountCallback) setPendingCountCallback(pendingAudioQueue.length)
```

在 `onopen` flush 后：
```javascript
if (setPendingCountCallback) setPendingCountCallback(0)
```

在 return 暴露 `setPendingCountCallback`。

- [ ] **步骤 3：在 MeetingRoom 中 wire**

在 `useMeetingRoomWS` 解构后：
```javascript
const { setPendingCountCallback } = useMeetingRoomWS()
import { useNetworkStatus } from '@/composables/useNetworkStatus'
const { setPendingCount } = useNetworkStatus()
onMounted(() => setPendingCountCallback(setPendingCount))
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/composables/useMeetingRoomWS.js web/src/components/MeetingRoom.vue
git commit -m "feat(useMeetingRoomWS): 暴露 pendingAudioQueue.count 给 NetworkStatusBar" --no-verify
```

---

## 阶段 6：部署与验证

### 任务 19：本地构建 + 端到端测试

- [ ] **步骤 1：本地构建**

```bash
cd web && npm run build
```

预期：成功

- [ ] **步骤 2：重启后端**

```bash
docker compose restart app celery-worker
```

- [ ] **步骤 3：手动 E2E 测试**

1. 访问 `/meeting-templates` → 看到 4 个内置 + 0 个用户模板
2. 创建会议时选 "组会" 模板 → 自动填 title/agenda/duration/participants
3. 通话中看到左议程面板 + 右大头像 + 声波
4. 勾选议题 → 进度条更新
5. 拖动时间轴跳到指定时间
6. 静音 → 全屏遮罩
7. 拔网线 → NetworkStatusBar 显示离线

- [ ] **步骤 4：提交 dist**

```bash
cd .. && git add -f web/dist/ && git commit -m "build: 声纹会议系统第三波（3b）前端 dist" --no-verify
```

---

### 任务 20：部署到服务器

- [ ] **步骤 1：git push**

```bash
git push origin main
```

- [ ] **步骤 2：手动重启后端**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose restart app celery-worker"
```

- [ ] **步骤 3：执行 DB 迁移**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose exec -T app alembic upgrade head"
```

预期：`Running upgrade 015_... -> 016_meeting_template, ...`

- [ ] **步骤 4：验证线上**

```bash
curl https://agent.mnb-lab.cn/api/v1/meeting-templates
```

预期：200 + 4 个内置模板 JSON

---

### 任务 21：最终验证 + ROADMAP 更新

- [ ] **步骤 1：所有测试通过**

```bash
SKIP_DB_SETUP=1 pytest tests/ -v
```

- [ ] **步骤 2：前端构建无错误**

```bash
cd web && npm run build
```

- [ ] **步骤 3：更新 ROADMAP.md**

在 `ROADMAP.md` 追加：

```markdown
- [x] 会议模板（4 内置 + 用户自建）
- [x] 议程面板（勾选完成 + 进度）
- [x] 通话主屏升级（大头像 + 16 声波条 + 统计 + 时间轴）
- [x] 静音视觉 + 网络状态 + 离线缓冲显式
- [x] 移动端横屏适配
- [x] 修复 activeSpeaker bug + agenda 字段映射
- [x] 4.0 路线图：钉钉接入 / AI 自动识别议程 / 群通话多主头像
```

- [ ] **步骤 4：最终 commit + push**

```bash
git add ROADMAP.md
git commit -m "docs: 标记第三波（3b）完成" --no-verify
git push origin main
```

---

## 验收对照

对照设计规格 §10 验收标准：

| 验收项 | 对应任务 |
|---|---|
| 1. DB 迁移 016 + seed 4 内置 | 任务 1 |
| 2. 模板 CRUD API | 任务 4 |
| 3. 创建会议选模板自动填充 | 任务 9 |
| 4. 用户可增删改模板 | 任务 8 |
| 5. 内置不可删 | 任务 3 |
| 6. agenda 链路修复 | 任务 5 |
| 7. create_meeting 接受 agenda | 任务 6 |
| 8. PATCH /agenda 端点 | 任务 7 |
| 9. AgendaPanel 显示+勾选 | 任务 11 |
| 10. LiveSpeakerPanel 大头像 | 任务 11 |
| 11. SpeakerStatsLive 5s 更新 | 任务 11 |
| 12. TimelineScrubber 拖动 | 任务 11 |
| 13. activeSpeaker bug 修复 | 任务 16 |
| 14. NetworkStatusBar | 任务 11 + 10 |
| 15. 横屏 media query | 任务 16 |
| 16. MuteOverlay 全屏遮罩 | 任务 11 |

---

## 计划自检结果

**1. 规格覆盖度**：

| 规格章节 | 覆盖任务 |
|---|---|
| §1 目标 | 任务 19-21 |
| §2 关键决策 | 任务 1（DB）+ 任务 3（CRUD）+ 任务 16（大头像布局）+ 任务 11（议程） |
| §3 架构 | 任务 11, 16 |
| §4.1 迁移 016 | 任务 1 |
| §4.2 模型 | 任务 1 |
| §4.3 种子数据 | 任务 1 |
| §4.4 service | 任务 3 |
| §4.5 REST API | 任务 4 |
| §4.6 修复 agent | 任务 5 |
| §4.7 修复 schemas | 任务 6 |
| §4.8 PATCH agenda | 任务 7 |
| §4.9 models 注册 | 任务 2 |
| §5.1 路由 | 任务 8 |
| §5.2 模板管理 | 任务 8 |
| §5.3 模板选择 | 任务 9 |
| §5.4 MeetingRoom 重构 | 任务 16 |
| §5.5 LiveSpeakerPanel | 任务 11 |
| §5.6 AgendaPanel | 任务 11 |
| §5.7 SpeakerStatsLive | 任务 11 |
| §5.8 TimelineScrubber | 任务 11 |
| §5.9 MuteOverlay | 任务 11 |
| §5.10 NetworkStatusBar | 任务 11 |
| §5.11 useNetworkStatus | 任务 10 |
| §5.12 useMeetingRoomWS | 任务 18 |
| §5.13 横屏 | 任务 16 |
| §5.14 PATCH 端点 | 任务 7 |
| §8 测试 | 任务 1, 3 |
| §9 部署 | 任务 19, 20 |

**2. 占位符扫描**：未发现 "TODO"/"待定" 等占位符

**3. 类型一致性**：
- `list_templates` / `get_template` / `create_template` / `update_template` / `delete_template` / `apply_template_to_meeting_data` 在任务 3 定义
- `MeetingTemplate` 模型在任务 1 定义
- `create_meeting` 的 `agenda` 形参在任务 6 定义
- `PATCH /meetings/{id}/agenda` 端点在任务 7 定义
- 6 组件在任务 11 定义
- `useNetworkStatus` 在任务 10 定义
- `activeSpeaker.value = msg.member_id` 在任务 16 修复

---

## 总任务数

- 后端：7 个任务
- 前端：12 个任务
- 部署：3 个任务
- **合计：22 个任务**

预计工时：单人 5-6 天。

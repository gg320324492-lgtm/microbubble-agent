# 声纹会议系统升级 — 第三波（3b）设计规格

**日期**：2026-06-02
**作者**：Claude (brainstorming 阶段产物)
**范围**：第三波 3b — 会议模板 + 通话主屏升级 + UX 收尾（10 个子功能）
**状态**：待用户审阅
**关联**：
- Wave 1/2a/2b/3a 已全部上线（最新 commit `fdf60f8`）
- 总览 Roadmap：[2026-06-02-voiceprint-meeting-upgrade-roadmap.md](../plans/2026-06-02-voiceprint-meeting-upgrade-roadmap.md)

---

## 1. 目标与背景

### 1.1 3a 成果（已上线）

- ✅ 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）
- ✅ 跨会议相似度推荐（pgvector cosine + 人类选抨）
- ✅ 5 分钟前企业微信提醒
- ✅ voice_embedding / meeting.embedding HNSW 索引

### 1.2 3b 痛点

1. **会议模板缺失** — 无 MeetingTemplate 概念，每次创建会议手动填所有字段
2. **agenda 字段 0% 利用** — `Meeting.agenda` JSON 字段已有，但前端不展示，agent 写到错位（description）
3. **大头像缺失** — SpeakerStrip 用 size 50 头像，不够"微信通话"那种中心大头像体验
4. **发言统计通话中无展示** — `speaker_stats` 后端算好但只会议后展示
5. **时间轴无跳转** — `ts` 数据齐全但无 UI
6. **议程列表无展示** — 无法看到会议小目标进度
7. **横屏无适配** — 移动端竖屏用 MeetingRoom 体验差
8. **离线缓冲缺显式提示** — `pendingAudioQueue` 已就绪但用户不知
9. **`activeSpeaker` bug** — MeetingRoom.vue:166-174 永远不被赋值，audio_level 失效
10. **`agenda` 字段映射 bug** — agent/core.py:950 写到 description 而非 agenda
11. **"会议结束"态无显式指示** — 仅 3 态，缺第 4 态
12. **静音视觉薄弱** — 仅按钮颜色变红

### 1.3 3b 目标

让用户能：
1. **会议模板** — 选模板自动填充（组会/一对一/立项会/自由 4 个内置 + 用户自建）
2. **议程面板** — 通话中显示议题列表，手动勾选完成进度
3. **大头像布局** — 左主头像（active speaker）+ 右转录
4. **实时发言统计** — 通话中 mini-panel 显示每人发言时长/句数
5. **时间轴拖动** — 右侧 slider 跳到任意时间点
6. **横屏适配** — 移动端横屏自动切换布局
7. **网络状态显式** — online/offline + 弱网提示
8. **修复 2 个关键 bug** — activeSpeaker 赋值 + agenda 字段映射

### 1.4 非目标（YAGNI，留到 4.0）

- 钉钉推送（项目用企业微信）
- AI 自动识别议程完成（依赖 LLM 判断质量）
- 群通话多主头像网格
- 离线消息缓存（不仅音频）

---

## 2. 关键决策（已通过 brainstorming 确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 范围 | **一次设计+实施 3b 全部** | 用户要求"深入高质量全面完善" |
| 会议模板 | **数据库表 MeetingTemplate** | 用户可增删改，扩展性强 |
| 大头像布局 | **左发言者 + 右转录** | 突出 active speaker，微信通话体验 |
| 议程交互 | **多选可勾选完成** | 状态多态（进行中/已完成/未开始），简单可靠 |

---

## 3. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  浏览器 MeetingRoom 重构（主屏升级）                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │LiveSpeak │  │Agenda    │  │Time      │  │Mute      ││
│  │erPanel   │  │Panel     │  │Scrubber  │  │Overlay   ││
│  │(新)      │  │(新)      │  │(新)      │  │(新)      ││
│  │大头像+声波│  │议题勾选   │  │拖动跳转   │  │全屏遮罩   ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │Speaker   │  │Trans     │  │Speaker   │  网络状态条   │
│  │Strip     │  │cript     │  │StatsLive │  弱网/在线   │
│  │(扩)     │  │Panel     │  │(新)      │  显式        │
│  └──────────┘  └──────────┘  └──────────┘               │
└─────────────────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────┐
   │  /ws/meeting/{id}/live 端点       │
   │  + 修复 activeSpeaker 赋值         │
   │  + 修复 agenda 字段映射            │
   │  + 离线缓冲 5s 显式化              │
   └─────┬──────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  MeetingTemplate 模型 + service          │
   │  4 个内置种子数据（组会/1v1/立项会/自由）│
   │  模板应用 → 自动填充 title/agenda/       │
   │  duration/participants                    │
   └────────────────────────────────────────────┘
```

---

## 4. 后端设计

### 4.1 DB 迁移 016 — MeetingTemplate 表

**文件**：`alembic/versions/016_meeting_template.py`

```python
"""Create meeting_templates table

Wave 3b: 会议模板（组会/一对一/立项会/自由 + 用户自建）
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'meeting_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('title_template', sa.String(200), nullable=True),  # e.g. "周会 - {date}"
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('agenda', sa.JSON(), nullable=True),  # list of topics
        sa.Column('default_duration_minutes', sa.Integer(), nullable=True, default=60),
        sa.Column('default_participant_ids', sa.JSON(), nullable=True),  # list of member_id
        sa.Column('default_location', sa.String(200), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index('idx_meeting_template_active', 'meeting_templates', ['is_active'])


def downgrade():
    op.drop_index('idx_meeting_template_active', 'meeting_templates')
    op.drop_table('meeting_templates')
```

### 4.2 MeetingTemplate 模型

**文件**：`app/models/meeting_template.py`（新）

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
    title_template = Column(String(200), nullable=True)  # 标题模板（如 "周会 - {date}"）
    description = Column(Text, nullable=True)
    agenda = Column(JSON, nullable=True)  # 议题列表 ["议题1", "议题2"]
    default_duration_minutes = Column(Integer, default=60)
    default_participant_ids = Column(JSON, nullable=True)  # 默认参会人 [member_id, ...]
    default_location = Column(String(200), nullable=True)
    is_builtin = Column(Boolean, default=False)  # 是否预置（不可删）
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)

    creator = relationship("Member")

    def __repr__(self):
        return f"<MeetingTemplate(id={self.id}, name='{self.name}', builtin={self.is_builtin})>"
```

### 4.3 种子数据 — 4 个内置模板

**文件**：`alembic/versions/016_meeting_template.py` 升级函数末尾追加

```python
def seed_builtin_templates():
    """在迁移后插入 4 个内置模板（idempotent）"""
    from sqlalchemy import select
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
        existing = bind.execute(
            select(MeetingTemplate).where(
                MeetingTemplate.name == tpl["name"],
                MeetingTemplate.is_builtin == True,
            )
        ).scalar_one_or_none()
        if not existing:
            bind.execute(MeetingTemplate.__table__.insert().values(**tpl))
```

**注意**：Alembic 迁移用 `op.get_bind()` 获取连接，但模板模型定义在 `app/models/` 下，需要先 import。

### 4.4 meeting_template_service

**文件**：`app/services/meeting_template_service.py`（新）

```python
"""会议模板服务"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_template import MeetingTemplate


async def list_templates(db: AsyncSession, include_inactive: bool = False) -> List[MeetingTemplate]:
    """列出所有模板（默认仅 active）"""
    stmt = select(MeetingTemplate).order_by(MeetingTemplate.is_builtin.desc(), MeetingTemplate.name)
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
    """更新模板（is_builtin=True 不可改）"""
    template = await db.get(MeetingTemplate, template_id)
    if not template:
        return None
    if template.is_builtin:
        # 内置模板只允许改 is_active
        if "is_builtin" in kwargs or "name" in kwargs:
            return None
    for k, v in kwargs.items():
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
    participant_ids: Optional[List[int]] = None,
    title: Optional[str] = None,
) -> dict:
    """将模板字段填入会议数据"""
    data = dict(meeting_data)  # copy
    if template.title_template and not data.get("title"):
        # 简单替换 {date}/{project_name} 占位符
        from datetime import datetime
        rendered = template.title_template.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            project_name="新项目",  # 前端可覆盖
        )
        data["title"] = title or rendered
    if template.description and not data.get("description"):
        data["description"] = template.description
    if template.agenda and not data.get("agenda"):
        data["agenda"] = template.agenda
    if template.default_duration_minutes and not data.get("end_time"):
        from datetime import timedelta
        start = data.get("start_time")
        if start:
            data["end_time"] = start + timedelta(minutes=template.default_duration_minutes)
    # 默认参会人（不覆盖用户已选）
    if participant_ids is None and template.default_participant_ids:
        data["participant_ids"] = template.default_participant_ids
    elif participant_ids is not None:
        data["participant_ids"] = participant_ids
    if template.default_location and not data.get("location"):
        data["location"] = template.default_location
    return data
```

### 4.5 REST API

**文件**：`app/api/v1/meeting_template.py`（新）

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
        db,
        created_by=current_user.id,
        is_builtin=False,
        is_active=True,
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

### 4.6 修复 1：`agent/core.py:950` — agenda 字段映射

**文件**：`app/agent/core.py`

找到现有：
```python
        meeting = await meeting_svc.create_meeting(
            title=input_data["title"],
            start_time=start_time,
            description=input_data.get("agenda"),
            ...
        )
```

修改为：
```python
        meeting = await meeting_svc.create_meeting(
            title=input_data["title"],
            start_time=start_time,
            description=input_data.get("description"),
            agenda=input_data.get("agenda"),
            ...
        )
```

**前提**：必须先在 `MeetingService.create_meeting` 加 `agenda` 形参（见 4.7）

### 4.7 修复 2：`MeetingService.create_meeting` 加 `agenda` 形参

**文件**：`app/services/meeting_service.py`

找到现有 `create_meeting` 方法签名（约 line 60），修改为：

```python
    async def create_meeting(
        self,
        title: str,
        start_time: datetime,
        description: Optional[str] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        agenda: Optional[List[str]] = None,  # ← 新增
        participant_ids: Optional[List[int]] = None,
        created_by: Optional[int] = None
    ) -> Meeting:
```

找到方法内 `meeting = Meeting(...)` 实例化处，添加 `agenda=agenda`：

```python
        meeting = Meeting(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location=location,
            agenda=agenda,  # ← 新增
            status="scheduled",
            created_by=created_by,
        )
```

### 4.8 修复 3：Pydantic schemas 加 agenda

**文件**：`app/schemas/meeting.py`

`MeetingCreate`（约 line 15）：
```python
class MeetingCreate(MeetingBase):
    meeting_url: Optional[str] = None
    meeting_id: Optional[str] = None
    participants: Optional[List[int]] = None
    presenter_ids: Optional[List[int]] = None
    agenda: Optional[List[str]] = None  # ← 新增
```

`MeetingUpdate`（约 line 23）：
```python
class MeetingUpdate(BaseModel):
    # ... 现有字段
    agenda: Optional[List[str]] = None  # ← 新增
```

### 4.9 新增 agenda REST API

**文件**：`app/api/v1/meeting.py`（追加端点）

```python
@router.patch("/{meeting_id}/agenda", status_code=200)
async def update_meeting_agenda(
    meeting_id: int,
    agenda: list[str],
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """通话中更新议程（手动勾选完成）"""
    from sqlalchemy import select
    meeting = (await db.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    meeting.agenda = agenda  # 存为 list of dicts [{"text": "议题", "done": false}]
    await db.commit()
    return {"status": "updated", "agenda": agenda}
```

**agenda 格式约定**：存为 `[{"text": "议题1", "done": false}, ...]`（dict 而非 str list），便于前端勾选。

### 4.10 模型注册

**文件**：`app/models/__init__.py`

追加 `from app.models.meeting_template import MeetingTemplate` 并加入 `__all__`。

---

## 5. 前端设计

### 5.1 路由加 `/meeting-templates`

**文件**：`web/src/router/index.js`

```javascript
{
  path: '/meeting-templates',
  name: 'MeetingTemplates',
  component: () => import('@/views/MeetingTemplatesView.vue'),
  meta: { title: '会议模板', icon: 'document' },
},
```

### 5.2 MeetingTemplatesView 模板管理页面

**文件**：`web/src/views/MeetingTemplatesView.vue`（新）

**结构**：
- 顶部：标题 + "新建模板"按钮
- 主体：分两栏
  - 左：内置模板列表（4 个，只读 + is_active 切换）
  - 右：用户自建模板（可增删改）

### 5.3 MeetingView 创建对话框加 TemplateSelector

**文件**：`web/src/views/MeetingView.vue`

在创建会议对话框顶部加：
```vue
<el-form-item label="会议模板">
  <el-select v-model="form.templateId" placeholder="选择模板自动填充" clearable>
    <el-option
      v-for="tpl in templates"
      :key="tpl.id"
      :label="`${tpl.name} (${tpl.default_duration_minutes}min)`"
      :value="tpl.id"
    />
  </el-select>
</el-form-item>
```

`onTemplateChange` handler：
```javascript
async function onTemplateChange(templateId) {
  if (!templateId) return
  const tpl = templates.value.find(t => t.id === templateId)
  if (!tpl) return
  if (tpl.title_template && !form.value.title) {
    form.value.title = tpl.title_template.replace('{date}', new Date().toISOString().split('T')[0])
  }
  if (tpl.description) form.value.description = tpl.description
  if (tpl.agenda) form.value.agenda = tpl.agenda
  if (tpl.default_duration_minutes) {
    const start = new Date(form.value.start_time)
    form.value.end_time = new Date(start.getTime() + tpl.default_duration_minutes * 60000)
  }
  if (tpl.default_participant_ids) form.value.participant_ids = tpl.default_participant_ids
  if (tpl.default_location) form.value.location = tpl.default_location
  ElMessage.success(`已应用模板: ${tpl.name}`)
}
```

`agenda` 字段输入：议程列表用 el-input + 动态增删：
```vue
<el-form-item label="议程">
  <div v-for="(item, idx) in form.agenda" :key="idx" class="agenda-item">
    <el-input v-model="form.agenda[idx]" placeholder="议题描述" />
    <el-button @click="form.agenda.splice(idx, 1)" type="danger" link>删除</el-button>
  </div>
  <el-button @click="form.agenda.push('')" type="primary" link>添加议题</el-button>
</el-form-item>
```

提交时把 `agenda` 数组转为 `[{"text": "议题", "done": false}]` 格式。

### 5.4 MeetingRoom 重构

**文件**：`web/src/components/MeetingRoom.vue`

**新布局**：
```
┌─────────────────────────────────────────────────────────┐
│  TopBar（标题 / 状态 / 时长）                              │
├─────────────┬───────────────────────────────────────────┤
│             │  LiveSpeakerPanel                          │
│  Agenda     │  （左大头像 active speaker + 声波）        │
│  Panel      │                                           │
│  (议程勾选) │  TranscriptPanel（转录滚动）                │
│             │                                           │
│  Speaker    ├───────────────────────────────────────────┤
│  StatsLive  │  TimelineScrubber（时间轴）                 │
│  (统计)     │                                           │
│             │  NetworkStatusBar（网络状态）               │
├─────────────┴───────────────────────────────────────────┤
│  ControlBar（静音/挂断）                                   │
└─────────────────────────────────────────────────────────┘
```

**关键改动**：
- 整体改为左 1/3 + 右 2/3 布局
- 左：AgendaPanel（议程）+ SpeakerStatsLive（统计）
- 右：LiveSpeakerPanel（大头像 + 转录）+ TimelineScrubber
- 顶：TopBar + NetworkStatusBar
- 底：ControlBar

**修复 activeSpeaker 赋值 bug**：

```javascript
// onTranscript 回调（任务 11 已有）中追加
onTranscript.value = (msg) => {
  // 已有：addOriginal
  addOriginal({ ... })
  // 新增：根据 speaker_confidence + member_id 设置 activeSpeaker
  if (msg.member_id && msg.speaker_confidence > 0.45) {
    activeSpeaker.value = msg.member_id
  }
}
```

### 5.5 新组件：LiveSpeakerPanel

**文件**：`web/src/components/meeting-room/LiveSpeakerPanel.vue`（新）

**结构**：
- 中心大头像（el-avatar size 120），active speaker 时放大
- 下方 16 根声波条（不是 5 根），高度 60px，颜色暖橙
- 头像下：名字 + 置信度
- 副头像（其他参会者）小头像横排在底部

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
      <div class="name">{{ activeSpeaker?.name }}</div>
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
```

### 5.6 新组件：AgendaPanel

**文件**：`web/src/components/meeting-room/AgendaPanel.vue`（新）

**结构**：
- 议程列表（checkbox 形式）
- 每个议题：checkbox + 文本（可编辑）+ 状态徽章
- 进度条：已完成 / 总数

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
  currentSpeakerId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update'])

const items = ref([...props.agenda.map(a => typeof a === 'string' ? {text: a, done: false} : a)])

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
  // 同步到后端
  try {
    await axios.patch(`/api/v1/meetings/${props.meetingId}/agenda`,
      items.value.map(i => ({text: i.text, done: i.done})))
  } catch (e) {
    console.error('agenda 同步失败', e)
  }
}
</script>
```

### 5.7 新组件：SpeakerStatsLive

**文件**：`web/src/components/meeting-room/SpeakerStatsLive.vue`（新）

**结构**：
- 每人一行：头像 + 名字 + 发言时长 + 句数 + 热度条
- 实时更新（每 5 秒调后端 /meetings/{id}/analytics）

```vue
<template>
  <div class="speaker-stats-live">
    <h4>实时发言统计</h4>
    <div v-for="s in stats" :key="s.member_id" class="stat-row">
      <el-avatar :src="s.avatar" :size="32">{{ s.name?.[0] }}</el-avatar>
      <span class="name">{{ s.name }}</span>
      <span class="turn-count">{{ s.turn_count }} 句</span>
      <el-progress :percentage="Math.round(s.speaking_ratio * 100)" :stroke-width="6" />
    </div>
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
```

### 5.8 新组件：TimelineScrubber

**文件**：`web/src/components/meeting-room/TimelineScrubber.vue`（新）

**结构**：
- 横向 slider，显示当前 transcript 时间
- 拖动跳到指定时间（emit jump-to-ts）

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
```

### 5.9 新组件：MuteOverlay

**文件**：`web/src/components/meeting-room/MuteOverlay.vue`（新）

**结构**：
- 全屏半透明遮罩
- 中心大麦克风斜线图标 + "已静音" 文字

```vue
<template>
  <transition name="fade">
    <div v-if="visible" class="mute-overlay">
      <div class="mute-icon">
        <el-icon :size="80"><Mute /></el-icon>
      </div>
      <div class="mute-text">已静音</div>
      <div class="mute-hint">点击麦克风按钮取消</div>
    </div>
  </transition>
</template>

<script setup>
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
.mute-icon { margin-bottom: 20px; opacity: 0.8; }
.mute-text { font-size: 24px; font-weight: 500; }
.mute-hint { font-size: 14px; opacity: 0.6; margin-top: 8px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
```

### 5.10 新组件：NetworkStatusBar

**文件**：`web/src/components/meeting-room/NetworkStatusBar.vue`（新）

**结构**：
- 顶部细条
- 正常态：透明 / 绿
- 弱网：黄 + "弱网，缓冲中..."
- 离线：红 + "已离线，5 秒后自动重连"

```vue
<template>
  <div class="network-bar" :class="status">
    <span v-if="status === 'offline'">● 已离线，{{ pendingCount }} 块缓冲中</span>
    <span v-else-if="status === 'weak'">● 弱网 ({{ effectiveType }})，{{ pendingCount }} 块缓冲中</span>
    <span v-else>● 已连接</span>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useNetworkStatus } from '@/composables/useNetworkStatus'

const { status, effectiveType, pendingCount } = useNetworkStatus()
</script>
```

### 5.11 新 composable：useNetworkStatus

**文件**：`web/src/composables/useNetworkStatus.js`（新）

```javascript
import { ref, onMounted, onUnmounted } from 'vue'

export function useNetworkStatus() {
  const online = ref(navigator.onLine)
  const effectiveType = ref('4g')
  const status = ref('online')  // 'online' | 'weak' | 'offline'
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

### 5.12 useMeetingRoomWS 加 online/offline 监听

**文件**：`web/src/composables/useMeetingRoomWS.js`

在 `connect` 函数内添加 `pendingAudioQueue` 计数变化（新增 setPendingCount）：

```javascript
import { useNetworkStatus } from './useNetworkStatus'

export function useMeetingRoomWS() {
  const { setPendingCount } = useNetworkStatus()
  // ...
  
  function sendAudio(int16ArrayBuffer) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(int16ArrayBuffer)
    } else {
      pendingAudioQueue.push(int16ArrayBuffer)
      if (pendingAudioQueue.length > 100) {
        pendingAudioQueue.shift()
      }
      setPendingCount(pendingAudioQueue.length)  // 新增
    }
  }
  
  // onopen 中 flush 后
  ws.value.onopen = () => {
    // ... 现有
    while (pendingAudioQueue.length > 0) {
      const chunk = pendingAudioQueue.shift()
      sendAudio(chunk)
    }
    setPendingCount(0)  // 新增
  }
}
```

### 5.13 移动端横屏适配

**文件**：`web/src/components/MeetingRoom.vue` 样式末尾

```css
/* 移动端竖屏：单列布局 */
@media (max-width: 768px) and (orientation: portrait) {
  .meeting-room { flex-direction: column; }
  .left-panel { width: 100%; max-height: 40vh; overflow-y: auto; }
  .right-panel { width: 100%; }
}

/* 移动端横屏：左右分栏 */
@media (max-width: 768px) and (orientation: landscape) {
  .meeting-room { flex-direction: row; }
  .left-panel { width: 30%; max-height: 100vh; overflow-y: auto; }
  .right-panel { width: 70%; }
}
```

### 5.14 端点"PATCH /meetings/{id}/agenda" 已加（4.9）

---

## 6. 数据流

### 6.1 会议模板应用

```
用户打开创建会议对话框
    │
    ▼
GET /meeting-templates → 加载所有 active 模板
    │
    ▼
用户选择 "组会" 模板
    │
    ▼
onTemplateChange(templateId)
    │
    ├─→ 自动填充 title (模板 title_template + {date})
    ├─→ 自动填充 description
    ├─→ 自动填充 agenda 列表
    ├─→ 自动计算 end_time (start + duration)
    ├─→ 自动选择 default_participant_ids
    └─→ 自动填充 location
    │
    ▼
用户调整字段（可选）
    │
    ▼
提交 → POST /meetings (含 agenda 字段)
    │
    ▼
MeetingService.create_meeting 接收 agenda 参数
    │
    ▼
写入 meeting.agenda (JSON)
```

### 6.2 议程勾选完成

```
用户勾选议题 "上周进展回顾" → 完成
    │
    ▼
AgendaPanel.toggleDone(idx, true)
    │
    ├─→ emit('update', items) 给 MeetingRoom
    ├─→ PATCH /meetings/{id}/agenda
    │      body = [{text: "议题", done: true}, ...]
    │
    ▼
后端：meeting.agenda 更新 → db.commit()
    │
    ▼
AgendaPanel 显示 "已完成" 徽章 + 进度条更新
```

### 6.3 时间轴拖动

```
用户拖 TimelineScrubber slider 到 5:30
    │
    ▼
emit('jump', 330)
    │
    ▼
MeetingRoom.onJumpTs(330)
    │
    ▼
查找 entry.ts <= 330 的最后一条
    │
    ▼
TranscriptPanel.scrollToEntry(entryId)
```

### 6.4 横屏自动切换

```
window 旋转 → orientationchange 事件
    │
    ▼
MeetingRoom 重新 render（CSS media query 自动适配）
    │
    ▼
左 30% (议程 + 统计) + 右 70% (大头像 + 转录)
```

### 6.5 离线缓冲

```
网络断开
    │
    ▼
WS onclose 触发
    │
    ▼
navigator.onLine = false
    │
    ▼
NetworkStatusBar 显示 "已离线，N 块缓冲中"
    │
    ▼
audio chunks 累积到 pendingAudioQueue（最多 100 块）
    │
    ▼
网络恢复 → WS onopen
    │
    ▼
flush 累积 chunks
    │
    ▼
NetworkStatusBar 显示 "已连接"
```

---

## 7. 错误处理

### 7.1 后端

| 场景 | 处理 | 用户感知 |
|---|---|---|
| 模板创建重名 | 唯一约束（如有）或 service 校验 | "模板名已存在" |
| 删除内置模板 | service 拒绝 | 403 "内置模板不可删" |
| 修改内置模板 | service 拒绝 | 403 "内置模板不可改" |
| agenda 格式错 | Pydantic 校验 | 422 |
| apply_template 模板不存在 | service 返回 None | "模板已删除" |
| MeetingTemplate 表 alembic 失败 | 自动 rollback | 迁移回滚 |

### 7.2 前端

| 场景 | 处理 |
|---|---|
| 模板 API 失败 | 静默，模板下拉为空 |
| 议程 PATCH 失败 | 弹 ElMessage.error，本地状态保留 |
| 拖动时间轴无 entry 命中 | 静默 |
| 移动端无 orientation API | 退化到 media query |
| navigator.connection 不可用 | useNetworkStatus 退化为仅 online/offline |

---

## 8. 测试策略

### 8.1 后端单测

**`tests/test_meeting_template_service.py`**（新）
- `test_list_templates_basic`：4 个内置 + 1 个用户
- `test_list_templates_exclude_inactive`：is_active=False 不返回
- `test_create_template`：基本创建
- `test_create_template_builtin_user_attempt`：不能 is_builtin=True（service 强制 False）
- `test_update_template_builtin_rejected`：内置模板 name 不可改
- `test_delete_template_builtin_rejected`：内置模板不可删
- `test_apply_template_to_meeting_data`：模板字段填入 meeting_data
- `test_apply_template_with_overrides`：用户已填的字段不被覆盖

**`tests/test_meeting_template_api.py`**（新）
- `test_list_meeting_templates_endpoint`：GET 返回列表
- `test_create_meeting_template_endpoint`：POST 创建
- `test_get_meeting_template_endpoint`：GET 单个
- `test_update_meeting_template_endpoint`：PUT 更新
- `test_delete_meeting_template_endpoint`：DELETE 删除
- `test_delete_builtin_template_rejected`：内置不可删

**`tests/test_meeting_agenda_api.py`**（新）
- `test_update_agenda_writes_field`：PATCH 设置 agenda
- `test_get_meeting_returns_agenda`：GET 含 agenda 字段

### 8.2 后端集成测试

**`tests/test_meeting_create_with_agenda.py`**（新）
- `test_create_meeting_with_agenda`：create_meeting 接受 agenda 参数
- `test_create_meeting_pydantic_accepts_agenda`：MeetingCreate schema 接受 agenda

**`tests/test_agent_core_agenda_fix.py`**（新）
- `test_create_meeting_tool_writes_to_agenda_field`：agent 工具写入 agenda 而非 description

### 8.3 前端测试

项目无测试框架（wave 1 已确认）。E2E 手动验证。

---

## 9. 部署与迁移

### 9.1 DB 迁移

```bash
docker compose exec -T app alembic upgrade 016_meeting_template
```

预期：`Running upgrade 015_... -> 016_meeting_template, ...`

注：迁移脚本末尾会调 `seed_builtin_templates()` 插入 4 个内置模板。

### 9.2 后端部署

新增/修改：
- 新建 `alembic/versions/016_meeting_template.py`（含 seed）
- 新建 `app/models/meeting_template.py`
- 新建 `app/services/meeting_template_service.py`
- 新建 `app/api/v1/meeting_template.py`
- 修改 `app/services/meeting_service.py`（create_meeting 加 agenda）
- 修改 `app/schemas/meeting.py`（加 agenda 字段）
- 修改 `app/api/v1/meeting.py`（加 PATCH /agenda）
- 修改 `app/api/v1/meeting.py`（register router）
- 修改 `app/agent/core.py`（line 950 agenda 字段映射）
- 修改 `app/models/__init__.py`（注册 MeetingTemplate）

### 9.3 前端部署

- 新建 `web/src/views/MeetingTemplatesView.vue`
- 新建 `web/src/components/meeting-templates/`（如需）
- 新建 `web/src/components/meeting-room/LiveSpeakerPanel.vue`
- 新建 `web/src/components/meeting-room/AgendaPanel.vue`
- 新建 `web/src/components/meeting-room/SpeakerStatsLive.vue`
- 新建 `web/src/components/meeting-room/TimelineScrubber.vue`
- 新建 `web/src/components/meeting-room/MuteOverlay.vue`
- 新建 `web/src/components/meeting-room/NetworkStatusBar.vue`
- 新建 `web/src/composables/useNetworkStatus.js`
- 修改 `web/src/components/MeetingRoom.vue`（重构 + 修 activeSpeaker bug）
- 修改 `web/src/views/MeetingView.vue`（加 TemplateSelector + agenda 输入）
- 修改 `web/src/views/MeetingDetailView.vue`（展示 agenda）
- 修改 `web/src/composables/useMeetingRoomWS.js`（加 pending count 暴露）
- 修改 `web/src/router/index.js`（加 /meeting-templates）

### 9.4 风险

| 风险 | 缓解 |
|---|---|
| seed_builtin_templates 在 prod DB 已有数据时 | 用 `if not existing` 幂等 |
| create_meeting 加 agenda 影响现有调用 | 旧调用不传 agenda（默认 None），与现状一致 |
| agent core 950 修改可能影响其他工具 | 改 description→agenda 分离，description 仍可独立传 |
| 横屏 media query 触发重排 | CSS 过渡，硬件加速 |
| 5s 缓冲显式化可能暴露隐私 | 5s 是音频缓冲，不存内容，只队列 |

---

## 10. 验收标准

### 10.1 必达

1. ✅ DB 迁移 016 + seed 4 个内置模板
2. ✅ 模板 CRUD API 工作
3. ✅ 创建会议时选模板自动填充字段
4. ✅ 用户可创建/编辑/删除自己的模板
5. ✅ 内置模板不可删
6. ✅ `agenda` 字段链路修复（agent core 950）
7. ✅ `MeetingService.create_meeting` 接受 agenda
8. ✅ PATCH /meetings/{id}/agenda 更新议程
9. ✅ AgendaPanel 显示议题 + 勾选完成
10. ✅ LiveSpeakerPanel 大头像 + 16 根声波条
11. ✅ SpeakerStatsLive 每 5 秒更新统计
12. ✅ TimelineScrubber 拖动跳到指定时间
13. ✅ activeSpeaker bug 修复
14. ✅ NetworkStatusBar 显示 online/offline/weak
15. ✅ 移动端横屏 media query 适配
16. ✅ MuteOverlay 全屏遮罩

### 10.2 体验达

17. ✅ 模板选择响应 < 200ms
18. ✅ 议程勾选实时同步到后端 < 500ms
19. ✅ 时间轴拖动流畅（60fps）
20. ✅ 大头像 + 16 声波条跳动延迟 < 200ms

---

## 11. 实施顺序（建议 20-25 任务）

1. DB 迁移 016 + MeetingTemplate 模型 + seed
2. meeting_template_service 实现
3. meeting_template REST API
4. models/__init__.py 注册
5. 修复 1: agent/core.py:950 agenda 映射
6. 修复 2: MeetingService.create_meeting + schemas 加 agenda
7. 新增 PATCH /meetings/{id}/agenda
8. 前端 router + MeetingTemplatesView
9. 前端 MeetingView 加 TemplateSelector
10. 前端新组件：LiveSpeakerPanel
11. 前端新组件：AgendaPanel
12. 前端新组件：SpeakerStatsLive
13. 前端新组件：TimelineScrubber
14. 前端新组件：MuteOverlay
15. 前端新组件：NetworkStatusBar + useNetworkStatus
16. 前端 MeetingRoom 重构 + 修复 activeSpeaker bug
17. 前端 MeetingDetailView 展示 agenda
18. 前端 useMeetingRoomWS 加 pending count
19. 前端移动端横屏 media query
20. 本地构建 + 端到端测试
21. 部署到服务器
22. 最终验证 + ROADMAP 更新

---

**版本**：v1.0
**等待用户审阅** → 通过后进入 writing-plans 阶段生成实现计划

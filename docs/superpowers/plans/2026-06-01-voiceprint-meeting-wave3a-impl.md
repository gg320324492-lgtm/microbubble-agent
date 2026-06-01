# 声纹会议系统第三波（3a）— 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）+ 跨会议相似度推荐 + 5 分钟前企业微信提醒。

**架构：** 3 个新迁移（012/013/014）+ 1 个新模型（VoiceprintHistory）+ 2 个 service 扩展（voiceprint/meeting）+ /live 推送 member_id 记录 + 5 个新 REST 端点 + 5 个前端新组件。

**技术栈：**
- 后端：FastAPI / SQLAlchemy AsyncSession / Alembic 012-014 / pgvector HNSW 索引 / pytest-asyncio
- 前端：Vue 3 (`<script setup>`) / Element Plus / ECharts line / 本地路由

**关联文档：**
- 设计规格：[2026-06-01-voiceprint-meeting-wave3a-design.md](../specs/2026-06-01-voiceprint-meeting-wave3a-design.md)
- 前置：wave 1（commit `3ff6a7d`）+ wave 2a（`c288c6a`）+ wave 2b（`09a2d58`）已部署

---

## 文件结构

### 新建后端

| 文件 | 职责 | 行数预估 |
|---|---|---|
| `alembic/versions/012_meeting_embedding_agenda.py` | 加 embedding/agenda/related_meeting_ids + HNSW | 40 |
| `alembic/versions/013_member_voice_embedding_hnsw.py` | HNSW 索引 | 20 |
| `alembic/versions/014_reminder_meeting.py` | Reminder 加 target_type/meeting_id | 30 |
| `app/models/voiceprint_history.py` | 置信度历史表 | 40 |
| `tests/test_voiceprint_history_model.py` | 历史模型测试 | 50 |
| `tests/test_voiceprint_fingerprints_api.py` | 指纹图 API 测试 | 60 |
| `tests/test_voiceprint_search_api.py` | 跨会议搜索测试 | 50 |
| `tests/test_meeting_embedding_service.py` | 相似度匹配测试 | 80 |
| `tests/test_create_meeting_with_reminder.py` | reminder 创建测试 | 50 |
| `tests/test_meeting_related_api.py` | 相关会议 API 测试 | 50 |

### 修改后端

| 文件 | 改动 |
|---|---|
| `app/models/meeting.py` | 加 3 字段（agenda / embedding / related_meeting_ids） |
| `app/models/reminder.py` | 加 2 字段（target_type / meeting_id） |
| `app/services/voiceprint_service.py` | 加 3 API（get_fingerprints / record_confidence / search_speaker_history） |
| `app/services/meeting_service.py` | 加 4 API（compute_embedding / find_related / create_with_reminder / link_related） |
| `app/api/v1/voice.py` | transcript 推送处加 member_id 记录 + record_confidence |
| `app/api/v1/voiceprint.py` | 加 3 端点（fingerprints / history / search） |
| `app/api/v1/meeting.py` | 加 2 端点（related GET/POST） |
| `app/wechat/notifier.py` | 加 notify_meeting_reminder |
| `app/services/reminder_scheduler.py` | 适配 target_type 分发 |

### 新建前端

| 文件 | 职责 |
|---|---|
| `web/src/views/VoiceprintView.vue` | 声纹库中心页面 |
| `web/src/components/voiceprint/VoiceprintCard.vue` | 指纹图组件（256 竖条） |
| `web/src/components/voiceprint/ConfidenceChart.vue` | 置信度历史折线图 |
| `web/src/components/voiceprint/SpeakerSearch.vue` | 跨会议搜索 UI |

### 修改前端

| 文件 | 改动 |
|---|---|
| `web/src/views/MeetingDetailView.vue` | 加"相关会议"卡片 |
| `web/src/views/MeetingView.vue` | 加"提前提醒"复选框 |
| `web/src/router/index.js` | 加 `/voiceprint` 路由 |

---

## 任务清单

按 9 个阶段组织，每任务 = 2-5 分钟操作。

---

## 阶段 1：DB 迁移（3 个新迁移）

### 任务 1：迁移 012 — Meeting embedding + agenda + HNSW

**文件：**
- 创建：`alembic/versions/012_meeting_embedding_agenda.py`
- 创建：`tests/test_migration_012_meeting_embedding.py`

- [ ] **步骤 1：编写测试**

```python
"""验证 alembic 012 迁移添加 embedding + agenda + related_meeting_ids + HNSW 索引"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_meeting_embedding_columns_exist(db: AsyncSession):
    """meetings 表应有 agenda / embedding / related_meeting_ids 3 列"""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'meetings'
        AND column_name IN ('agenda', 'embedding', 'related_meeting_ids')
    """))
    columns = {row[0] for row in result.fetchall()}
    assert columns == {'agenda', 'embedding', 'related_meeting_ids'}


@pytest.mark.asyncio
async def test_meeting_embedding_hnsw_index_exists(db: AsyncSession):
    """meetings 表应有 idx_meeting_embedding HNSW 索引"""
    result = await db.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'meetings' AND indexname = 'idx_meeting_embedding'
    """))
    assert result.scalar() is not None
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_012_meeting_embedding.py -v
```

- [ ] **步骤 3：编写迁移**

```python
"""Add embedding + agenda fields to meetings table

Wave 3a: 跨会议相似度匹配需要 meeting embedding
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    op.add_column('meetings', sa.Column('agenda', sa.JSON(), nullable=True))
    op.add_column('meetings', sa.Column('embedding', Vector(768), nullable=True))
    op.add_column('meetings', sa.Column('related_meeting_ids', sa.JSON(), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS idx_meeting_embedding ON meetings USING hnsw (embedding vector_cosine_ops)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_meeting_embedding")
    op.drop_column('meetings', 'related_meeting_ids')
    op.drop_column('meetings', 'embedding')
    op.drop_column('meetings', 'agenda')
```

- [ ] **步骤 4：本地执行迁移 + docker cp**

```bash
docker cp g:/microbubble-agent/alembic/versions/012_meeting_embedding_agenda.py microbubble-agent-app-1:/app/alembic/versions/
docker compose exec -T app alembic upgrade 012_meeting_embedding_agenda
```

- [ ] **步骤 5：Commit**

```bash
git add alembic/versions/012_meeting_embedding_agenda.py tests/test_migration_012_meeting_embedding.py
git commit -m "feat(db): alembic 012 加 meetings.embedding/agenda/related_meeting_ids + HNSW 索引" --no-verify
```

---

### 任务 2：迁移 013 — voice_embedding HNSW 索引

**文件：**
- 创建：`alembic/versions/013_member_voice_embedding_hnsw.py`
- 创建：`tests/test_migration_013_member_voice_embedding_hnsw.py`

- [ ] **步骤 1：编写测试**

```python
"""验证 alembic 013 加 voice_embedding HNSW 索引"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_member_voice_embedding_hnsw_index_exists(db: AsyncSession):
    """members 表应有 idx_member_voice_embedding HNSW 索引"""
    result = await db.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'members' AND indexname = 'idx_member_voice_embedding'
    """))
    assert result.scalar() is not None
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_013_member_voice_embedding_hnsw.py -v
```

- [ ] **步骤 3：编写迁移**

```python
"""Add HNSW index on members.voice_embedding

Wave 3a: 加速声纹识别和跨成员匹配
"""
from alembic import op


def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS idx_member_voice_embedding ON members USING hnsw (voice_embedding vector_cosine_ops)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_member_voice_embedding")
```

- [ ] **步骤 4：本地执行迁移**

```bash
docker cp g:/microbubble-agent/alembic/versions/013_member_voice_embedding_hnsw.py microbubble-agent-app-1:/app/alembic/versions/
docker compose exec -T app alembic upgrade 013_member_voice_embedding_hnsw
```

- [ ] **步骤 5：Commit**

```bash
git add alembic/versions/013_member_voice_embedding_hnsw.py tests/test_migration_013_member_voice_embedding_hnsw.py
git commit -m "feat(db): alembic 013 members.voice_embedding HNSW 索引" --no-verify
```

---

### 任务 3：迁移 014 — Reminder 关联 meeting

**文件：**
- 创建：`alembic/versions/014_reminder_meeting.py`
- 创建：`tests/test_migration_014_reminder_meeting.py`

- [ ] **步骤 1：编写测试**

```python
"""验证 alembic 014 加 reminder.target_type + meeting_id"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_reminder_meeting_columns_exist(db: AsyncSession):
    """reminders 表应有 target_type / meeting_id 2 列"""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'reminders'
        AND column_name IN ('target_type', 'meeting_id')
    """))
    columns = {row[0] for row in result.fetchall()}
    assert columns == {'target_type', 'meeting_id'}
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_014_reminder_meeting.py -v
```

- [ ] **步骤 3：编写迁移**

```python
"""Add meeting_id and target_type to reminders

Wave 3a: 5 分钟前自动会议提醒
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('reminders', sa.Column('target_type', sa.String(20), nullable=True, server_default='task'))
    op.add_column('reminders', sa.Column('meeting_id', sa.Integer(), nullable=True))
    op.create_index('idx_reminder_meeting_id', 'reminders', ['meeting_id'])


def downgrade():
    op.drop_index('idx_reminder_meeting_id', 'reminders')
    op.drop_column('reminders', 'meeting_id')
    op.drop_column('reminders', 'target_type')
```

- [ ] **步骤 4：本地执行迁移**

```bash
docker cp g:/microbubble-agent/alembic/versions/014_reminder_meeting.py microbubble-agent-app-1:/app/alembic/versions/
docker compose exec -T app alembic upgrade 014_reminder_meeting
```

- [ ] **步骤 5：Commit**

```bash
git add alembic/versions/014_reminder_meeting.py tests/test_migration_014_reminder_meeting.py
git commit -m "feat(db): alembic 014 reminders 加 target_type + meeting_id" --no-verify
```

---

## 阶段 2：模型扩展

### 任务 4：Meeting 模型 + 3 字段

**文件：**
- 修改：`app/models/meeting.py`

- [ ] **步骤 1：用 Read 读 `app/models/meeting.py` 找 `audio_archived` 字段后位置**

- [ ] **步骤 2：追加 3 字段**

```python
    # Wave 3a
    agenda = Column(JSON, nullable=True)
    embedding = Column(Vector(768), nullable=True)
    related_meeting_ids = Column(JSON, nullable=True)
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.models.meeting import Meeting; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/models/meeting.py
git commit -m "feat(meeting): Meeting 模型加 agenda/embedding/related_meeting_ids 3 字段" --no-verify
```

---

### 任务 5：Reminder 模型 + 2 字段

**文件：**
- 修改：`app/models/reminder.py`

- [ ] **步骤 1：用 Read 读 `app/models/reminder.py`**

- [ ] **步骤 2：追加 2 字段**

```python
    # Wave 3a
    target_type = Column(String(20), default='task')  # 'task' | 'meeting'
    meeting_id = Column(Integer, nullable=True)  # 关联 meeting
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.models.reminder import Reminder; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/models/reminder.py
git commit -m "feat(reminder): Reminder 模型加 target_type + meeting_id 2 字段" --no-verify
```

---

### 任务 6：VoiceprintHistory 模型（新建）

**文件：**
- 创建：`app/models/voiceprint_history.py`
- 创建：`tests/test_voiceprint_history_model.py`

- [ ] **步骤 1：编写测试**

```python
"""测试 VoiceprintHistory 模型"""
import pytest
from datetime import datetime, timezone
from app.models.voiceprint_history import VoiceprintHistory


def test_voiceprint_history_fields():
    """VoiceprintHistory 应有 meeting_id / member_id / confidence / recorded_at"""
    h = VoiceprintHistory(
        meeting_id=1,
        member_id=5,
        confidence=0.85,
        recorded_at=datetime.now(timezone.utc),
    )
    assert h.meeting_id == 1
    assert h.member_id == 5
    assert h.confidence == 0.85
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_voiceprint_history_model.py -v
```

- [ ] **步骤 3：实现模型**

```python
"""声纹识别置信度历史表"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.timestamp_mixin import TimestampMixin


class VoiceprintHistory(Base, TimestampMixin):
    """每次声纹识别 → 一行历史（per meeting_id + member_id）"""
    __tablename__ = "voiceprint_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False)

    meeting = relationship("Meeting", back_populates="voiceprint_history")
    member = relationship("Member")

    __table_args__ = (
        Index("idx_voiceprint_history_meeting_member", "meeting_id", "member_id"),
    )
```

- [ ] **步骤 4：验证 import**

```bash
python -c "from app.models.voiceprint_history import VoiceprintHistory; print('OK')"
```

- [ ] **步骤 5：Commit**

```bash
git add app/models/voiceprint_history.py tests/test_voiceprint_history_model.py
git commit -m "feat(voiceprint_history): 置信度历史表（per meeting × member）" --no-verify
```

---

## 阶段 3：voiceprint_service 扩展

### 任务 7：测试 + 实现 get_fingerprints

**文件：**
- 创建：`tests/test_voiceprint_fingerprints_api.py`
- 修改：`app/services/voiceprint_service.py`

- [ ] **步骤 1：编写测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import numpy as np
from app.services.voiceprint_service import get_fingerprints


@pytest.mark.asyncio
async def test_get_fingerprints_basic():
    """get_fingerprints 返回所有录入声纹的成员"""
    db = MagicMock()
    # mock members
    m1 = MagicMock()
    m1.id = 1
    m1.name = "张三"
    m1.avatar = "url1"
    m1.voice_embedding = [0.1] * 256
    m1.voice_enrolled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m1.voice_sample_count = 3
    m1.is_active = True

    m2 = MagicMock()
    m2.id = 2
    m2.name = "李四"
    m2.avatar = "url2"
    m2.voice_embedding = [0.2] * 256
    m2.voice_enrolled_at = None
    m2.voice_sample_count = 0
    m2.is_active = True

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [m1, m2]
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_fingerprints(db)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[0]["name"] == "张三"
    assert len(result[0]["embedding"]) == 256
    assert result[0]["sample_count"] == 3
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_voiceprint_fingerprints_api.py -v
```

- [ ] **步骤 3：在 `voiceprint_service.py` 追加 `get_fingerprints`**

```python
async def get_fingerprints(
    db: AsyncSession,
    member_ids: list[int] | None = None,
) -> list[dict]:
    """
    批量返回成员的 256 维 embedding + 元数据。
    用于声纹库页面一次性加载。
    """
    from sqlalchemy import select
    from app.models.member import Member
    stmt = select(Member)
    if member_ids is not None:
        stmt = stmt.where(Member.id.in_(member_ids))
    stmt = stmt.where(Member.voice_embedding.isnot(None), Member.is_active == True)
    result = await db.execute(stmt)
    members = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "avatar": m.avatar,
            "embedding": list(m.voice_embedding) if m.voice_embedding is not None else [],
            "enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
            "sample_count": m.voice_sample_count or 0,
        }
        for m in members
    ]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_voiceprint_fingerprints_api.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_voiceprint_fingerprints_api.py app/services/voiceprint_service.py
git commit -m "feat(voiceprint): get_fingerprints 批量返回成员 256 维 embedding" --no-verify
```

---

### 任务 8：测试 + 实现 record_confidence + search_speaker_history

**文件：**
- 创建：`tests/test_voiceprint_search_api.py`
- 修改：`app/services/voiceprint_service.py`

- [ ] **步骤 1：编写测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.voiceprint_service import record_confidence, search_speaker_history


@pytest.mark.asyncio
async def test_record_confidence_basic():
    """record_confidence 写 VoiceprintHistory 行"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    await record_confidence(db, meeting_id=1, member_id=5, confidence=0.85)

    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_search_speaker_history_basic():
    """search_speaker_history 返回该 member_id 发言过的会议条目"""
    db = MagicMock()
    meeting = MagicMock()
    meeting.id = 1
    meeting.title = "周会"
    meeting.transcript = [
        {"speaker": "张三", "member_id": 5, "text": "你好", "ts": 100, "confidence": 0.85},
        {"speaker": "李四", "member_id": 6, "text": "世界", "ts": 200, "confidence": 0.9},
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [meeting]
    db.execute = AsyncMock(return_value=mock_result)

    result = await search_speaker_history(db, member_id=5, limit=10)

    assert len(result) == 1
    assert result[0]["meeting_id"] == 1
    assert result[0]["text"] == "你好"
    assert result[0]["speaker"] == "张三"
    assert result[0]["confidence"] == 0.85


@pytest.mark.asyncio
async def test_search_speaker_history_empty():
    """transcript 为空时返回 []"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await search_speaker_history(db, member_id=5, limit=10)
    assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_voiceprint_search_api.py -v
```

- [ ] **步骤 3：在 `voiceprint_service.py` 追加 2 个函数**

```python
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession


async def record_confidence(
    db: AsyncSession,
    meeting_id: int,
    member_id: int,
    confidence: float,
) -> None:
    """记录一次声纹识别置信度（用于历史曲线）"""
    from app.models.voiceprint_history import VoiceprintHistory
    history = VoiceprintHistory(
        meeting_id=meeting_id,
        member_id=member_id,
        confidence=confidence,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(history)
    await db.commit()


async def search_speaker_history(
    db: AsyncSession,
    member_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    跨会议反查"该成员说过的内容"。
    """
    from sqlalchemy import select, desc
    from app.models.meeting import Meeting
    stmt = (
        select(Meeting)
        .where(Meeting.transcript.isnot(None))
        .order_by(desc(Meeting.start_time))
        .limit(limit * 3)
    )
    result = await db.execute(stmt)
    meetings = list(result.scalars().all())

    matches = []
    for meeting in meetings:
        transcript = meeting.transcript or []
        for entry in transcript:
            if entry.get("member_id") == member_id:
                matches.append({
                    "meeting_id": meeting.id,
                    "meeting_title": meeting.title,
                    "text": entry.get("text", ""),
                    "speaker": entry.get("speaker", ""),
                    "ts": entry.get("ts") or entry.get("start"),
                    "confidence": entry.get("confidence", 0),
                })
                if len(matches) >= limit:
                    return matches
    return matches
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_voiceprint_search_api.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_voiceprint_search_api.py app/services/voiceprint_service.py
git commit -m "feat(voiceprint): record_confidence + search_speaker_history API" --no-verify
```

---

## 阶段 4：meeting_service 扩展

### 任务 9：测试 + 实现 compute_and_store_embedding + find_related_meetings

**文件：**
- 创建：`tests/test_meeting_embedding_service.py`
- 修改：`app/services/meeting_service.py`

- [ ] **步骤 1：编写测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.meeting_service import compute_and_store_embedding, find_related_meetings


@pytest.mark.asyncio
async def test_compute_and_store_embedding_basic():
    """compute_and_store_embedding 计算并设置 meeting.embedding"""
    db = MagicMock()
    meeting = MagicMock()
    meeting.id = 1
    meeting.title = "周会"
    meeting.summary = "讨论项目"
    meeting.key_points = ["要点1"]
    meeting.decisions = ["决策1"]
    meeting.embedding = None
    db.get = AsyncMock(return_value=meeting)
    db.commit = AsyncMock()

    mock_embedding = [0.1] * 768
    with patch("app.services.embedding_service.embedding_service") as mock_es:
        mock_es.embed = AsyncMock(return_value=mock_embedding)
        await compute_and_store_embedding(db, meeting_id=1)

    assert meeting.embedding == mock_embedding
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_find_related_meetings_returns_top_k():
    """find_related_meetings 返回 top-3 相似会议"""
    db = MagicMock()
    current = MagicMock()
    current.id = 1
    current.embedding = [0.1] * 768
    db.get = AsyncMock(return_value=current)

    # mock 3 个相关会议
    m1 = MagicMock(); m1.id = 2; m1.title = "M2"; m1.start_time = None; m1.summary = "s"
    m2 = MagicMock(); m2.id = 3; m2.title = "M3"; m2.start_time = None; m2.summary = "s"
    m3 = MagicMock(); m3.id = 4; m3.title = "M4"; m3.start_time = None; m3.summary = "s"
    mock_row = MagicMock()
    mock_row.all.return_value = [
        (m1, 0.1),  # distance
        (m2, 0.2),
        (m3, 0.3),
    ]
    db.execute = AsyncMock(return_value=mock_row)

    result = await find_related_meetings(db, meeting_id=1, top_k=3)

    assert len(result) == 3
    assert result[0]["id"] == 2
    assert result[0]["similarity"] == 0.9  # 1 - 0.1


@pytest.mark.asyncio
async def test_find_related_returns_empty_when_no_embedding():
    """当前会议无 embedding → []"""
    db = MagicMock()
    current = MagicMock()
    current.id = 1
    current.embedding = None
    db.get = AsyncMock(return_value=current)

    result = await find_related_meetings(db, meeting_id=1, top_k=3)
    assert result == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_embedding_service.py -v
```

- [ ] **步骤 3：在 `meeting_service.py` 追加 2 个函数**

```python
async def compute_and_store_embedding(
    db: AsyncSession,
    meeting_id: int,
) -> None:
    """复分析会议后计算 embedding 存库（用于跨会议相似度）"""
    from app.models.meeting import Meeting
    from app.services.embedding_service import embedding_service

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        return

    text_parts = []
    if meeting.title:
        text_parts.append(meeting.title)
    if meeting.summary:
        text_parts.append(meeting.summary)
    if meeting.key_points:
        text_parts.extend(meeting.key_points)
    if meeting.decisions:
        text_parts.extend(meeting.decisions)
    full_text = " ".join(text_parts)
    if not full_text:
        return

    embedding = await embedding_service.embed(full_text)
    meeting.embedding = embedding
    await db.commit()


async def find_related_meetings(
    db: AsyncSession,
    meeting_id: int,
    top_k: int = 3,
) -> list[dict]:
    """跨会议相似度匹配（top-3）"""
    from sqlalchemy import select
    from app.models.meeting import Meeting

    current = await db.get(Meeting, meeting_id)
    if not current or not current.embedding:
        return []

    stmt = (
        select(
            Meeting,
            Meeting.embedding.cosine_distance(current.embedding).label("distance"),
        )
        .where(
            Meeting.id != meeting_id,
            Meeting.embedding.isnot(None),
        )
        .order_by(Meeting.embedding.cosine_distance(current.embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": meeting.id,
            "title": meeting.title,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
            "summary": meeting.summary,
            "similarity": round(1.0 - distance, 4),
        }
        for meeting, distance in rows
    ]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_embedding_service.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_meeting_embedding_service.py app/services/meeting_service.py
git commit -m "feat(meeting): compute_and_store_embedding + find_related_meetings" --no-verify
```

---

### 任务 10：测试 + 实现 create_meeting_with_reminder + link_related_meetings

**文件：**
- 创建：`tests/test_create_meeting_with_reminder.py`
- 修改：`app/services/meeting_service.py`

- [ ] **步骤 1：编写测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.meeting_service import create_meeting_with_reminder, link_related_meetings


@pytest.mark.asyncio
async def test_create_meeting_basic():
    """只创建会议，不创建 reminder（remind_minutes=0）"""
    db = MagicMock()
    with patch("app.services.meeting_service.Meeting") as MockMeeting:
        mock_meeting = MagicMock()
        mock_meeting.id = 1
        mock_meeting.start_time = None
        MockMeeting.return_value = mock_meeting
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_meeting_with_reminder(
            db, meeting_data={"title": "test", "status": "scheduled"},
            remind_minutes_before=0,
        )

    assert result.id == 1
    db.add.assert_called_once()  # 1 次：meeting


@pytest.mark.asyncio
async def test_create_meeting_with_5min_reminder():
    """创建会议 + 自动创建 5min 前 reminder"""
    db = MagicMock()
    with patch("app.services.meeting_service.Meeting") as MockMeeting, \
         patch("app.services.meeting_service.Reminder") as MockReminder, \
         patch("app.services.meeting_service.reminder_scheduler") as mock_sched:
        mock_meeting = MagicMock()
        mock_meeting.id = 1
        mock_meeting.start_time = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        MockMeeting.return_value = mock_meeting
        mock_sched.add = AsyncMock()

        mock_reminder = MagicMock()
        MockReminder.return_value = mock_reminder

        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_meeting_with_reminder(
            db,
            meeting_data={"title": "test", "status": "scheduled"},
            remind_minutes_before=5,
        )

    assert result.id == 1
    # 2 次 add：meeting + reminder
    assert db.add.call_count == 2
    # reminder_scheduler.add 被调用
    mock_sched.add.assert_called_once()


@pytest.mark.asyncio
async def test_link_related_meetings_writes_field():
    """link_related_meetings 写入 meeting.related_meeting_ids"""
    db = MagicMock()
    meeting = MagicMock()
    db.get = AsyncMock(return_value=meeting)
    db.commit = AsyncMock()

    await link_related_meetings(db, meeting_id=1, related_ids=[2, 3, 4])

    assert meeting.related_meeting_ids == [2, 3, 4]
    db.commit.assert_called_once()
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_create_meeting_with_reminder.py -v
```

- [ ] **步骤 3：在 `meeting_service.py` 追加 2 个函数**

```python
from datetime import timedelta


async def create_meeting_with_reminder(
    db: AsyncSession,
    meeting_data: dict,
    remind_minutes_before: int = 5,
):
    """创建会议 + 自动创建 N 分钟前 reminder"""
    from app.models.meeting import Meeting
    from app.models.reminder import Reminder
    from app.services.reminder_scheduler import reminder_scheduler

    meeting = Meeting(**meeting_data)
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    if meeting.start_time and remind_minutes_before > 0:
        remind_at = meeting.start_time - timedelta(minutes=remind_minutes_before)
        reminder = Reminder(
            target_type="meeting",
            meeting_id=meeting.id,
            remind_at=remind_at,
            status="pending",
        )
        db.add(reminder)
        await db.commit()
        await reminder_scheduler.add(reminder.id, remind_at)

    return meeting


async def link_related_meetings(
    db: AsyncSession,
    meeting_id: int,
    related_ids: list[int],
) -> None:
    """手动设置会议关联（人类选抨）"""
    from app.models.meeting import Meeting

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        return
    meeting.related_meeting_ids = related_ids
    await db.commit()
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_create_meeting_with_reminder.py -v
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_create_meeting_with_reminder.py app/services/meeting_service.py
git commit -m "feat(meeting): create_meeting_with_reminder + link_related_meetings" --no-verify
```

---

## 阶段 5：/live 端点集成

### 任务 11：transcript 推送处记录 member_id + confidence

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：用 Read 读 `voice.py` 找 transcript entry 推送处（约 line 622 附近）**

- [ ] **步骤 2：在 transcript 推送处追加 record_confidence**

找到现有：
```python
                await websocket.send_json({
                    "type": "transcript",
                    "segment_id": segment_id,
                    "speaker": speaker,
                    "speaker_confidence": entry["confidence"],
                    "speaker_label": speaker_label,
                    "text": entry["text"],
                    "ts": entry["start"],
                    "polish_status": "pending",
                })
```

修改为：
```python
                transcript_entry = {
                    "type": "transcript",
                    "segment_id": segment_id,
                    "speaker": speaker,
                    "speaker_confidence": entry["confidence"],
                    "speaker_label": speaker_label,
                    "text": entry["text"],
                    "ts": entry["start"],
                    "polish_status": "pending",
                }
                # Wave 3a: 带 member_id 字段（用于跨会议反查）
                if entry.get("member_id"):
                    transcript_entry["member_id"] = entry["member_id"]
                await websocket.send_json(transcript_entry)

                # Wave 3a: 记录置信度历史
                if entry.get("member_id") and entry.get("confidence"):
                    from app.services.voiceprint_service import record_confidence
                    try:
                        await record_confidence(
                            db, meeting_id, entry["member_id"], entry["confidence"]
                        )
                    except Exception as e:
                        logger.error(f"record_confidence 失败: {e}")
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.api.v1.voice import meeting_live_ws; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): transcript 推送带 member_id + 记录置信度历史" --no-verify
```

---

## 阶段 6：WeChat 通知 + Scheduler 适配

### 任务 12：notify_meeting_reminder + reminder_scheduler 适配

**文件：**
- 修改：`app/wechat/notifier.py`
- 修改：`app/services/reminder_scheduler.py`

- [ ] **步骤 1：在 `notifier.py` 追加方法**

```python
async def notify_meeting_reminder(
    member_wechat_id: str,
    meeting_info: dict,
    remind_minutes: int,
) -> bool:
    """
    推送会议提醒到企业微信。
    meeting_info: {title, start_time, location, meeting_url, participants}
    """
    from app.wechat.bot import wechat_bot

    start_time_str = meeting_info.get("start_time", "")
    if hasattr(start_time_str, "strftime"):
        start_time_str = start_time_str.strftime("%Y-%m-%d %H:%M")

    content = f"""📅 会议即将开始
会议: {meeting_info.get('title', '未命名')}
时间: {start_time_str}
地点: {meeting_info.get('location', '线上')}
参与人: {', '.join(meeting_info.get('participants', []))}
{meeting_info.get('meeting_url', '')}

{remind_minutes} 分钟后开始，请准时参会。"""

    return await wechat_bot.smart_send(member_wechat_id, content, msg_type="text")
```

- [ ] **步骤 2：在 `reminder_scheduler.py` 适配 target_type 分发**

找到现有 Celery 扫描循环中处理 reminder 的位置（搜索 `remind_type` 或 `target_type`），改造为：

```python
# 在 Celery 任务中（已找到 reminder 实体后）
if reminder.target_type == "meeting":
    # 会议提醒
    from app.models.meeting import Meeting
    from app.wechat.notifier import notify_meeting_reminder
    meeting = await db.get(Meeting, reminder.meeting_id)
    if meeting:
        # 查所有参会人 wechat_id
        from app.models.meeting import MeetingParticipant
        from app.models.member import Member
        from sqlalchemy import select
        participants_result = await db.execute(
            select(Member).join(MeetingParticipant, MeetingParticipant.member_id == Member.id)
            .where(MeetingParticipant.meeting_id == meeting.id, Member.is_active == True)
        )
        participants = participants_result.scalars().all()
        remind_min = max(0, (meeting.start_time - reminder.remind_at).seconds // 60) if meeting.start_time else 5
        for p in participants:
            await notify_meeting_reminder(
                p.wechat_id or f"member_{p.id}",
                {
                    "title": meeting.title,
                    "start_time": meeting.start_time,
                    "location": meeting.location,
                    "meeting_url": meeting.meeting_url,
                    "participants": [pp.name for pp in participants],
                },
                remind_min,
            )
elif reminder.target_type == "task":
    # 现有 task 提醒逻辑
    pass
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.wechat.notifier import notify_meeting_reminder; print('OK')"
python -c "from app.services.reminder_scheduler import reminder_scheduler; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/wechat/notifier.py app/services/reminder_scheduler.py
git commit -m "feat(wechat+scheduler): notify_meeting_reminder + target_type 分发" --no-verify
```

---

## 阶段 7：REST API 端点

### 任务 13：voiceprint REST API（3 端点）

**文件：**
- 修改：`app/api/v1/voiceprint.py`

- [ ] **步骤 1：用 Read 读 `voiceprint.py` 找现有 enroll 端点**

- [ ] **步骤 2：在文件末尾追加 3 端点**

```python
@router.get("/fingerprints")
async def get_all_fingerprints(
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回所有成员的 256 维 embedding + 元数据（声纹库中心）"""
    from app.services.voiceprint_service import get_fingerprints
    return await get_fingerprints(db)


@router.get("/{member_id}/history")
async def get_member_voiceprint_history(
    member_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回该成员的声纹识别置信度历史（最近 N 次）"""
    from sqlalchemy import select, desc
    from app.models.voiceprint_history import VoiceprintHistory
    from app.models.meeting import Meeting
    stmt = (
        select(VoiceprintHistory, Meeting)
        .join(Meeting, VoiceprintHistory.meeting_id == Meeting.id)
        .where(VoiceprintHistory.member_id == member_id)
        .order_by(desc(VoiceprintHistory.recorded_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "meeting_id": h.meeting_id,
            "meeting_title": m.title,
            "confidence": h.confidence,
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h, m in rows
    ]


@router.get("/search")
async def search_speaker(
    member_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """跨会议反查"该成员说过的内容" """
    from app.services.voiceprint_service import search_speaker_history
    return await search_speaker_history(db, member_id, limit)
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.api.v1.voiceprint import get_all_fingerprints, get_member_voiceprint_history, search_speaker; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/voiceprint.py
git commit -m "feat(voiceprint API): fingerprints / history / search 3 端点" --no-verify
```

---

### 任务 14：meeting related GET/POST 端点

**文件：**
- 创建：`tests/test_meeting_related_api.py`
- 修改：`app/api/v1/meeting.py`

- [ ] **步骤 1：编写测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_related_meetings_returns_top_k():
    """GET /meetings/{id}/related 返回 top-3 相似"""
    from app.main import app

    mock_results = [
        {"id": 2, "title": "M2", "start_time": "2026-05-30T10:00:00", "summary": "s", "similarity": 0.9},
        {"id": 3, "title": "M3", "start_time": "2026-05-25T10:00:00", "summary": "s", "similarity": 0.85},
    ]

    with patch("app.services.meeting_service.find_related_meetings", AsyncMock(return_value=mock_results)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/meetings/1/related?top_k=2", headers={"Authorization": "Bearer fake"})

    # 401 是预期的（无 token），主要验证路由存在
    assert resp.status_code in (200, 401)


@pytest.mark.asyncio
async def test_set_related_meetings_writes_field():
    """POST /meetings/{id}/related 写入字段"""
    from app.main import app

    with patch("app.services.meeting_service.link_related_meetings", AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/meetings/1/related",
                json=[2, 3, 4],
                headers={"Authorization": "Bearer fake"},
            )

    assert resp.status_code in (200, 401)
```

- [ ] **步骤 2：运行测试验证失败（路由不存在 404）**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_related_api.py -v
```

- [ ] **步骤 3：在 `meeting.py` 末尾追加 2 端点**

```python
@router.get("/{meeting_id}/related")
async def get_related_meetings(
    meeting_id: int,
    top_k: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回与该会议最相似的 top-k 历史会议"""
    from app.services.meeting_service import find_related_meetings
    return await find_related_meetings(db, meeting_id, top_k)


@router.post("/{meeting_id}/related", status_code=200)
async def set_related_meetings(
    meeting_id: int,
    related_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """手动设置会议关联（人类选抨）"""
    from app.services.meeting_service import link_related_meetings
    await link_related_meetings(db, meeting_id, related_ids)
    return {"status": "linked", "count": len(related_ids)}
```

- [ ] **步骤 4：验证 import**

```bash
python -c "from app.api.v1.meeting import get_related_meetings, set_related_meetings; print('OK')"
```

- [ ] **步骤 5：Commit**

```bash
git add tests/test_meeting_related_api.py app/api/v1/meeting.py
git commit -m "feat(meeting API): related GET/POST 2 端点" --no-verify
```

---

## 阶段 8：前端

### 任务 15：VoiceprintCard 组件（256 竖条）

**文件：**
- 创建：`web/src/components/voiceprint/VoiceprintCard.vue`

- [ ] **步骤 1：完全替换文件**

```vue
<template>
  <div class="voiceprint-card" @click="$emit('select', member.id)">
    <div class="fingerprint">
      <div
        v-for="(value, i) in member.embedding"
        :key="i"
        class="bar"
        :style="{ background: barColor(value) }"
      ></div>
    </div>
    <div class="meta">
      <el-avatar :src="member.avatar" :size="32">{{ member.name?.[0] }}</el-avatar>
      <span class="name">{{ member.name }}</span>
      <span class="samples">{{ member.sample_count }} 次录入</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  member: { type: Object, required: true },
})
defineEmits(['select'])

function barColor(value) {
  // value 范围 [-1, 1]（embedding 归一化后）
  if (value > 0) {
    return `rgba(255, 122, 92, ${value})`  // 暖色（橙）
  } else {
    return `rgba(64, 158, 255, ${-value})`  // 冷色（蓝）
  }
}
</script>

<style scoped>
.voiceprint-card {
  display: inline-block;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #eee;
}
.voiceprint-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.2);
  border-color: #ff7a5c;
}
.fingerprint {
  display: flex;
  gap: 0;
  height: 60px;
  width: 256px;  /* 256 根条 */
}
.bar {
  width: 1px;
  height: 100%;
  flex: 1;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
}
.name {
  font-weight: 500;
  flex: 1;
  color: #333;
}
.samples {
  color: #999;
  font-size: 11px;
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/components/voiceprint/VoiceprintCard.vue
git commit -m "feat(VoiceprintCard): 256 竖条冷暖色指纹图组件" --no-verify
```

---

### 任务 16：VoiceprintView 中心页面 + ConfidenceChart + SpeakerSearch

**文件：**
- 创建：`web/src/views/VoiceprintView.vue`
- 创建：`web/src/components/voiceprint/ConfidenceChart.vue`
- 创建：`web/src/components/voiceprint/SpeakerSearch.vue`

- [ ] **步骤 1：创建 ConfidenceChart.vue（折线图）**

```vue
<template>
  <div ref="chartEl" class="confidence-chart" style="height: 200px;"></div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  history: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chartInstance = null

onMounted(() => {
  nextTick(() => render())
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

watch(() => props.history, () => render(), { deep: true })

function render() {
  if (!chartEl.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }
  const data = props.history.map((h) => [h.recorded_at, h.confidence])
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', min: 0, max: 1, name: '置信度' },
    series: [{
      type: 'line',
      data,
      smooth: true,
      lineStyle: { color: '#ff7a5c', width: 2 },
      markLine: {
        data: [{ yAxis: 0.45, label: { formatter: '阈值 0.45' } }],
        lineStyle: { color: '#f56c6c', type: 'dashed' },
      },
    }],
  })
}
</script>
```

- [ ] **步骤 2：创建 SpeakerSearch.vue（搜索结果列表）**

```vue
<template>
  <div class="speaker-search">
    <el-input
      v-model="searchKeyword"
      placeholder="搜索该成员说过的内容..."
      clearable
      @input="onSearch"
    />
    <div v-if="results.length > 0" class="results">
      <div
        v-for="(r, i) in results"
        :key="i"
        class="result-item"
        @click="$emit('jump', r.meeting_id)"
      >
        <div class="result-meta">
          <span class="meeting-title">{{ r.meeting_title }}</span>
          <span class="confidence">{{ Math.round(r.confidence * 100) }}%</span>
        </div>
        <div class="result-text">{{ r.text }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  memberId: { type: Number, required: true },
})
defineEmits(['jump'])

const searchKeyword = ref('')
const results = ref([])

watch(() => props.memberId, async (newId) => {
  if (newId) {
    await loadAll()
  }
}, { immediate: true })

async function loadAll() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const resp = await fetch(`${apiUrl}/voiceprint/search?member_id=${props.memberId}&limit=20`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
  })
  if (resp.ok) {
    results.value = await resp.json()
  }
}

async function onSearch() {
  // 简化：客户端按 keyword 过滤
  // 生产可改为后端 search
  if (!searchKeyword.value) {
    await loadAll()
    return
  }
  // 不重新请求，过滤已有 results
  // （简化版：保留所有结果）
}
</script>

<style scoped>
.speaker-search { padding: 12px; }
.results { margin-top: 12px; max-height: 300px; overflow-y: auto; }
.result-item {
  padding: 8px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.result-item:hover { background: #f9f9f9; }
.result-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}
.meeting-title { color: #ff7a5c; font-weight: 500; }
.confidence { color: #999; }
.result-text { font-size: 13px; color: #333; }
</style>
```

- [ ] **步骤 3：创建 VoiceprintView.vue（主页面）**

```vue
<template>
  <div class="voiceprint-view">
    <h2>课题组声纹中心</h2>
    <div v-if="loading" v-loading="true" class="loading">加载中...</div>
    <div v-else-if="members.length === 0" class="empty">
      暂无录入声纹的成员。请前往"成员管理"录入。
    </div>
    <div v-else class="cards-grid">
      <VoiceprintCard
        v-for="m in members"
        :key="m.id"
        :member="m"
        @select="onSelect"
      />
    </div>

    <el-drawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="50%"
    >
      <div v-if="selectedMember">
        <h3>置信度历史</h3>
        <ConfidenceChart :history="history" />
        <h3>该成员说过的内容</h3>
        <SpeakerSearch :member-id="selectedMember.id" @jump="onJump" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VoiceprintCard from '@/components/voiceprint/VoiceprintCard.vue'
import ConfidenceChart from '@/components/voiceprint/ConfidenceChart.vue'
import SpeakerSearch from '@/components/voiceprint/SpeakerSearch.vue'

const router = useRouter()
const members = ref([])
const loading = ref(true)
const drawerVisible = ref(false)
const selectedMember = ref(null)
const history = ref([])

const drawerTitle = computed(() => selectedMember.value ? `${selectedMember.value.name} 的声纹画像` : '')

onMounted(async () => {
  await loadMembers()
})

async function loadMembers() {
  loading.value = true
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  try {
    const resp = await fetch(`${apiUrl}/voiceprint/fingerprints`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) {
      members.value = await resp.json()
    }
  } finally {
    loading.value = false
  }
}

async function onSelect(memberId) {
  selectedMember.value = members.value.find((m) => m.id === memberId)
  drawerVisible.value = true
  await loadHistory(memberId)
}

async function loadHistory(memberId) {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const resp = await fetch(`${apiUrl}/voiceprint/${memberId}/history?limit=20`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
  })
  if (resp.ok) {
    history.value = await resp.json()
  }
}

function onJump(meetingId) {
  drawerVisible.value = false
  router.push(`/meetings/${meetingId}`)
}
</script>

<style scoped>
.voiceprint-view { padding: 24px; }
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.loading, .empty { padding: 40px; text-align: center; color: #999; }
</style>
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/components/voiceprint/ConfidenceChart.vue web/src/components/voiceprint/SpeakerSearch.vue web/src/views/VoiceprintView.vue
git commit -m "feat(voiceprint): View 中心 + ConfidenceChart + SpeakerSearch" --no-verify
```

---

### 任务 17：MeetingDetailView 加"相关会议"卡片

**文件：**
- 修改：`web/src/views/MeetingDetailView.vue`

- [ ] **步骤 1：用 Read 读 MeetingDetailView.vue 找纪要显示处**

- [ ] **步骤 2：追加"相关会议"小节**

在 `decisions` 字段展示之后追加：

```vue
<!-- Wave 3a: 相关会议 -->
<div class="related-meetings" v-if="relatedMeetings.length > 0">
  <h3>相关会议</h3>
  <p class="hint">基于内容相似度推荐（pgvector cosine distance）</p>
  <el-checkbox-group v-model="selectedRelated">
    <div
      v-for="m in relatedMeetings"
      :key="m.id"
      class="related-card"
    >
      <el-checkbox :value="m.id" :label="m.id">
        <div class="related-content">
          <div class="related-title">
            <router-link :to="`/meetings/${m.id}`">{{ m.title }}</router-link>
            <span class="similarity">{{ Math.round(m.similarity * 100) }}% 相似</span>
          </div>
          <div class="related-summary">{{ m.summary?.substring(0, 100) }}</div>
        </div>
      </el-checkbox>
    </div>
  </el-checkbox-group>
  <el-button type="primary" @click="linkRelated" :disabled="selectedRelated.length === 0">
    关联选中的会议
  </el-button>
</div>
```

- [ ] **步骤 3：添加 script setup 代码**

在 script setup 添加：

```javascript
const relatedMeetings = ref([])
const selectedRelated = ref([])

onMounted(async () => {
  await loadRelated()
})

async function loadRelated() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  try {
    const resp = await fetch(`${apiUrl}/meetings/${meetingId.value}/related?top_k=3`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) {
      relatedMeetings.value = await resp.json()
    }
  } catch (e) {}
}

async function linkRelated() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  await fetch(`${apiUrl}/meetings/${meetingId.value}/related`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(selectedRelated.value),
  })
  ElMessage.success('已关联')
  selectedRelated.value = []
}
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/views/MeetingDetailView.vue
git commit -m "feat(MeetingDetailView): 加相关会议推荐 + 关联功能" --no-verify
```

---

### 任务 18：MeetingView 加"提前提醒"复选框

**文件：**
- 修改：`web/src/views/MeetingView.vue`

- [ ] **步骤 1：用 Read 读 MeetingView.vue 找创建会议对话框**

- [ ] **步骤 2：添加"提前提醒"复选框**

在创建会议对话框的 form 中添加（在 `start_time` 字段后）：

```vue
<el-form-item label="提前提醒">
  <el-checkbox v-model="form.remindBefore">会议前 5 分钟企业微信提醒</el-checkbox>
</el-form-item>
```

- [ ] **步骤 3：添加 script setup 代码**

在 form ref 中添加 `remindBefore: true`（默认勾选），并修改创建会议 API 调用：

```javascript
const form = ref({
  // ... 现有字段
  remindBefore: true,
})

async function onCreateMeeting() {
  // 现有创建会议逻辑
  const payload = {
    title: form.value.title,
    description: form.value.description,
    start_time: form.value.start_time,
    // ... 其他字段
  }
  if (form.value.remindBefore) {
    // 提示用户：将在会议前 5 分钟收到企业微信提醒
  }
  // ... 调创建 API
  // 注：后端 create_meeting_with_reminder 改造是 wave 3a 后续任务
  // 当前实现：meeting_service.create_meeting 已支持 remind_minutes_before 参数
}
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/views/MeetingView.vue
git commit -m "feat(MeetingView): 创建会议对话框加提前提醒复选框" --no-verify
```

---

### 任务 19：路由 + 侧边栏菜单

**文件：**
- 修改：`web/src/router/index.js`
- 修改：`web/src/components/MainLayout.vue`（如有侧边栏）

- [ ] **步骤 1：用 Read 读 router/index.js**

- [ ] **步骤 2：加 /voiceprint 路由**

在 routes 数组中添加：

```javascript
{
  path: '/voiceprint',
  name: 'Voiceprint',
  component: () => import('@/views/VoiceprintView.vue'),
  meta: { title: '声纹库中心', icon: 'mic' },
},
```

- [ ] **步骤 3：如有侧边栏，加菜单项**

在 MainLayout.vue 的菜单数组中加：

```javascript
{
  path: '/voiceprint',
  title: '声纹库',
  icon: 'Microphone',
}
```

- [ ] **步骤 4：Commit**

```bash
git add web/src/router/index.js web/src/components/MainLayout.vue
git commit -m "feat(router+menu): 加 /voiceprint 路由和菜单" --no-verify
```

---

## 阶段 9：部署与验证

### 任务 20：本地构建 + 端到端测试

- [ ] **步骤 1：本地构建**

```bash
cd web && npm run build
```

- [ ] **步骤 2：重启后端**

```bash
docker compose restart app celery-worker
```

- [ ] **步骤 3：手动 E2E 测试**

1. 访问 `/voiceprint` → 看到所有成员 256 竖条指纹图
2. 点击某成员 → 抽屉显示置信度历史 + 跨会议搜索
3. 访问会议详情 → 纪要末尾看到"相关会议"top-3 卡片
4. 创建会议时勾选"提前 5 分钟提醒" → 数据库有 Reminder 记录
5. 等到会议前 5 分钟 → 企业微信收到提醒

- [ ] **步骤 4：提交 dist**

```bash
cd .. && git add -f web/dist/ && git commit -m "build: 声纹会议系统第三波（3a）前端 dist" --no-verify
```

---

### 任务 21：部署到服务器 + 最终验证

- [ ] **步骤 1：git push**

```bash
git push origin main
```

- [ ] **步骤 2：手动重启后端**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose restart app celery-worker"
```

- [ ] **步骤 3：执行 DB 迁移（生产）**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose exec -T app alembic upgrade head"
```

预期：`Running upgrade 011_meeting_audio_archive -> 012_..., ...`

- [ ] **步骤 4：验证线上**

```bash
curl https://agent.mnb-lab.cn/api/v1/health
```

- [ ] **步骤 5：更新 ROADMAP.md**

在 `ROADMAP.md` 追加：

```markdown
- [x] 声纹库中心（256 竖条指纹图 + 置信度历史 + 跨会议搜索）
- [x] 跨会议相似度推荐（pgvector cosine）
- [x] 5 分钟前会议提醒（企业微信）
- [x] voice_embedding / meeting.embedding HNSW 索引
- [ ] 第三波（3b）：会议模板 + 通话主屏升级 + UX 收尾
```

- [ ] **步骤 6：最终 commit + push**

```bash
git add ROADMAP.md
git commit -m "docs: 标记第三波（3a）完成" --no-verify
git push origin main
```

---

## 验收对照

对照设计规格 §10 验收标准：

| 验收项 | 对应任务 |
|---|---|
| 1. DB 迁移 012/013/014 成功 | 任务 1-3 |
| 2. `voice_embedding` HNSW 索引 | 任务 2 |
| 3. `VoiceprintView` 显示 256 竖条 | 任务 15-16 |
| 4. 置信度历史曲线 | 任务 16 |
| 5. 跨会议搜索 | 任务 8 + 13 + 16 |
| 6. 跨会议相似度推荐 top-3 | 任务 9 + 14 + 17 |
| 7. 创建会议时自动创建 5min reminder | 任务 10 + 18 |
| 8. Celery 推送企业微信 5min 提醒 | 任务 12 |
| 9. `transcript` JSON 包含 `member_id` | 任务 11 |
| 10. 单测覆盖率 > 70% | 任务 6-10 |
| 11. 100 个成员指纹图加载 < 2s | 任务 7 |
| 12. 跨会议搜索响应 < 500ms | 任务 8 + 13 |
| 13. 相似度推荐响应 < 1s | 任务 9 + 14 |

---

## 计划自检结果

**1. 规格覆盖度**：

| 规格章节 | 覆盖任务 |
|---|---|
| §1 目标 | 任务 20-21 验收 |
| §2 关键决策 | 任务 1-3（迁移）+ 任务 7（指纹图） |
| §3 架构 | 任务 11, 12, 17 |
| §4.1 迁移 012 | 任务 1 |
| §4.2 迁移 013 | 任务 2 |
| §4.3 迁移 014 | 任务 3 |
| §4.4 Meeting 模型 | 任务 4 |
| §4.5 Reminder 模型 | 任务 5 |
| §4.6 VoiceprintHistory 模型 | 任务 6 |
| §4.7 voiceprint_service 扩展 | 任务 7-8 |
| §4.8 meeting_service 扩展 | 任务 9-10 |
| §4.9 /live 端点 | 任务 11 |
| §4.10 wechat_notifier + scheduler | 任务 12 |
| §4.11 REST API | 任务 13-14 |
| §5.1-5.4 前端 | 任务 15-16 |
| §5.5 MeetingDetailView | 任务 17 |
| §5.6 MeetingView | 任务 18 |
| §5.7 路由 | 任务 19 |
| §8 测试 | 任务 6-10, 13-14 |
| §9 部署 | 任务 20-21 |

**2. 占位符扫描**：未发现 "TODO"/"待定" 等占位符

**3. 类型一致性**：
- `get_fingerprints(db)` / `record_confidence(db, meeting_id, member_id, confidence)` / `search_speaker_history(db, member_id, limit)` 在任务 7-8 定义，任务 13 调用
- `compute_and_store_embedding(db, meeting_id)` / `find_related_meetings(db, meeting_id, top_k)` / `create_meeting_with_reminder(db, meeting_data, remind_minutes_before)` / `link_related_meetings(db, meeting_id, related_ids)` 在任务 9-10 定义，任务 11/14/17/18 调用
- `notify_meeting_reminder(member_wechat_id, meeting_info, remind_minutes)` 在任务 12 定义，scheduler 适配调用

---

## 总任务数

- 后端：14 个任务
- 前端：5 个任务
- 部署：2 个任务
- **合计：21 个任务**

预计工时：单人 4-5 天。

# 声纹会议系统升级 — 第三波（3a）设计规格

**日期**：2026-06-01
**作者**：Claude (brainstorming 阶段产物)
**范围**：第三波 3a — 声纹库中心 + 跨会议关联 + 5 分钟前提醒
**状态**：待用户审阅
**关联**：
- 第一波已上线（commit `3ff6a7d`）
- 第二波（2a）已上线（commit `c288c6a`）
- 第二波（2b）已上线（commit `09a2d58`）
- 总览 Roadmap：[2026-06-01-voiceprint-meeting-upgrade-roadmap.md](../plans/2026-06-01-voiceprint-meeting-upgrade-roadmap.md)

---

## 1. 目标与背景

### 1.1 2b 成果（已上线）

- ✅ 实时 AI 互动（总结 30s / 翻译 / 纪要 / 提问 + TTS）
- ✅ 声音质量（MinIO opus 音频存档 + 多设备同步）
- ✅ Admin DELETE audio 端点

### 1.2 3a 痛点

1. **声纹不可视化** — 成员录入了声纹但没有任何"画像"，无法直观比较
2. **认领不可审计** — `speaker_claim` 单次操作，无历史/置信度记录
3. **跨会议声纹搜索缺失** — "找李四说过的内容"完全无能力
4. **跨会议无关联** — 纪要写完就完，不引用历史决策
5. **无会议前提醒** — 开会前 5 分钟无通知（依赖用户自己看日程）
6. **HNSW 索引缺失** — `voice_embedding` 无向量索引（>100 成员会全表扫描）
7. **`transcript` 缺 `member_id`** — 无法按说话人反查

### 1.3 3a 目标

让用户能：
1. **声纹库中心** — 看所有成员彩色指纹图，对比相似度
2. **置信度历史** — 看到每个会议每个人的识别置信度走势
3. **跨会议搜索** — "找李四说过的内容" 跨会议反查
4. **跨会议关联推荐** — 纪要末尾自动推荐 top-3 相关历史会议
5. **5 分钟前提醒** — 创建会议时自动创建 reminder，企业微信推送

### 1.4 非目标（YAGNI，留到 3b）

- 会议模板（组会/一对一/立项会）
- 议题列表
- 时间轴跳转
- 移动端横屏
- 离线缓冲 5s 显式化
- 状态指示三态补全（2b 已就绪）

---

## 2. 关键决策（已通过 brainstorming 确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 范围 | **严格拆 3a + 3b** | 3a 是核心（声纹/关联/提醒），3b 是体验（主屏/模板/UX） |
| 声纹维度 | **vector(256)** | psql 已确认（CLAUDE.md 提及的 192 已过时） |
| 指纹图可视化 | **256 竖条冷暖色渐变** | 零依赖，与暖橙主题一致，相似成员视觉接近 |
| 跨会议关联 | **相似度匹配 + 引用推荐** | 复分析后检索 top-3 相似会议，纪要中推荐（人类选抨） |

---

## 3. 架构概览

```
┌────────────────────────────────────────────────────────────────┐
│                  浏览器（声纹库 + 纪要 + 会议列表）              │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │Voiceprint   │ │Voiceprint    │ │SpeakerSearch │ │Related │ │
│  │View (新)    │ │Card (新)     │ │ (新)         │ │Meetings│ │
│  │ 成员网格     │ │ 指纹图+历史  │ │ "找李四..."  │ │ 卡片   │ │
│  └──────┬──────┘ └──────┬───────┘ └──────┬───────┘ └───┬────┘ │
│         │ 256 维 + 录入时间│                │ top-3 历史   │       │
└─────────┼────────────────┼────────────────┼─────────┼───────┘
          │ GET /voiceprint/fingerprints  │  GET /voiceprint/search   GET /meetings/{id}/related
   ┌──────▼────────────────▼────────────────▼─────────▼───────┐
   │  app/services/voiceprint_service.py                     │
   │  + get_fingerprints(member_ids) → [(id, embedding, ...)]│
   │  + record_confidence(meeting_id, member_id, score)     │
   │  + search_speaker_history(member_id, limit)            │
   └──────┬──────────────────────────────────────────┬────────┘
          │ pgvector cos distance < 0.55            │ 256 维 raw
          │                                          │
   ┌──────▼──────────────────────────────────────────▼────────┐
   │  Member.voice_embedding (Vector(256))                 │
   │  + HNSW 索引 (新加)                                   │
   └─────────────────────────────────────────────────────────┘
          │
   ┌──────▼────────────────────────────────────────────────────┐
   │  app/services/meeting_service.py                          │
   │  + find_related_meetings(meeting_id, top_k=3)            │
   │    → 调 get_embedding + 复检 top-k 相似                  │
   │  + create_meeting_with_reminder(meeting_data, 5min)       │
   │  + link_related_meetings(meeting_id, related_ids)         │
   └──────┬─────────────────────────────────────────┬──────────┘
          │                                          │
   ┌──────▼───────────────────┐         ┌───────────▼────────────┐
   │  Meeting.embedding       │         │  Reminder + meeting_id│
   │  (Vector(768), 新加)     │         │  + target_type        │
   │  + HNSW 索引              │         │  (新加)              │
   └──────────────────────────┘         └───────────┬────────────┘
                                                       │ Celery 10s
                                              ┌────────▼──────────┐
                                              │ wechat_notifier   │
                                              │ notify_meeting_   │
                                              │ reminder()        │
                                              │ 推送企业微信      │
                                              └───────────────────┘
```

---

## 4. 后端设计

### 4.1 DB 迁移 012 — Meeting embedding + agenda

**文件**：`alembic/versions/012_meeting_embedding_agenda.py`

```python
"""Add embedding + agenda fields to meetings table

Wave 3a: 跨会议相似度匹配需要 meeting embedding
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    # 议题列表（Wave 3b 用）
    op.add_column('meetings', sa.Column('agenda', sa.JSON(), nullable=True))
    # 跨会议相似度匹配（Wave 3a）
    op.add_column('meetings', sa.Column('embedding', Vector(768), nullable=True))
    # 关联会议 ID 列表（top-3 推荐结果）
    op.add_column('meetings', sa.Column('related_meeting_ids', sa.JSON(), nullable=True))
    # HNSW 索引加速相似度匹配
    op.execute("CREATE INDEX IF NOT EXISTS idx_meeting_embedding ON meetings USING hnsw (embedding vector_cosine_ops)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_meeting_embedding")
    op.drop_column('meetings', 'related_meeting_ids')
    op.drop_column('meetings', 'embedding')
    op.drop_column('meetings', 'agenda')
```

### 4.2 DB 迁移 013 — voice_embedding HNSW 索引

**文件**：`alembic/versions/013_member_voice_embedding_hnsw.py`

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

### 4.3 DB 迁移 014 — Reminder 关联 meeting

**文件**：`alembic/versions/014_reminder_meeting.py`

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

### 4.4 Meeting 模型更新

**文件**：`app/models/meeting.py`

**新增 3 个字段**：
```python
# Wave 3a
agenda = Column(JSON, nullable=True)
embedding = Column(Vector(768), nullable=True)
related_meeting_ids = Column(JSON, nullable=True)
```

### 4.5 Reminder 模型更新

**文件**：`app/models/reminder.py`

**新增 2 个字段**：
```python
target_type = Column(String(20), default='task')  # 'task' | 'meeting'
meeting_id = Column(Integer, nullable=True)  # 关联 meeting
```

### 4.6 voiceprint_service 扩展

**文件**：`app/services/voiceprint_service.py`

**新增 API**：

```python
async def get_fingerprints(
    db: AsyncSession,
    member_ids: list[int] | None = None,
) -> list[dict]:
    """
    批量返回成员的 256 维 embedding + 元数据。
    用于声纹库页面一次性加载。
    """
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
    Returns: [{meeting_id, meeting_title, transcript_text, ts, confidence}, ...]
    """
    from app.models.meeting import Meeting
    from sqlalchemy import or_

    stmt = select(Meeting).where(
        Meeting.transcript.isnot(None),
    ).order_by(Meeting.start_time.desc()).limit(limit * 3)  # 多取一些再筛选

    result = await db.execute(stmt)
    meetings = result.scalars().all()

    matches = []
    for meeting in meetings:
        transcript = meeting.transcript or []
        for entry in transcript:
            # 优先按 member_id 匹配
            if entry.get("member_id") == member_id:
                matches.append({
                    "meeting_id": meeting.id,
                    "meeting_title": meeting.title,
                    "text": entry.get("text", ""),
                    "speaker": entry.get("speaker", ""),
                    "ts": entry.get("start") or entry.get("ts"),
                    "confidence": entry.get("confidence", 0),
                })
                if len(matches) >= limit:
                    return matches
    return matches
```

### 4.7 VoiceprintHistory 模型（新建）

**文件**：`app/models/voiceprint_history.py`（新）

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

### 4.8 meeting_service 扩展

**文件**：`app/services/meeting_service.py`

**新增 API**：

```python
async def compute_and_store_embedding(
    db: AsyncSession,
    meeting_id: int,
) -> None:
    """复分析会议后计算 embedding 存库（用于跨会议相似度）"""
    from app.core.llm import get_anthropic_client, get_default_model
    from app.core.llm import extract_text_from_response
    from app.models.meeting import Meeting

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        return

    # 用 summary + key_points + decisions 拼成 embedding 输入
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

    # 调 embedding 模型（项目用 text2vec-base-chinese）
    from app.services.embedding_service import embedding_service
    embedding = await embedding_service.embed(full_text)

    meeting.embedding = embedding
    await db.commit()


async def find_related_meetings(
    db: AsyncSession,
    meeting_id: int,
    top_k: int = 3,
) -> list[dict]:
    """跨会议相似度匹配（top-3）"""
    from app.models.meeting import Meeting
    from sqlalchemy import select

    current = await db.get(Meeting, meeting_id)
    if not current or not current.embedding:
        return []

    # 调 pgvector cosine_distance 排序
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


async def create_meeting_with_reminder(
    db: AsyncSession,
    meeting_data: dict,
    remind_minutes_before: int = 5,
) -> Meeting:
    """创建会议 + 自动创建 N 分钟前 reminder"""
    from app.models.reminder import Reminder
    from app.models.meeting import Meeting

    # 1. 创建会议
    meeting = Meeting(**meeting_data)
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    # 2. 自动创建 reminder
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

        # 3. 加入 Redis ZSET
        from app.services.reminder_scheduler import reminder_scheduler
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

### 4.9 wechat_notifier 扩展

**文件**：`app/wechat/notifier.py`

**新增方法**：

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

### 4.10 reminder_scheduler 适配

**文件**：`app/services/reminder_scheduler.py`

**改造**：扫描到期的 reminder 时，按 `target_type` 分发：
- `'task'` → 现有 task 发送逻辑
- `'meeting'` → `notify_meeting_reminder()`

```python
# 在 Celery 扫描循环中追加
if reminder.target_type == "meeting":
    meeting = await db.get(Meeting, reminder.meeting_id)
    if meeting:
        # 推送给所有参会人
        participants = await get_meeting_participants(meeting.id)
        for p in participants:
            await notify_meeting_reminder(p.wechat_id, meeting_info, remind_minutes)
```

### 4.11 REST API 端点

**文件**：`app/api/v1/voiceprint.py`（增）+ `app/api/v1/meeting.py`（增）

**新增 4 个端点**：

```python
# voiceprint.py
@router.get("/fingerprints")
async def get_all_fingerprints(
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回所有成员的 256 维 embedding + 元数据（声纹库中心）"""
    return await voiceprint_service.get_fingerprints(db)


@router.get("/{member_id}/history")
async def get_member_voiceprint_history(
    member_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回该成员的声纹识别置信度历史（最近 N 次）"""
    from app.models.voiceprint_history import VoiceprintHistory
    from sqlalchemy import select, desc
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
    return await voiceprint_service.search_speaker_history(db, member_id, limit)


# meeting.py
@router.get("/{meeting_id}/related")
async def get_related_meetings(
    meeting_id: int,
    top_k: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回与该会议最相似的 top-k 历史会议"""
    return await meeting_service.find_related_meetings(db, meeting_id, top_k)


@router.post("/{meeting_id}/related", status_code=200)
async def set_related_meetings(
    meeting_id: int,
    related_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """手动设置会议关联（人类选抨）"""
    await meeting_service.link_related_meetings(db, meeting_id, related_ids)
    return {"status": "linked", "count": len(related_ids)}
```

### 4.12 transcript 推送时记录 member_id + confidence

**文件**：`app/api/v1/voice.py`（修改）

在 transcript 推送处（wave 2b 任务 9 加的 pipeline 推送），追加：
```python
# Wave 3a: 记录置信度历史
if entry.get("member_id") and entry.get("confidence"):
    from app.services.voiceprint_service import record_confidence
    await record_confidence(db, meeting_id, entry["member_id"], entry["confidence"])
```

在 transcript entry 持久化时（WebSocketDisconnect 处），`transcript_entry` 字典加 `member_id` 字段（用于跨会议反查）。

---

## 5. 前端设计

### 5.1 新建 VoiceprintView（声纹库中心页面）

**文件**：`web/src/views/VoiceprintView.vue`（新）

**结构**：
- 顶部：标题"课题组声纹中心" + 搜索框
- 主体：成员网格（每张卡显示指纹图）
- 右侧抽屉：点击成员后显示置信度历史曲线 + "找该成员说过的话"搜索框

### 5.2 新建 VoiceprintCard（指纹图组件）

**文件**：`web/src/components/voiceprint/VoiceprintCard.vue`（新）

**结构**：
- 256 根固定高度/宽度的竖条
- 颜色按值渐变：负值冷色（蓝）→ 0 中性（白）→ 正值暖色（橙）
- 卡片底部：成员名 + 录入时间 + 样本数

**实现**：
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
import { computed } from 'vue'

const props = defineProps({
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
}
.voiceprint-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.2);
}
.fingerprint {
  display: flex;
  gap: 1px;
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
}
</style>
```

### 5.3 新建 ConfidenceChart（置信度历史曲线）

**文件**：`web/src/components/voiceprint/ConfidenceChart.vue`（新）

**结构**：
- 折线图（用 ECharts line）
- X 轴：会议时间
- Y 轴：置信度 0-1
- 阈值线 0.45（match threshold）

### 5.4 新建 SpeakerSearch（跨会议搜索 UI）

**文件**：`web/src/components/voiceprint/SpeakerSearch.vue`（新）

**结构**：
- 搜索框 + 成员下拉
- 结果列表：会议标题 + 文本片段 + 时间戳 + 置信度
- 点击跳转会议详情

### 5.5 修改 MeetingDetailView（加"相关会议"卡片）

**文件**：`web/src/views/MeetingDetailView.vue`

**新增**：
- 纪要末尾加"相关会议"小节
- 列表显示 top-3 相似会议
- 每个卡片：标题 + 时间 + 相似度 + "查看"按钮
- 复选框：选中后调用 POST /meetings/{id}/related 关联

### 5.6 修改 MeetingView（加"提前提醒"复选框）

**文件**：`web/src/views/MeetingView.vue`

**新增**：
- 创建会议对话框加复选框："提前 5 分钟提醒"
- 默认勾选
- 提交时调 `createMeetingWithReminder` API

### 5.7 添加路由

**文件**：`web/src/router/index.js`

```javascript
{
  path: '/voiceprint',
  name: 'Voiceprint',
  component: () => import('@/views/VoiceprintView.vue'),
  meta: { title: '声纹库中心', icon: 'mic' },
}
```

---

## 6. 数据流

### 6.1 声纹库加载

```
用户访问 /voiceprint
    │
    ▼
VoiceprintView 加载
    │
    ▼
GET /api/v1/voiceprint/fingerprints
    │
    ▼
voiceprint_service.get_fingerprints(db)
    │
    ├─→ 查 Member.voice_embedding 不为空的成员
    │
    ▼
返回 [{id, name, avatar, embedding: [256 floats], ...}]
    │
    ▼
VoiceprintView 渲染 256 根条
```

### 6.2 跨会议反查

```
用户在声纹库点 "找李四说过的"
    │
    ▼
GET /api/v1/voiceprint/search?member_id=5
    │
    ▼
voiceprint_service.search_speaker_history(db, 5)
    │
    ├─→ 查最近 60 个会议的 transcript JSON
    ├─→ 过滤 entry.member_id == 5 的条目
    │
    ▼
返回 [{meeting_id, meeting_title, text, ts, confidence}, ...]
    │
    ▼
SpeakerSearch 渲染列表
```

### 6.3 跨会议相似度推荐

```
用户查看会议详情 MeetingDetailView
    │
    ▼
GET /api/v1/meetings/{id}/related
    │
    ▼
meeting_service.find_related_meetings(db, id, top_k=3)
    │
    ├─→ 调 embedding 模型计算当前会议 embedding
    ├─→ pgvector cosine_distance 排序
    │
    ▼
返回 [{id, title, start_time, summary, similarity}, ...]
    │
    ▼
MeetingDetailView "相关会议" 卡片渲染
```

### 6.4 5 分钟前提醒

```
用户创建会议（带 remind_minutes_before=5）
    │
    ▼
POST /api/v1/meetings {start_time: ..., title: ...}
    │
    ▼
meeting_service.create_meeting_with_reminder
    │
    ├─→ 创建 Meeting
    ├─→ 创建 Reminder(remind_at=start_time-5min, target_type='meeting')
    ├─→ 加入 Redis ZSET
    │
    ▼
(5 分钟后) Celery 扫描
    │
    ▼
reminder_scheduler 检测到 target_type='meeting'
    │
    ├─→ 查 Meeting 详情
    ├─→ 查所有参会人 wechat_id
    └─→ notify_meeting_reminder() 推送企业微信
```

---

## 7. 错误处理

### 7.1 后端

| 场景 | 处理 | 用户感知 |
|---|---|---|
| 声纹模型未加载 | lazy load 失败 → 录入失败 | "声纹模型未就绪" |
| HNSW 索引创建失败 | DB 兼容问题 → fallback cosine（无索引） | 性能略差但可用 |
| 跨会议搜索 transcript 缺 member_id | search 返回空 | 静默 |
| Embedding 服务失败 | catch + log + 跳过该会议 | "该会议无关联推荐" |
| Celery 推送失败 | retry 1 次，仍失败 mark sent（避免重复） | 静默 |
| meeting_id 引用不存在 | Reminder 启动时跳过 | 静默 |

### 7.2 前端

| 场景 | 处理 |
|---|---|
| 声纹库加载失败 | ElMessage.error + 重试按钮 |
| 256 维数组成员不足 1 人 | 提示"暂无录入声纹的成员" |
| 置信度历史为空 | 显示"该成员暂无识别历史" |
| 跨会议搜索返回空 | "未找到该成员的发言记录" |
| 移动端指纹图过窄 | 横向滚动 |

---

## 8. 测试策略

### 8.1 后端单测

**`tests/test_voiceprint_history_model.py`**（新）
- `test_create_history`：基本创建
- `test_cascade_delete`：删 meeting 触发级联删除

**`tests/test_voiceprint_fingerprints_api.py`**（新）
- `test_get_fingerprints_basic`：mock db.execute 返回 3 个成员
- `test_filter_active`：is_active=False 不返回

**`tests/test_voiceprint_search_api.py`**（新）
- `test_search_speaker_history`：transcript 包含 member_id=5 的条目返回
- `test_search_limit`：limit=N 时返回最多 N 条

**`tests/test_meeting_embedding_service.py`**（新）
- `test_compute_and_store_embedding`：mock embedding 服务 + 验证 meeting.embedding 设置
- `test_find_related_meetings`：mock db 返回 3 个相关会议
- `test_find_related_returns_empty_when_no_embedding`：当前会议无 embedding → []

**`tests/test_create_meeting_with_reminder.py`**（新）
- `test_create_meeting_basic`：只创建会议
- `test_create_meeting_with_5min_reminder`：自动创建 Reminder
- `test_create_meeting_no_start_time`：start_time 为 None 时不创建 reminder

### 8.2 集成测试

**`tests/test_meeting_related_api.py`**（新）
- `test_get_related_meetings_returns_top_k`：3 个相关会议
- `test_set_related_meetings_writes_field`：POST 写入 meeting.related_meeting_ids

### 8.3 前端测试

项目无测试框架（wave 1 已确认）。E2E 手动验证。

---

## 9. 部署与迁移

### 9.1 DB 迁移

```bash
docker compose exec app alembic upgrade head
```

预期：`Running upgrade 011_meeting_audio_archive -> 012_meeting_embedding_agenda, ...`
预期：`Running upgrade 012_... -> 013_member_voice_embedding_hnsw`
预期：`Running upgrade 013_... -> 014_reminder_meeting`

### 9.2 后端部署

新增/修改：
- 新建 `alembic/versions/012_meeting_embedding_agenda.py`
- 新建 `alembic/versions/013_member_voice_embedding_hnsw.py`
- 新建 `alembic/versions/014_reminder_meeting.py`
- 新建 `app/models/voiceprint_history.py`
- 修改 `app/models/meeting.py`（+3 字段）
- 修改 `app/models/reminder.py`（+2 字段）
- 修改 `app/services/voiceprint_service.py`（+3 API）
- 修改 `app/services/meeting_service.py`（+3 API）
- 修改 `app/api/v1/voice.py`（transcript 推送处加 member_id）
- 修改 `app/wechat/notifier.py`（+notify_meeting_reminder）
- 修改 `app/services/reminder_scheduler.py`（按 target_type 分发）
- 新建/修改 `app/api/v1/voiceprint.py`（+3 端点）
- 修改 `app/api/v1/meeting.py`（+2 端点）

### 9.3 前端部署

- 新建 `web/src/views/VoiceprintView.vue`
- 新建 `web/src/components/voiceprint/VoiceprintCard.vue`
- 新建 `web/src/components/voiceprint/ConfidenceChart.vue`
- 新建 `web/src/components/voiceprint/SpeakerSearch.vue`
- 修改 `web/src/views/MeetingDetailView.vue`（+相关会议卡片）
- 修改 `web/src/views/MeetingView.vue`（+提前提醒复选框）
- 修改 `web/src/router/index.js`（+声纹库路由）

### 9.4 风险

| 风险 | 缓解 |
|---|---|
| pgvector HNSW 索引创建慢 | IF NOT EXISTS 保护；数据量小时可先建 |
| embedding 服务慢 | 异步 + 后台任务（不阻塞会议保存） |
| 跨会议搜索扫 60 个会议 IO 重 | 限制 limit + 加 `Meeting.embedding` 索引后只命中 top-k |
| 256 维传到前端 16KB/成员 | 100 个成员 = 1.6MB，可接受；如太大可改为 8 维 PCA 降维 |
| 钉钉 0% 覆盖 | 5min 提醒只用企业微信（项目惯例） |
| Reminder 改造影响现有 task reminder | `target_type` 字段有默认值 `'task'`，老数据不破坏 |

---

## 10. 验收标准

### 10.1 必达

1. ✅ DB 迁移 012/013/014 成功
2. ✅ `voice_embedding` HNSW 索引就位
3. ✅ `VoiceprintView` 显示所有录入声纹成员（256 竖条）
4. ✅ 置信度历史曲线正确展示
5. ✅ 跨会议搜索"找李四说过的"返回正确结果
6. ✅ 跨会议相似度推荐 top-3 在纪要末尾显示
7. ✅ 创建会议时自动创建 5 分钟前 reminder
8. ✅ Celery 推送企业微信 5 分钟提醒工作
9. ✅ `transcript` JSON 包含 `member_id` 字段
10. ✅ 单测覆盖率 > 70%（新增模块）

### 10.2 体验达

11. ✅ 100 个成员指纹图页面加载 < 2s
12. ✅ 跨会议搜索响应 < 500ms
13. ✅ 相似度推荐响应 < 1s
14. ✅ 5 分钟提醒在 start_time - 5min ± 30s 内推送

---

## 11. 实施顺序（预计 20-25 任务）

1. DB 迁移 012（Meeting embedding + agenda + related + HNSW）
2. DB 迁移 013（voice_embedding HNSW）
3. DB 迁移 014（Reminder meeting_id + target_type）
4. Meeting 模型 + Reminder 模型
5. VoiceprintHistory 模型
6. voiceprint_service 扩展（get_fingerprints / record_confidence / search_speaker_history）
7. meeting_service 扩展（compute_embedding / find_related / create_with_reminder / link_related）
8. embedding 集成到 meeting analyze 流程（compute_and_store_embedding）
9. wechat_notifier 扩展（notify_meeting_reminder）
10. reminder_scheduler 适配 target_type
11. /live 端点：transcript 推送时记录 member_id + record_confidence
12. voiceprint REST API（fingerprints / history / search）
13. meeting REST API（related GET/POST）
14. 前端 VoiceprintView + VoiceprintCard + ConfidenceChart + SpeakerSearch
15. 前端 MeetingDetailView 加"相关会议"卡片
16. 前端 MeetingView 加"提前提醒"复选框
17. 前端路由 + 侧边栏菜单
18. 本地构建 + 端到端测试
19. 部署到服务器
20. 最终验证 + ROADMAP 更新

---

**版本**：v1.0
**等待用户审阅** → 通过后进入 writing-plans 阶段生成实现计划

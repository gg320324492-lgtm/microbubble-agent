from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timedelta
import json
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundException, ValidationException, ForbiddenException
from app.schemas.pagination import PaginatedResponse
from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from app.models.task import Task

logger = logging.getLogger("microbubble.meeting_api")
from app.schemas.meeting import (
    MeetingCreate, MeetingUpdate, MeetingResponse, MeetingList, MeetingMinutes,
    SpeakerDetectRequest, SpeakerDetectResponse,
    TranscriptAnalyzeRequest, TranscriptAnalyzeResponse,
    SpeakerMapRequest, MeetingAnalyticsResponse, TranscriptSpeakerRequest, TranscriptSpeakerUpdateRequest,
)
from app.services.meeting_service import MeetingService
from app.services.meeting_analysis_service import meeting_analysis
from app.services.progress_service import init_progress
from app.services.post_meeting_tasks import post_meeting_process

router = APIRouter()


@router.post("/meetings", status_code=201)
async def create_meeting(
    meeting_data: MeetingCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建会议"""
    meeting = Meeting(
        title=meeting_data.title,
        description=meeting_data.description,
        start_time=meeting_data.start_time,
        end_time=meeting_data.end_time,
        location=meeting_data.location,
        agenda=meeting_data.agenda,  # Wave 3b
        meeting_url=meeting_data.meeting_url,
        meeting_id=meeting_data.meeting_id,
        status="scheduled"
    )

    db.add(meeting)
    await db.flush()

    # 添加参与者
    if meeting_data.participants:
        for member_id in meeting_data.participants:
            participant = MeetingParticipant(
                meeting_id=meeting.id,
                member_id=member_id
            )
            db.add(participant)

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/meetings")
async def list_meetings(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询会议列表"""
    from sqlalchemy.orm import selectinload
    query = select(Meeting).options(
        selectinload(Meeting.participants).selectinload(MeetingParticipant.member)
    )

    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(Meeting.start_time >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            # +1 天包含当天
            query = query.where(Meeting.start_time < dt + timedelta(days=1))
        except ValueError:
            pass
    if keyword:
        query = query.where(Meeting.title.contains(keyword))
    if status:
        query = query.where(Meeting.status == status)

    query = query.order_by(Meeting.start_time.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    meetings = list(dict.fromkeys(result.scalars().unique().all()).keys())

    # 手动构建响应字典避免 Pydantic 序列化 ORM 失败
    items = []
    for m in meetings:
        p_list = []
        for p in (m.participants or []):
            p_list.append({
                "member_id": p.member_id,
                "name": p.member.name if p.member else "",
                "role": p.role or "participant",
                "avatar": getattr(p.member, "avatar", None) if p.member else None,
            })
        items.append({
            "id": m.id,
            "title": m.title,
            "start_time": m.start_time.isoformat() if m.start_time else None,
            "end_time": m.end_time.isoformat() if m.end_time else None,
            "location": m.location,
            "status": m.status,
            "summary": m.summary,
            "audio_url": m.audio_url,
            "audio_duration": m.audio_duration,
            "participants": p_list,
            "presenter_ids": m.presenter_ids,
            "agenda": m.agenda,
            "created_by": m.created_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {"items": items, "total": len(items)}

    return {"items": meetings, "total": len(meetings)}


# === 粘贴转录 + AI 分析（固定路径必须在参数化路由之前） ===

@router.post("/meetings/detect-speakers", response_model=SpeakerDetectResponse)
async def detect_speakers(
    request: SpeakerDetectRequest,
    current_user: Member = Depends(get_current_user),
):
    """检测转录文本中的发言者（阶段1：不创建会议）"""
    try:
        result = await meeting_analysis.detect_speakers(request.transcript_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发言者检测失败: {str(e)}")


@router.post("/meetings/analyze-text")
async def analyze_transcript_text(
    request: TranscriptAnalyzeRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """粘贴转录文本并全量分析（阶段2：创建会议 + AI 分析 + 创建任务）

    支持两种模式：
    - 不带 speaker_mapping：先返回发言者检测结果让用户确认
    - 带 speaker_mapping：直接执行完整分析
    """
    meeting_service = MeetingService(db)

    if request.speaker_mapping is None:
        # 阶段1：只检测发言者，不创建会议
        detection = await meeting_analysis.detect_speakers(request.transcript_text)
        return {
            "phase": "speaker_detection",
            "detection": detection,
            "message": "请确认发言者映射后再次提交",
        }

    # 阶段2：完整分析
    try:
        title = request.title or await meeting_analysis.generate_title(request.transcript_text)
        result = await meeting_service.process_pasted_transcript(
            title=title,
            start_time=request.start_time,
            transcript_text=request.transcript_text,
            speaker_mapping=request.speaker_mapping,
            participant_ids=request.participants,
            created_by=current_user.id,
        )
        result["phase"] = "complete"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录分析失败: {str(e)}")


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会议详情"""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.participants).selectinload(MeetingParticipant.member))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    return meeting


@router.get("/meetings/{meeting_id}/minutes", response_model=MeetingMinutes)
async def get_meeting_minutes(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取会议纪要"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    if not meeting.summary:
        # 返回空内容而非 404，让前端能正常展示空状态
        return MeetingMinutes(
            summary="",
            key_points=meeting.key_points or [],
            decisions=meeting.decisions or [],
            action_items=[],
            next_meeting=None
        )

    return MeetingMinutes(
        summary=meeting.summary,
        key_points=meeting.key_points or [],
        decisions=meeting.decisions or [],
        action_items=[],
        next_meeting=None
    )


@router.post("/meetings/{meeting_id}/generate-minutes")
async def generate_meeting_minutes(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成会议纪要"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    if not meeting.transcript:
        raise ValidationException("会议转写内容为空")

    transcript_text = json.dumps(meeting.transcript, ensure_ascii=False)

    # 直接调用 AI 分析服务，不走 agent.chat()（避免污染会话状态）
    analysis = await meeting_analysis.analyze_transcript(transcript_text)

    meeting.summary = analysis.get("summary", "")
    meeting.key_points = analysis.get("key_points") or None
    meeting.decisions = analysis.get("decisions") or None
    meeting.status = "completed"
    await db.commit()

    return {
        "message": "会议纪要生成成功",
        "summary": meeting.summary,
        "key_points": meeting.key_points or [],
        "decisions": meeting.decisions or [],
    }


@router.post("/meetings/{meeting_id}/analyze")
async def analyze_meeting_transcript(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """分析会议转写内容，自动提取摘要、要点、决定和任务"""
    meeting_service = MeetingService(db)
    meeting = await meeting_service.get_meeting(meeting_id)

    if not meeting:
        raise NotFoundException("会议")

    if not meeting.transcript:
        raise ValidationException("会议转写内容为空，无法分析")

    try:
        result = await meeting_service.process_meeting_transcript(meeting_id)
        return {
            "message": "分析完成",
            "summary": result["summary"],
            "key_points": result["key_points"],
            "decisions": result["decisions"],
            "tasks_created": result["tasks_created"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.put("/meetings/{meeting_id}")
async def update_meeting(
    meeting_id: int,
    meeting_data: MeetingUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新会议"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    update_data = meeting_data.model_dump(exclude_unset=True)
    # participants 是关联表，需特殊处理
    participant_ids = update_data.pop("participants", None)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    if participant_ids is not None:
        # 清除旧参与者，写入新列表
        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id))
        for mid in participant_ids:
            db.add(MeetingParticipant(meeting_id=meeting_id, member_id=mid, role="participant"))

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.delete("/meetings/{meeting_id}")
async def delete_meeting(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除会议"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    # ★ 阶段 4（2026-06-12 防御机制）：先清 MinIO 上的 chunked/merged 文件 + 旧版 audio_url
    # 防止删除会议后 MinIO 残留孤儿文件
    try:
        from app.services.chunked_upload_service import chunked_upload_service
        from app.services.file_service import file_service
        # 1. 清 chunked 模式文件（chunks/ + merged.webm）
        await chunked_upload_service.delete_all(meeting_id)
        # 2. 清旧版一次性上传的 audio_url
        if meeting.audio_url and not meeting.audio_url.startswith("recordings/" + str(meeting_id) + "/"):
            try:
                file_service.delete_file(meeting.audio_url)
            except Exception as e:
                logger.warning(f"清旧版 audio_url 失败: {e}")
    except Exception as e:
        logger.warning(f"清理会议 {meeting_id} MinIO 资源失败（继续删 DB）: {e}")

    # 先清除关联数据（避免外键约束阻止删除）
    from sqlalchemy import delete as sa_delete, update as sa_update
    await db.execute(sa_delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id))
    await db.execute(sa_update(Task).where(Task.meeting_id == meeting_id).values(meeting_id=None))
    await db.delete(meeting)
    await db.commit()
    return {"message": "会议已删除"}


@router.post("/meetings/{meeting_id}/speaker-map")
async def apply_speaker_mapping(
    meeting_id: int,
    request: SpeakerMapRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为已有会议设置发言者映射并重新分析"""
    meeting_service = MeetingService(db)

    meeting = await meeting_service.get_meeting(meeting_id)
    if not meeting:
        raise NotFoundException("会议")

    try:
        result = await meeting_service.reanalyze_with_speakers(
            meeting_id, request.speaker_mapping
        )
        return {"message": "发言者映射已应用并重新分析", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新分析失败: {str(e)}")


@router.post("/meetings/{meeting_id}/polish-text")
async def polish_text(
    meeting_id: int,
    body: dict,
    current_user: Member = Depends(get_current_user),
):
    """对指定文本进行 AI 轻量润色（2026-06-11 升级：加标点 + 删孤立幻觉 + 修明显错字）

    升级背景：原版 prompt "只加标点不改内容" 过于保守，导致 ASR 乱码 / 错名 / 字幕组声明
    等噪声全部原样保留。现已对齐 meeting_polish.py 的新规则。
    """
    text = body.get("text", "")
    if not text or len(text.strip()) < 3:
        raise HTTPException(status_code=400, detail="文本太短")

    from app.services.meeting_ai_polish import polish_segments_with_cache

    # 用缓存版 (meeting_id 隔离 Redis key), 同一段文本二次请求直接命中缓存, 0 LLM 调用
    result = await polish_segments_with_cache(
        meeting_id=meeting_id,
        segments=[{"speaker": "未知", "text": text, "ts": 0.0}],
        meeting_context={"title": "", "participants": [], "topic": None, "context": None},
    )
    polished = result["polished"][0]["text"] if result.get("polished") else text
    return {"polished": polished}


@router.post("/meetings/{meeting_id}/polish-text-batch")
async def polish_text_batch(
    meeting_id: int,
    body: dict,
    current_user: Member = Depends(get_current_user),
):
    """批量润色多条文本（v31.3.2: 解决 83 段会议一次性 83 个 polish-text 触发 write tier 30/min 限流）

    输入: {"texts": ["text1", "text2", ...]}
    输出: {"polished": ["polished1", "polished2", ...]}

    实现要点:
      - 内部循环调 polish_segments_with_cache（每条文本独立 cache key, 复用已有 Redis 缓存）
      - 整个批次对外只算 1 个 write tier 请求（rate-limit middleware 在路由外计数）
      - 上限 200 条/批（防恶意 payload + LLM token 超限）
      - 空字符串 / 过短文本直接返回原文（与单文本端点行为一致）

    为什么需要：单文本 polish-text 在前端 autoPolishIfNeeded 并发 3 调用 N 条转录
    → 83 条会议触发 ~83 次 POST → write tier 30/min 在 ~30 条后全 429。
    batch 端点把这 83 次 HTTP 请求压缩到 1 次，从根本上避开限流。
    """
    texts = body.get("texts", [])
    if not isinstance(texts, list):
        raise HTTPException(status_code=400, detail="texts 必须是数组")
    if len(texts) > 200:
        raise HTTPException(status_code=400, detail=f"单批最多 200 条（当前 {len(texts)} 条）")
    if not texts:
        return {"polished": []}

    from app.services.meeting_ai_polish import polish_segments_with_cache

    polished_list = []
    for text in texts:
        if not text or not isinstance(text, str) or len(text.strip()) < 3:
            # 空 / 过短：原样返回（与单文本端点 '文本太短' 异常不同——批量场景下保持对齐友好）
            polished_list.append(text)
            continue
        # 每条文本独立 cache key（hash 仅基于单条 segment）→ 复用已有 Redis 缓存
        result = await polish_segments_with_cache(
            meeting_id=meeting_id,
            segments=[{"speaker": "未知", "text": text, "ts": 0.0}],
            meeting_context={"title": "", "participants": [], "topic": None, "context": None},
        )
        polished = result["polished"][0]["text"] if result.get("polished") and result["polished"] else text
        polished_list.append(polished)

    return {"polished": polished_list}


@router.patch("/meetings/{meeting_id}/transcript-speaker")
async def update_transcript_speaker(
    meeting_id: int,
    request: TranscriptSpeakerUpdateRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动修正某条转录记录的发言人，不重新生成纪要。"""
    meeting_service = MeetingService(db)
    try:
        result = await meeting_service.update_transcript_speaker(
            meeting_id=meeting_id,
            entry_index=request.entry_index,
            speaker=request.speaker,
        )
    except IndexError:
        raise ValidationException("转录条目不存在")
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新发言人失败: {str(e)}")

    if result.get("error"):
        raise NotFoundException("会议")
    return {"message": "转录发言人已更新", **result}


@router.get("/meetings/{meeting_id}/analytics", response_model=MeetingAnalyticsResponse)
async def get_meeting_analytics(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会议发言者维度统计"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise NotFoundException("会议")

    if not meeting.speaker_stats:
        # 如果还没有统计但有转录内容，实时计算
        if meeting.transcript and isinstance(meeting.transcript, list):
            stats = meeting_analysis.compute_speaker_stats(meeting.transcript)
            meeting.speaker_stats = stats
            await db.commit()
        else:
            return MeetingAnalyticsResponse(
                speaker_stats=[],
                meeting_stats={"total_turns": 0, "total_words": 0},
            )

    total_turns = sum(s.get("turn_count", 0) for s in (meeting.speaker_stats or []))
    total_words = sum(s.get("word_count", 0) for s in (meeting.speaker_stats or []))

    return MeetingAnalyticsResponse(
        speaker_stats=meeting.speaker_stats or [],
        meeting_stats={
            "total_turns": total_turns,
            "total_words": total_words,
            "speaker_count": len(meeting.speaker_stats or []),
        },
    )


@router.post("/meetings/{meeting_id}/end-call", status_code=200)
async def end_meeting_call(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """挂断会议：标记完成 + 启动 Celery 任务 + 返回进度 WS URL"""
    import datetime

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise NotFoundException("会议")

    # 校验用户是参与者
    part_result = await db.execute(
        select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.member_id == current_user.id,
        )
    )
    if not part_result.scalar_one_or_none():
        raise ForbiddenException("非会议参与者")

    # 更新状态
    meeting.status = "completed"
    meeting.end_time = datetime.datetime.utcnow()
    await db.commit()

    # 初始化进度
    await init_progress(meeting_id)

    # 启动 Celery
    post_meeting_process.delay(meeting_id)

    return {
        "status": "ended",
        "meeting_id": meeting_id,
        "progress_ws_url": f"/api/v1/ws/meeting/{meeting_id}/progress",
    }


# 2026-07-12 死代码清理: 删除 DELETE /meetings/{id}/audio handler
# 原因: audio_archive_service.py 已删 (孤儿), model 列已 drop (alembic 059)
# handler 唯一作用 = 软删除 audio_archive_url, 列已不存在, handler 必 500


@router.get("/meetings/{meeting_id}/related")
async def get_related_meetings(
    meeting_id: int,
    top_k: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回与该会议最相似的 top-k 历史会议"""
    from app.services.meeting_service import find_related_meetings
    return await find_related_meetings(db, meeting_id, top_k)


@router.post("/meetings/{meeting_id}/related", status_code=200)
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


# === Wave 3b: 议程端点 ===
@router.patch("/meetings/{meeting_id}/agenda", status_code=200)
async def update_meeting_agenda(
    meeting_id: int,
    agenda: list,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """通话中更新议程（手动勾选完成 / 模板应用后写入）"""
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )).scalar_one_or_none()
    if not meeting:
        raise NotFoundException("会议")
    meeting.agenda = agenda
    await db.commit()
    await db.refresh(meeting)
    return {"status": "updated", "agenda": agenda}

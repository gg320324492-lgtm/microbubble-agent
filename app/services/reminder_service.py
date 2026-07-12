"""提醒服务（v2.1）

2026-06-15 全面优化：
- 所有提醒统一在 11:00 AM 北京时间窗口发送（± 60min 容差）
- 每个 task 只有 1 次 11AM 提醒机会：发完即结束，不重试
- 同用户多条 reminder 聚合为 1 条 digest 消息（避免轰炸）
- **任何微信消息都触发 ack**（用户活跃 = 不再推旧的）
  - 包括"收到"/"OK"/"好"/"今天别提醒"/"你好"/"查询 XXX"等所有内容
  - "完成"/"进度 X%" 仍然有 task 状态变更副作用
- 失败也标 sent（one-shot，不重试）

注：snooze_user_reminders 仍保留在 API 端点用于向后兼容，但微信路径已不再调用。
设计文档：C:\\Users\\admin\\.claude\\plans\\snappy-coalescing-quiche.md
"""
import logging
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select
from typing import List, Dict, Any, Optional

from app.models.base import utcnow, BEIJING_TZ
from app.core.celery_db import create_celery_engine_and_session
from app.models.task import Task
from app.models.member import Member
from app.models.reminder import Reminder
from app.services.reminder_policy import (
    is_in_digest_window,
    batch_date_for,
)
from app.wechat.bot import wechat_bot

logger = logging.getLogger("microbubble.reminder")


class ReminderService:
    """提醒服务（v2）

    状态机：
    - pending → sent（11AM 推送成功 / 失败也都标 sent，one-shot）
    - pending → acknowledged（用户主动"收到" / "OK" / "好" / "👌" / "1" / snooze）
    - pending → cancelled（任务完成时通过 ack 联动 / 任务被删 / soft_delete）
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_pending_reminders(self) -> List[Reminder]:
        """检查待发送的提醒（兼容旧 API）"""
        result = await self.db.execute(
            select(Reminder).where(Reminder.status == "pending")
        )
        return result.scalars().all()

    async def send_reminder(self, reminder: Reminder) -> bool:
        """发送单条提醒（兼容旧 API，失败仅 return False）"""
        task_result = await self.db.execute(
            select(Task).where(Task.id == reminder.task_id)
        )
        task = task_result.scalar_one_or_none()

        if not task or not task.assignee_id:
            logger.warning(
                f"提醒 {reminder.id} 无法发送: task不存在或无负责人"
            )
            return False

        member_result = await self.db.execute(
            select(Member).where(Member.id == task.assignee_id)
        )
        member = member_result.scalar_one_or_none()

        if not member:
            logger.warning(
                f"提醒 {reminder.id} 无法发送: 成员不存在 id={task.assignee_id}"
            )
            return False

        if not member.wechat_id and not member.external_userid:
            logger.warning(
                f"提醒 {reminder.id} 无法发送: 成员 {member.name} 无微信标识"
            )
            return False

        message = self._format_reminder_message(task, member)

        try:
            result = await wechat_bot.smart_send(member, message)
            errcode = (
                result.get("errcode", -1) if isinstance(result, dict) else -1
            )
            if errcode != 0:
                logger.warning(
                    f"微信推送返回错误: {result}, member={member.name}"
                )
                return False
            logger.info(f"微信推送成功: member={member.name}")
        except Exception as e:
            logger.error(
                f"微信推送失败 reminder_id={reminder.id} member={member.name}: {e}",
                exc_info=True,
            )
            return False

        return True

    async def send_meeting_reminder(self, reminder: Reminder) -> bool:
        """发送会议提醒（Wave 3a，兼容旧 API）"""
        from app.models.meeting import Meeting, MeetingParticipant
        from app.wechat.notifier import notify_meeting_reminder

        meeting_id = getattr(reminder, "meeting_id", None)
        if not meeting_id:
            logger.warning(f"会议提醒 {reminder.id} 无 meeting_id，跳过")
            return False

        meeting = await self.db.get(Meeting, meeting_id)
        if not meeting:
            logger.warning(
                f"会议提醒 {reminder.id}: meeting {meeting_id} 不存在"
            )
            return False

        try:
            participants_result = await self.db.execute(
                select(Member)
                .join(
                    MeetingParticipant,
                    MeetingParticipant.member_id == Member.id,
                )
                .where(
                    MeetingParticipant.meeting_id == meeting.id,
                    Member.is_active == True,
                )
            )
            participants = list(participants_result.scalars().all())
        except Exception as e:
            logger.error(
                f"会议提醒 {reminder.id} 查询参会人失败: {e}", exc_info=True
            )
            return False

        if not participants:
            logger.warning(
                f"会议 {meeting_id} 没有 active 参会人，跳过提醒"
            )
            return False

        try:
            if meeting.start_time and reminder.remind_at:
                remind_min = max(
                    0,
                    int(
                        (meeting.start_time - reminder.remind_at).total_seconds()
                        // 60
                    ),
                )
            else:
                remind_min = 5
        except Exception:
            remind_min = 5

        push_ok = False
        for p in participants:
            wechat_id = p.wechat_id or p.external_userid or f"member_{p.id}"
            try:
                result = await notify_meeting_reminder(
                    wechat_id,
                    {
                        "title": meeting.title,
                        "start_time": meeting.start_time,
                        "location": meeting.location or "线上",
                        "meeting_url": meeting.meeting_url or "",
                        "participants": [pp.name for pp in participants],
                    },
                    remind_min,
                )
                if result:
                    push_ok = True
            except Exception as e:
                logger.error(
                    f"notify_meeting_reminder 失败: member={p.id} {e}",
                    exc_info=True,
                )

        return push_ok

    def _format_reminder_message(self, task: Task, member: Member) -> str:
        """格式化单条提醒消息（兼容旧 API）"""
        now = utcnow()
        if not task.due_date:
            return (
                f"📋 任务提醒\n\n{member.name}，你好！\n"
                f"📌 任务：{task.title}\n📊 进度：{task.progress}%"
            )

        due_date_beijing = task.due_date.replace(
            tzinfo=timezone.utc
        ).astimezone(BEIJING_TZ)
        diff = task.due_date - now
        total_seconds = diff.total_seconds()

        if total_seconds < 0:
            emoji = "⚠️"
            hours_overdue = int(abs(total_seconds) // 3600)
            if hours_overdue < 24:
                status = f"已逾期{hours_overdue}小时"
            else:
                days = hours_overdue // 24
                status = f"已逾期{days}天"
        elif total_seconds < 3600:
            emoji = "🔔"
            minutes_left = int(total_seconds // 60)
            status = f"还有{minutes_left}分钟到期"
        elif total_seconds < 86400:
            emoji = "🔔"
            hours_left = int(total_seconds // 3600)
            status = f"还有{hours_left}小时到期"
        elif total_seconds <= 172800:
            emoji = "⏰"
            status = f"还有1天到期"
        else:
            emoji = "📋"
            days_left = int(total_seconds // 86400)
            status = f"还有{days_left}天到期"

        return f"""
{emoji} 任务提醒

{member.name}，你好！

你有一个任务即将到期：
📌 任务：{task.title}
📅 截止：{due_date_beijing.strftime('%Y-%m-%d %H:%M')}
📊 状态：{status}
📈 进度：{task.progress}%

请及时处理！
"""

    async def _send_digest_message(
        self, member: Member, reminders: list
    ) -> bool:
        """聚合多 task → 1 条微信消息

        11AM 推送时把该用户所有 pending reminder 合并成 1 条 digest，
        避免 8 个任务就推 8 条轰炸。

        Returns:
            bool — 微信 API 是否返回 errcode=0
        """
        lines = [f"📋 你今天有 {len(reminders)} 条待办：\n"]
        for r in reminders:
            task = r.task
            if not task:
                continue
            due_beijing = (
                task.due_date.replace(tzinfo=timezone.utc).astimezone(
                    BEIJING_TZ
                )
                if task.due_date
                else None
            )
            due_str = (
                due_beijing.strftime("%m-%d %H:%M") if due_beijing else "无截止"
            )
            lines.append(
                f"• [{task.priority or 'medium'}] {task.title}（截止 {due_str}）"
            )
        content = (
            "\n".join(lines)
            + "\n\n回复「收到」= 今天不再提醒；「完成 XXX」= 标记完成。"
        )

        try:
            result = await wechat_bot.smart_send(member, content)
            errcode = (
                result.get("errcode", -1) if isinstance(result, dict) else -1
            )
            if errcode != 0:
                logger.warning(
                    f"digest send failed member_id={member.id} errcode={errcode}"
                )
                return False
            return True
        except Exception as e:
            logger.error(
                f"digest send exception member_id={member.id}: {e}",
                exc_info=True,
            )
            return False

    async def process_reminders(self, redis_override=None):
        """v2 主入口：11AM 窗口内 → 聚合推送 → 标 sent（不重试）

        Celery beat 周期 10s。窗口外时立即 return（不再依赖 Redis ZSET），
        避免半夜触发非预期推送。窗口内时聚合推送，失败也标 sent。

        Returns:
            dict — {total, success, fail, skipped}
        """
        # 1. 窗口外立即返回（半夜 0 行 SQL）
        if not is_in_digest_window():
            return {"total": 0, "success": 0, "fail": 0, "skipped": 0}

        # 2. 查所有 status=pending 的 reminder
        result = await self.db.execute(
            select(Reminder).where(Reminder.status == "pending")
        )
        all_reminders = list(result.scalars().all())

        # 3. 过滤：未 ack 且不在 snooze
        now = utcnow()
        due: List[Reminder] = [
            r
            for r in all_reminders
            if r.acknowledged_at is None
            and (r.snoozed_until is None or r.snoozed_until <= now)
        ]

        if not due:
            return {
                "total": 0,
                "success": 0,
                "fail": 0,
                "skipped": len(all_reminders),
            }

        # 4. 按 member_id 聚合
        by_member: Dict[int, List[Reminder]] = {}
        for r in due:
            task = r.task if r.task_id else None
            member_id = task.assignee_id if task else None
            if not member_id:
                # 无主的 reminder 标 sent 跳过
                r.status = "sent"
                r.sent_at = utcnow()
                continue
            by_member.setdefault(member_id, []).append(r)

        # 5. 每用户聚合 → 1 条 digest
        success, fail = 0, 0
        for member_id, member_rems in by_member.items():
            try:
                member_result = await self.db.execute(
                    select(Member).where(Member.id == member_id)
                )
                member = member_result.scalar_one_or_none()
                if not member:
                    for r in member_rems:
                        r.status = "sent"
                        r.sent_at = utcnow()
                    await self.db.commit()
                    fail += len(member_rems)
                    continue

                if not member.wechat_id and not member.external_userid:
                    logger.warning(
                        f"成员 {member.name} 无微信标识，跳过 {len(member_rems)} 条 reminder"
                    )
                    for r in member_rems:
                        r.status = "sent"
                        r.sent_at = utcnow()
                    await self.db.commit()
                    fail += len(member_rems)
                    continue

                ok = await self._send_digest_message(member, member_rems)
                # 失败也标 sent（one-shot，不重试）
                for r in member_rems:
                    r.status = "sent"
                    r.sent_at = utcnow()
                    r.reminder_batch_date = batch_date_for(r.sent_at)
                await self.db.commit()
                if ok:
                    success += len(member_rems)
                else:
                    fail += len(member_rems)
            except Exception as e:
                logger.error(
                    f"send digest failed member_id={member_id}: {e}",
                    exc_info=True,
                )
                for r in member_rems:
                    r.status = "sent"
                    r.sent_at = utcnow()
                await self.db.commit()
                fail += len(member_rems)

        # 6. 清理 Redis ZSET（兼容旧 ZSET 路径）
        try:
            from app.services.reminder_scheduler import (
                reminder_scheduler,
                ZSET_KEY,
            )

            sent_ids = [
                r.id for r in all_reminders if r.status in ("sent", "acknowledged")
            ]
            if sent_ids:
                if redis_override is not None:
                    await redis_override.zrem(
                        ZSET_KEY, *[str(sid) for sid in sent_ids]
                    )
                else:
                    await reminder_scheduler.remove_batch(sent_ids)
        except Exception as e:
            logger.warning(f"清理 Redis ZSET 失败: {e}")

        return {
            "total": len(due),
            "success": success,
            "fail": fail,
            "skipped": len(all_reminders) - len(due),
        }

    # === v2 新增方法：ack / snooze ===

    async def acknowledge_all_user_reminders(
        self, member_id: int, channel: str = "wechat"
    ) -> int:
        """取消该用户所有 pending reminder（跨任务）

        用于：
        - 微信发"收到"/"OK"/"好" → channel="wechat"
        - 任务"完成" → channel="wechat_done"
        - Web 端"全部标为已读" → channel="web"
        - API 调用 → channel="api"

        注意：不联动 task 状态（不修改 task.status / task.progress）。
        Returns:
            int — 实际取消的 reminder 数量
        """
        from app.models.meeting import MeetingParticipant
        from app.services.reminder_scheduler import reminder_scheduler

        now = utcnow()
        task_rems = list(
            (
                await self.db.execute(
                    select(Reminder)
                    .join(Task, Task.id == Reminder.task_id, isouter=True)
                    .where(
                        Reminder.status == "pending",
                        Task.assignee_id == member_id,
                    )
                )
            ).scalars().all()
        )
        mtg_rems = list(
            (
                await self.db.execute(
                    select(Reminder)
                    .join(
                        MeetingParticipant,
                        MeetingParticipant.meeting_id == Reminder.meeting_id,
                    )
                    .where(
                        Reminder.status == "pending",
                        Reminder.target_type == "meeting",
                        MeetingParticipant.member_id == member_id,
                    )
                )
            ).scalars().all()
        )
        all_rems = task_rems + mtg_rems

        ids: List[int] = []
        for r in all_rems:
            r.status = "acknowledged"
            r.acknowledged_at = now
            r.acknowledged_by = member_id
            r.ack_channel = channel
            ids.append(r.id)
        await self.db.commit()

        # 从 Redis ZSET 移除
        if ids:
            try:
                await reminder_scheduler.remove_batch(ids)
            except Exception as e:
                logger.warning(f"ack 后清理 Redis ZSET 失败: {e}")

        return len(all_rems)

    async def snooze_user_reminders(
        self, member_id: int, until: datetime
    ) -> int:
        """顺延该用户所有 pending reminder 到指定时间

        用于：
        - 微信发"今天别提醒" → until = next 11AM
        - Web/API 设置 snoozed_until

        Returns:
            int — 实际顺延的 reminder 数量
        """
        from app.models.meeting import MeetingParticipant
        from app.services.reminder_scheduler import reminder_scheduler

        task_rems = list(
            (
                await self.db.execute(
                    select(Reminder)
                    .join(Task, Task.id == Reminder.task_id, isouter=True)
                    .where(
                        Reminder.status == "pending",
                        Task.assignee_id == member_id,
                    )
                )
            ).scalars().all()
        )
        mtg_rems = list(
            (
                await self.db.execute(
                    select(Reminder)
                    .join(
                        MeetingParticipant,
                        MeetingParticipant.meeting_id == Reminder.meeting_id,
                    )
                    .where(
                        Reminder.status == "pending",
                        Reminder.target_type == "meeting",
                        MeetingParticipant.member_id == member_id,
                    )
                )
            ).scalars().all()
        )
        all_rems = task_rems + mtg_rems

        for r in all_rems:
            r.snoozed_until = until
            r.reminder_batch_date = batch_date_for(until)
        await self.db.commit()

        # 更新 Redis ZSET 时间戳
        for r in all_rems:
            try:
                await reminder_scheduler.add_reminder(r.id, until.timestamp())
            except Exception as e:
                logger.warning(
                    f"snooze 后更新 Redis ZSET 失败 reminder_id={r.id}: {e}",
                    exc_info=True,
                )

        return len(all_rems)


@shared_task(name="app.services.reminder_service.process_reminders_task")
def process_reminders_task():
    """Celery task: 处理所有待发送提醒（v2 入口）"""
    import asyncio
    import redis.asyncio as aioredis
    from app.config import settings

    async def _run():
        # 创建独立的引擎和 Redis 连接，避免跨事件循环的连接池冲突
        redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        try:
            async_session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session_factory() as db:
                service = ReminderService(db)
                result = await service.process_reminders(redis_override=redis_client)
                print(f"提醒处理完成: {result}")
                return result
        finally:
            await redis_client.aclose()
            await engine.dispose()

    return asyncio.run(_run())

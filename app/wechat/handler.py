"""企业微信消息处理模块 - 被动监听 + 主动分析 + 多模态"""

import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.member import Member
from app.models.task import Task, TaskStatus
from app.agent.core import agent
from app.wechat.notifier import notifier
from app.wechat.bot import wechat_bot
from app.wechat.identity import identity_resolver
from app.wechat.analyzer import analyzer
from app.services.vision_service import vision_service
from app.core.redis import get_redis

logger = logging.getLogger("microbubble.wechat")


class MessageHandler:
    """企业微信消息处理器"""

    # 缓冲区配置
    BUFFER_MAX_MESSAGES = 10       # 消息数达到此值触发分析
    BUFFER_MAX_SECONDS = 300       # 或时间达到5分钟触发分析
    BUFFER_COOLDOWN = 60           # 分析冷却期（秒）
    PENDING_USER_TTL = 1800        # 待绑定用户过期时间（30分钟）
    GROUP_BUFFER_TTL = 600         # 群聊缓冲区过期时间（10分钟）

    # ==================== Redis 状态管理 ====================

    async def _get_pending_user(self, user_id: str) -> dict | None:
        """从 Redis 获取待绑定用户状态"""
        r = await get_redis()
        data = await r.get(f"wechat:pending:{user_id}")
        return json.loads(data) if data else None

    async def _set_pending_user(self, user_id: str, state: dict) -> None:
        """保存待绑定用户状态到 Redis"""
        r = await get_redis()
        await r.set(
            f"wechat:pending:{user_id}",
            json.dumps(state, ensure_ascii=False),
            ex=self.PENDING_USER_TTL
        )

    async def _delete_pending_user(self, user_id: str) -> None:
        """删除待绑定用户状态"""
        r = await get_redis()
        await r.delete(f"wechat:pending:{user_id}")

    async def _get_group_buffer(self, chat_id: str) -> dict:
        """从 Redis 获取群聊缓冲区"""
        r = await get_redis()
        data = await r.get(f"wechat:buffer:{chat_id}")
        if data:
            buf = json.loads(data)
            if buf.get("last_analysis"):
                buf["last_analysis"] = datetime.fromisoformat(buf["last_analysis"])
            return buf
        return {"messages": [], "last_analysis": None}

    async def _save_group_buffer(self, chat_id: str, buffer: dict) -> None:
        """保存群聊缓冲区到 Redis"""
        r = await get_redis()
        save_data = {
            "messages": buffer["messages"],
            "last_analysis": buffer["last_analysis"].isoformat() if buffer["last_analysis"] else None
        }
        await r.set(
            f"wechat:buffer:{chat_id}",
            json.dumps(save_data, ensure_ascii=False, default=str),
            ex=self.GROUP_BUFFER_TTL
        )

    async def handle_message(self, msg: dict, db: AsyncSession) -> None:
        """路由处理消息"""
        msg_type = msg.get("MsgType", "")
        user_id = msg.get("FromUserName", "")
        chat_id = msg.get("ChatId", "")  # 群聊ID（私聊为空）

        # 事件处理
        if msg_type == "event":
            await self._handle_event(msg, db)
            return

        # 检测是否为外部用户（普通微信用户，external_userid 以 wm 开头）
        is_external = user_id.startswith("wm")

        # 识别用户身份
        member = await self._identify_user(user_id, msg, db, is_external)
        if not member:
            await self._handle_unknown_user(user_id, msg_type, msg, db, is_external)
            return

        # 判断是群聊还是私聊
        if chat_id:
            await self._handle_group_message(msg, member, chat_id, db, is_external)
        else:
            await self._handle_private_message(msg, member, msg_type, db, is_external)

    # ==================== 群聊处理 ====================

    async def _handle_group_message(self, msg: dict, member: Member,
                                      chat_id: str, db: AsyncSession,
                                      is_external: bool = False) -> None:
        """
        群聊消息处理

        - @机器人 → 立即响应
        - 普通消息 → 被动监听，缓冲后分析
        """
        content = msg.get("Content", "").strip()
        msg_type = msg.get("MsgType", "")
        user_id = msg.get("FromUserName", "")

        # 判断是否 @了机器人（企业微信群聊中 @机器人 会在 Content 中包含 @机器人 或 AgentID）
        is_mentioned = self._is_bot_mentioned(msg)

        if is_mentioned:
            # @机器人 → 立即响应
            # 去掉 @机器人 前缀
            clean_content = self._strip_bot_mention(content)

            if msg_type == "text" and clean_content:
                # 判断是否是任务回复
                if await self._try_handle_task_reply(clean_content, member, user_id, db):
                    return
                # Agent 对话（群聊回复也发到群里）
                await self._handle_group_chat(clean_content, member, user_id, chat_id, db, is_external)
            elif msg_type == "image":
                await self._handle_group_image(msg, member, chat_id, db, is_external)
            elif msg_type == "voice":
                await self._handle_group_voice(msg, member, chat_id, db, is_external)
        else:
            # 普通群聊消息 → 被动监听
            if msg_type == "text" and content:
                await self._buffer_group_message(chat_id, member, content, db)

    async def _buffer_group_message(self, chat_id: str, member: Member,
                                      content: str, db: AsyncSession) -> None:
        """
        缓冲群聊消息，满足条件时触发分析

        触发条件：
        - 消息数达到 BUFFER_MAX_MESSAGES
        - 距上次分析超过 BUFFER_MAX_SECONDS
        - 消息中包含关键词（任务、安排、决定等）
        """
        buffer = await self._get_group_buffer(chat_id)
        buffer["messages"].append({
            "speaker": member.name,
            "speaker_id": member.id,
            "content": content,
            "time": datetime.utcnow().isoformat()
        })

        should_analyze = False

        # 关键词触发立即分析
        action_keywords = ["安排", "任务", "截止", "deadline", "明天交", "负责",
                          "会议", "决定", "结论", "必须", "尽快", "提醒"]
        if any(kw in content for kw in action_keywords):
            should_analyze = True

        # 消息数触发
        if len(buffer["messages"]) >= self.BUFFER_MAX_MESSAGES:
            should_analyze = True

        # 时间触发
        if buffer["last_analysis"]:
            elapsed = (datetime.utcnow() - buffer["last_analysis"]).total_seconds()
            if elapsed >= self.BUFFER_MAX_SECONDS and len(buffer["messages"]) >= 3:
                should_analyze = True

        if should_analyze:
            await self._analyze_and_act(chat_id, db)
        else:
            await self._save_group_buffer(chat_id, buffer)

    async def _analyze_and_act(self, chat_id: str, db: AsyncSession) -> None:
        """分析缓冲区消息，提取行动项并执行"""
        buffer = await self._get_group_buffer(chat_id)
        messages = buffer["messages"]

        if not messages:
            return

        # 冷却期检查
        if buffer["last_analysis"]:
            elapsed = (datetime.utcnow() - buffer["last_analysis"]).total_seconds()
            if elapsed < self.BUFFER_COOLDOWN:
                return

        # 清空缓冲区并保存到 Redis
        buffer["messages"] = []
        buffer["last_analysis"] = datetime.utcnow()
        await self._save_group_buffer(chat_id, buffer)

        try:
            # 调用分析器
            result = await analyzer.analyze(messages)

            if not result.get("is_actionable"):
                return

            # 处理任务分配
            for task_info in result.get("tasks", []):
                await self._auto_create_task(task_info, messages, chat_id, db)

            # 处理会议安排
            for meeting_info in result.get("meetings", []):
                await self._auto_notify_meeting(meeting_info, chat_id, db)

            # 处理决定/结论
            decisions = result.get("decisions", [])
            if decisions:
                decision_text = "\n".join(f"• {d}" for d in decisions)
                await wechat_bot.smart_send_to_group(chat_id,
                    f"📝 本次讨论决定：\n{decision_text}", msg_type="text")

            # 处理提醒
            for reminder in result.get("reminders", []):
                await self._auto_send_reminder(reminder, db)

        except Exception as e:
            logger.error("群聊分析失败", exc_info=True)

    async def _auto_create_task(self, task_info: dict, messages: list,
                                  chat_id: str, db: AsyncSession) -> None:
        """自动创建任务并通知负责人"""
        assignee_name = task_info.get("assignee_name", "")
        title = task_info.get("title", "")
        description = task_info.get("description", "")
        due_date_str = task_info.get("due_date")
        priority = task_info.get("priority", "medium")

        if not assignee_name or not title:
            return

        # 匹配负责人
        members = await identity_resolver.fuzzy_search(assignee_name, db)
        if not members:
            await wechat_bot.smart_send_to_group(chat_id,
                f"⚠️ 识别到任务「{title}」，但未找到成员「{assignee_name}」，请确认。")
            return

        assignee = members[0]

        # 创建任务
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            except ValueError:
                pass

        task = Task(
            title=title,
            description=description,
            assignee_id=assignee.id,
            priority=priority,
            due_date=due_date,
            status=TaskStatus.TODO.value,
            source="ai_detected"
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # 群里通知
        due_text = f"，截止 {due_date_str}" if due_date_str else ""
        await wechat_bot.smart_send_to_group(chat_id,
            f"📋 已自动创建任务：\n📌 {title}\n👤 负责人：{assignee.name}{due_text}")

        # 私发负责人
        await notifier.notify_task_assigned(
            member=assignee,
            task_title=title,
            due_date=due_date_str or "待定",
            priority=priority,
            description=description,
            assigner="课题组讨论"
        )

    async def _auto_notify_meeting(self, meeting_info: dict,
                                     chat_id: str, db: AsyncSession) -> None:
        """自动通知会议安排"""
        title = meeting_info.get("title", "")
        time = meeting_info.get("time", "")
        location = meeting_info.get("location", "")
        participants = meeting_info.get("participants", [])

        if not title:
            return

        # 群里确认
        participant_names = ", ".join(participants) if participants else "全员"
        await wechat_bot.smart_send_to_group(chat_id,
            f"📅 会议安排已记录：\n📌 {title}\n⏰ {time}\n📍 {location or '待定'}\n👥 {participant_names}")

        # 私发参会者
        for name in participants:
            members = await identity_resolver.fuzzy_search(name, db)
            for m in members:
                if m.wechat_id or m.external_userid:
                    try:
                        content = f"""📅 **会议通知**

**主题**: {title}
**时间**: {time}
"""
                        if location:
                            content += f"**地点**: {location}\n"
                        content += "\n请准时参加！"
                        await wechat_bot.smart_send(m, content, msg_type="markdown")
                    except Exception as e:
                        logger.warning(f"会议通知发送失败 [{m.name}]: {e}")

    async def _auto_send_reminder(self, reminder_info: dict, db: AsyncSession) -> None:
        """自动发送提醒"""
        person = reminder_info.get("person", "")
        content = reminder_info.get("content", "")

        if not person or not content:
            return

        members = await identity_resolver.fuzzy_search(person, db)
        for m in members:
            if m.wechat_id or m.external_userid:
                try:
                    await wechat_bot.smart_send(m, f"🔔 提醒：{content}")
                except Exception as e:
                    logger.warning(f"提醒发送失败 [{m.name}]: {e}")

    # ==================== 私聊处理 ====================

    async def _handle_private_message(self, msg: dict, member: Member,
                                        msg_type: str, db: AsyncSession,
                                        is_external: bool = False) -> None:
        """私聊消息处理"""
        user_id = msg.get("FromUserName", "")

        if msg_type == "text":
            content = msg.get("Content", "").strip()
            if not content:
                return
            if await self._try_handle_task_reply(content, member, user_id, db):
                return
            await self._handle_general_chat(content, member, user_id, db, is_external)

        elif msg_type == "image":
            await self._handle_image(msg, member, db, is_external)

        elif msg_type == "voice":
            await self._handle_voice(msg, member, db, is_external)

        else:
            await self._reply_text(user_id, f"暂不支持 {msg_type} 类型消息。", is_external)

    # ==================== 群聊 Agent 对话 ====================

    async def _handle_group_chat(self, content: str, member: Member,
                                   user_id: str, chat_id: str, db: AsyncSession,
                                   is_external: bool = False) -> None:
        """群聊中 @机器人 的对话（回复到群里）"""
        session_id = f"wechat_group_{chat_id}"

        try:
            enriched_msg = f"[群聊, 用户: {member.name}, 角色: {member.role}] {content}"
            result = await agent.chat(message=enriched_msg, session_id=session_id, db=db, user_id=member.id)
            reply = result.get("content", "抱歉，处理失败了。")
            if len(reply) > 2000:
                reply = reply[:1950] + "\n\n...(内容过长已截断)"

            # 群聊回复
            await wechat_bot.smart_send_to_group(chat_id, reply, msg_type="text")
        except Exception as e:
            logger.error(f"群聊 Agent 调用失败: {e}", exc_info=True)
            await wechat_bot.smart_send_to_group(chat_id, "处理消息时出错了，请稍后再试。")

    async def _handle_group_image(self, msg: dict, member: Member,
                                    chat_id: str, db: AsyncSession,
                                    is_external: bool = False) -> None:
        """群聊图片处理"""
        media_id = msg.get("MediaId", "")
        try:
            image_data = await vision_service.download_image(media_id)
            if image_data:
                analysis = await vision_service.analyze_image(image_data)
                await wechat_bot.smart_send_to_group(chat_id, f"📷 图片分析：\n{analysis}")
        except Exception as e:
            logger.error(f"群聊图片处理失败: {e}", exc_info=True)

    async def _handle_group_voice(self, msg: dict, member: Member,
                                    chat_id: str, db: AsyncSession,
                                    is_external: bool = False) -> None:
        """群聊语音处理"""
        recognition = msg.get("Recognition", "")
        if recognition:
            await self._handle_group_chat(recognition, member, msg.get("FromUserName", ""), chat_id, db, is_external)

    # ==================== 图片/语音处理 ====================

    async def _handle_image(self, msg: dict, member: Member, db: AsyncSession,
                             is_external: bool = False) -> None:
        """私聊图片处理"""
        user_id = msg.get("FromUserName", "")
        media_id = msg.get("MediaId", "")

        await self._reply_text(user_id, "📷 收到图片，正在分析...", is_external)
        try:
            image_data = await vision_service.download_image(media_id)
            if not image_data:
                await self._reply_text(user_id, "图片下载失败。", is_external)
                return

            task = await self._get_active_task(member.id, db)
            if task:
                analysis = await vision_service.analyze_task_screenshot(image_data)
                await self._reply_text(user_id, f"📷 图片分析：\n{analysis}", is_external)
                if task.created_by:
                    teacher = await self._get_member_by_id(task.created_by, db)
                    if teacher:
                        await notifier.notify_progress_update(
                            teacher=teacher,
                            task_title=task.title,
                            member_name=member.name,
                            progress_text=f"[图片] {analysis[:200]}"
                        )
            else:
                analysis = await vision_service.analyze_image(image_data)
                await self._reply_text(user_id, f"📷 图片内容：\n{analysis}", is_external)
        except Exception as e:
            logger.error(f"图片处理失败: {e}", exc_info=True)
            await self._reply_text(user_id, "图片处理出错了。", is_external)

    async def _handle_voice(self, msg: dict, member: Member, db: AsyncSession,
                             is_external: bool = False) -> None:
        """私聊语音处理"""
        user_id = msg.get("FromUserName", "")
        recognition = msg.get("Recognition", "")

        if recognition:
            msg_copy = dict(msg)
            msg_copy["MsgType"] = "text"
            msg_copy["Content"] = recognition
            await self._handle_private_message(msg_copy, member, "text", db, is_external)
            return

        await self._reply_text(user_id, "🎤 收到语音，正在识别...", is_external)
        try:
            from app.voice.asr import asr_service
            media_id = msg.get("MediaId", "")
            voice_data = await vision_service.download_voice(media_id)
            if not voice_data:
                await self._reply_text(user_id, "语音下载失败。", is_external)
                return

            result = await asr_service.transcribe(audio_data=voice_data)
            text = result.get("text", "")
            if text:
                msg_copy = dict(msg)
                msg_copy["MsgType"] = "text"
                msg_copy["Content"] = text
                await self._handle_private_message(msg_copy, member, "text", db, is_external)
            else:
                await self._reply_text(user_id, "语音识别失败，请改用文字。", is_external)
        except Exception as e:
            logger.error(f"语音处理失败: {e}", exc_info=True)
            await self._reply_text(user_id, "语音处理出错了。", is_external)

    # ==================== 工具方法 ====================

    def _is_bot_mentioned(self, msg: dict) -> bool:
        """判断消息是否 @了机器人"""
        content = msg.get("Content", "")
        # 企业微信 @应用 的实际格式:  @应用名 或 @应用名
        # 同时检查 ToUserName 是否为 AgentID（另一种 @标识方式）
        from app.config import settings
        agent_id = msg.get("ToUserName", "")
        return (
            "@小气" in content
            or "@机器人" in content
            or " @" in content  # 企业微信 @分隔符（四角空格）
            or (agent_id and settings.WECHAT_AGENT_ID and agent_id == settings.WECHAT_AGENT_ID)
        )

    def _strip_bot_mention(self, content: str) -> str:
        """去掉 @机器人 前缀"""
        content = re.sub(r"@\S+\s*", "", content, count=1).strip()
        return content

    async def _identify_user(self, user_id: str, msg: dict, db: AsyncSession,
                               is_external: bool = False) -> Member:
        """多信号识别用户"""
        # 外部用户优先用 external_userid 查询
        if is_external:
            member = await identity_resolver.resolve_by_external_userid(user_id, db)
            if member:
                return member
        else:
            member = await identity_resolver.resolve(user_id, db)
            if member:
                return member

        pending = await self._get_pending_user(user_id)
        if pending:
            return None

        nickname = msg.get("NickName", "")
        if nickname:
            member = await identity_resolver.resolve_by_nickname(nickname, db)
            if member:
                if is_external:
                    await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                else:
                    await identity_resolver.bind_identity(member, wechat_userid=user_id, db=db)
                return member

        return None

    async def _handle_unknown_user(self, user_id: str, msg_type: str,
                                     msg: dict, db: AsyncSession,
                                     is_external: bool = False) -> None:
        """未知用户自引导绑定"""
        pending = await self._get_pending_user(user_id)

        # 有 pending 状态 → 验证流程
        if pending:
            if msg_type != "text":
                await self._reply_text(user_id, "请发送文字消息来验证身份。", is_external)
                return

            content = msg.get("Content", "").strip()
            if not content:
                await self._reply_text(user_id, "请发送文字消息来验证身份。", is_external)
                return

            pending["attempts"] += 1
            member = await identity_resolver.resolve_multi_signal(
                nickname=content, mobile=content, db=db)

            if member:
                if is_external:
                    await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                else:
                    await identity_resolver.bind_identity(member, wechat_userid=user_id, db=db)
                await self._delete_pending_user(user_id)
                await self._reply_text(user_id,
                    f"✅ 身份验证成功！你好，{member.name}！\n\n现在可以直接发消息给我。", is_external)
                return

            attempts = pending["attempts"]
            if attempts >= 3:
                await self._delete_pending_user(user_id)
                await self._reply_text(user_id, "多次匹配未成功，请联系管理员。", is_external)
            else:
                await self._set_pending_user(user_id, pending)
                await self._reply_text(user_id,
                    f"未找到匹配信息（{attempts}/3），请确认后重试。", is_external)
            return

        # 无 pending 状态 → 首次接触
        # 先检查是否是已验证用户换了设备/会话（通过姓名匹配已绑定的成员）
        if is_external and msg_type == "text":
            content = msg.get("Content", "").strip()
            if content:
                member = await identity_resolver.resolve_by_name_or_mobile(content, db)
                if member and member.external_userid:
                    # 已验证用户，绑定新的 external_userid
                    await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                    await self._reply_text(user_id,
                        f"✅ 识别到你了，{member.name}！现在可以直接发消息给我。", is_external)
                    return

        # 真正的首次用户
        await self._set_pending_user(user_id, {"awaiting": True, "attempts": 0})
        if is_external:
            await self._reply_text(user_id,
                "你好！👋 我是小气，课题组的AI助手。\n\n"
                "首次使用需要验证身份，请回复以下任一信息：\n"
                "• 你的姓名\n• 你的手机号", is_external)
        else:
            await self._reply_text(user_id,
                "你好！👋 我是小气，课题组的AI助手。\n\n"
                "首次使用需要验证身份，请回复以下任一信息：\n"
                "• 你的姓名\n• 你的手机号\n• 你的企业微信昵称", is_external)

    async def _handle_event(self, msg: dict, db: AsyncSession) -> None:
        """事件处理"""
        event = msg.get("Event", "")
        user_id = msg.get("FromUserName", "")
        is_external = user_id.startswith("wm")
        if event in ("subscribe", "enter_session"):
            await self._reply_text(user_id,
                "欢迎使用小气！👋\n\n我是课题组的AI助手，可以帮你管理任务、查询信息、搜索知识库。\n\n首次使用请回复你的姓名来验证身份。", is_external)

    async def _try_handle_task_reply(self, content: str, member: Member,
                                      user_id: str, db: AsyncSession) -> bool:
        """识别任务回复"""
        content_lower = content.lower().strip()
        task = await self._get_active_task(member.id, db)
        if not task:
            return False

        # 查找任务创建者（老师）
        teacher = await self._get_member_by_id(task.created_by, db) if task.created_by else None

        if content_lower in ("完成", "已完成", "done", "完成了", "搞定了", "搞定"):
            task.status = TaskStatus.DONE.value
            task.progress = 100
            task.completed_at = datetime.utcnow()
            await db.commit()
            if teacher:
                await notifier.notify_task_completed(teacher, task.title, member.name)
            await self._check_all_completed(task, db)
            await self._reply_text(user_id, "✅ 已记录完成！辛苦了！")
            return True

        if content_lower in ("收到", "ok", "好的", "知道了", "了解"):
            await self._reply_text(user_id, "👍 收到确认，加油！")
            return True

        progress_match = re.search(r"进度\s*(\d+)\s*%", content)
        if progress_match:
            progress = int(progress_match.group(1))
            task.progress = min(progress, 100)
            task.status = TaskStatus.DONE.value if progress >= 100 else TaskStatus.IN_PROGRESS.value
            if progress >= 100:
                task.completed_at = datetime.utcnow()
            await db.commit()
            if teacher:
                await notifier.notify_progress_update(teacher, task.title, member.name, content)
            if progress >= 100:
                await self._check_all_completed(task, db)
            await self._reply_text(user_id, f"📝 已更新进度为 {progress}%！")
            return True

        if content_lower in ("进行中", "做了一半", "在做了", "正在做"):
            task.status = TaskStatus.IN_PROGRESS.value
            task.progress = 50
            await db.commit()
            if teacher:
                await notifier.notify_progress_update(teacher, task.title, member.name, "进行中")
            await self._reply_text(user_id, "📝 已更新为进行中，加油！")
            return True

        problem_keywords = ("遇到问题", "问题：", "问题:", "卡住了", "有困难", "求助")
        if any(kw in content_lower for kw in problem_keywords):
            task.status = TaskStatus.BLOCKED.value
            await db.commit()
            if teacher:
                await notifier.notify_task_problem(teacher, task.title, member.name, content)
            await self._reply_text(user_id, "⚠️ 已记录问题并通知老师，请稍候。")
            return True

        return False

    async def _get_active_task(self, member_id: int, db: AsyncSession) -> Task:
        """获取最近的进行中任务"""
        result = await db.execute(
            select(Task).where(
                Task.assignee_id == member_id,
                Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
            ).order_by(Task.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_member_by_id(self, member_id: int, db: AsyncSession) -> Member | None:
        """通过成员ID获取成员对象"""
        result = await db.execute(
            select(Member).where(Member.id == member_id, Member.is_active == True)
        )
        return result.scalar_one_or_none()

    async def _check_all_completed(self, task: Task, db: AsyncSession) -> None:
        """检查任务完成情况"""
        if task.created_by:
            teacher = await self._get_member_by_id(task.created_by, db)
            if teacher:
                await notifier.notify_all_completed(teacher, task.title, "负责人已全部完成")

    async def _handle_general_chat(self, content: str, member: Member,
                                    user_id: str, db: AsyncSession,
                                    is_external: bool = False) -> None:
        """私聊通用对话"""
        session_id = f"wechat_{user_id}"
        try:
            enriched_msg = f"[用户: {member.name}, 角色: {member.role}] {content}"
            result = await agent.chat(message=enriched_msg, session_id=session_id, db=db, user_id=member.id)
            reply = result.get("content", "抱歉，处理失败了。")
            if len(reply) > 2000:
                reply = reply[:1950] + "\n\n...(内容过长已截断)"
            await self._reply_text(user_id, reply, is_external)
        except Exception as e:
            logger.error(f"Agent 调用失败: {e}", exc_info=True)
            await self._reply_text(user_id, "处理消息时出错了，请稍后再试。", is_external)

    async def _reply_text(self, user_id: str, content: str,
                           is_external: bool = False) -> None:
        """私聊回复（自动区分内部/外部用户）"""
        try:
            if is_external:
                await wechat_bot.send_to_external_user(user_id, content, msg_type="text")
            else:
                await wechat_bot.send_message(user_id, content, msg_type="text")
        except Exception as e:
            logger.warning(f"回复消息失败: {e}")

    # ==================== 微信客服消息处理 ====================

    async def handle_kf_message(self, msg: dict, db: AsyncSession) -> None:
        """
        处理微信客服消息

        微信客服消息格式：
        - MsgType: text/image/voice/video/file/location/link
        - Content: 文本内容
        - FromUserName: 外部用户ID (external_userid)
        - CreateTime: 时间戳
        - OpenKfId: 客服ID
        """
        msg_type = msg.get("MsgType", "")
        user_id = msg.get("FromUserName", "")
        content = msg.get("Content", "")
        open_kfid = msg.get("OpenKfId", "")

        logger.info(f"处理微信客服消息: user={user_id}, type={msg_type}, content={content[:50]}")

        # 微信客服消息始终为外部用户
        is_external = True

        # 识别用户身份
        member = await self._identify_user(user_id, msg, db, is_external)
        if not member:
            await self._handle_unknown_user(user_id, msg_type, msg, db, is_external)
            return

        # 处理文本消息
        if msg_type == "text" and content:
            # 调用 Agent 处理
            await self._call_agent_for_kf(user_id, content, member, db)
        elif msg_type == "image":
            # 图片消息处理
            media_id = msg.get("MediaId", "")
            if media_id:
                await self._handle_image(msg, member, db, is_external)
        else:
            await self._reply_text(user_id, f"暂不支持 {msg_type} 类型的消息，请发送文字或图片。", is_external)

    async def _call_agent_for_kf(self, user_id: str, content: str, member: Member, db: AsyncSession) -> None:
        """调用 Agent 处理微信客服消息"""
        try:
            session_id = f"kf:{user_id}"
            result = await agent.chat(
                message=f"[用户: {member.name}, 角色: {member.role}] {content}",
                session_id=session_id,
                db=db,
                user_id=member.id
            )

            reply = result.get("content", "抱歉，处理失败了。")
            if len(reply) > 2000:
                reply = reply[:1950] + "\n\n...(内容过长已截断)"

            # 微信客服回复使用 kf_service
            from app.wechat.kf_service import kf_service
            await kf_service.send_msg(
                open_kfid=self._current_kf_id if hasattr(self, '_current_kf_id') else "",
                external_userid=user_id,
                msg_type="text",
                content=reply
            )
        except Exception as e:
            logger.error(f"Agent 调用失败: {e}", exc_info=True)
            from app.wechat.kf_service import kf_service
            await kf_service.send_msg(
                open_kfid=self._current_kf_id if hasattr(self, '_current_kf_id') else "",
                external_userid=user_id,
                msg_type="text",
                content="处理消息时出错了，请稍后再试。"
            )


# 全局实例
message_handler = MessageHandler()

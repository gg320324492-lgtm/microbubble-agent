"""企业微信消息处理模块 - 被动监听 + 主动分析 + 多模态"""

import re
import json
import asyncio
import logging
from datetime import datetime
from app.models.base import utcnow
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


def _split_long_text(content: str, max_len: int = 2000) -> list:
    """将长文本按段落切分，尽量在换行处断开

    Args:
        content: 要切分的文本
        max_len: 每段最大字符数

    Returns:
        切分后的文本列表
    """
    if len(content) <= max_len:
        return [content]

    parts = []
    remaining = content
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break
        # 在 max_len 范围内找最后一个换行符
        cut = remaining.rfind('\n', 0, max_len)
        if cut < max_len // 2:
            # 换行位置太靠前，直接在 max_len 处截断
            cut = max_len
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip('\n')

    return parts


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

    async def _get_verified_user(self, user_id: str) -> int | None:
        """从 Redis 获取已验证用户的 member_id"""
        r = await get_redis()
        data = await r.get(f"wechat:verified:{user_id}")
        return int(data) if data else None

    async def _save_verified_user(self, user_id: str, member_id: int) -> None:
        """保存已验证用户到 Redis（7天过期）"""
        r = await get_redis()
        await r.set(f"wechat:verified:{user_id}", str(member_id), ex=86400 * 7)

    def _get_plugin_cache_key(self, msg: dict, user_id: str) -> str | None:
        """获取插件用户的验证缓存 key。from_user 是真实 ID 时用它做 key，否则用 user_id"""
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        if (from_user and from_user != to_user
                and not from_user.startswith("wwd")
                and from_user not in ("xiaoqi",)):
            return from_user
        # from_user 是 agent app name，用 user_id（agent ID）做 key
        # 注意：共享同一 agent ID 的用户会互相覆盖，但验证缓存有额外的时序保护
        return user_id if user_id.startswith("wwd") else None

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
        chat_id = msg.get("ChatId", "")  # 群聊ID（私聊为空）

        # 微信插件消息：FromUserName 是应用ID，ToUserName 才是用户ID
        # 企业微信普通消息：FromUserName 是用户ID
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        agent_id = msg.get("AgentID", "")

        # 判断是否为微信插件消息（有 AgentID 且 FromUserName 不是 external_userid 格式）
        if agent_id and not from_user.startswith("wm") and not from_user.startswith("wwd"):
            reply_to = from_user
            user_id = to_user
            is_plugin = True
            # 判断 from_user 是否是真实用户 ID（非 agent app name、非 wwd ID）
            from_user_is_real_id = (
                from_user != to_user
                and not from_user.startswith("wwd")
                and from_user not in ("xiaoqi",)
            )
        else:
            reply_to = from_user
            user_id = from_user
            is_plugin = False
            from_user_is_real_id = False

        chat_id = msg.get("ChatId", "")

        print(f"[WECHAT] 收到消息: from={from_user}, to={to_user}, agent={agent_id}, user_id={user_id}, reply_to={reply_to}, is_plugin={is_plugin}, msg_type={msg_type}", flush=True)

        # 事件处理
        if msg_type == "event":
            await self._handle_event(msg, db)
            return

        # 检测是否为外部用户（普通微信用户，external_userid 以 wm 开头）
        # 微信插件用户（wwd 开头）不算外部用户，用普通消息 API 回复
        is_external = user_id.startswith("wm")

        # 将 reply_to 存入 msg，供 _reply_text 使用
        msg["_reply_to"] = reply_to

        # 识别用户身份（插件消息传 from_user 作为备用识别信号）
        from_user_id = from_user if is_plugin else None
        member = await self._identify_user(user_id, msg, db, is_external, from_user=from_user_id)
        if not member:
            print(f"[WECHAT] 用户未识别: user_id={user_id}, is_external={is_external}", flush=True)
            await self._handle_unknown_user(user_id, msg_type, msg, db, is_external)
            return

        print(f"[WECHAT] 用户已识别: user_id={user_id}, member={member.name}", flush=True)
        msg["_resolved_user_id"] = user_id

        # 插件用户：如果 wechat_id 不是有效 userid（含中文/emoji等），用真实 UserId 更新
        if is_plugin and from_user_is_real_id:
            import re
            wechat_id_is_valid = member.wechat_id and re.match(r'^[a-zA-Z0-9._-]+$', member.wechat_id)
            if not wechat_id_is_valid:
                try:
                    old_id = member.wechat_id
                    await identity_resolver.bind_identity(member, wechat_userid=from_user, db=db, force=True)
                    print(f"[WECHAT] 自动更新wechat_id: member={member.name}, {old_id}->{from_user}", flush=True)
                except Exception as e:
                    logger.warning(f"自动更新wechat_id失败: {e}")

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
        user_id = msg.get("_resolved_user_id") or msg.get("FromUserName", "")

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
            "time": utcnow().isoformat()
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
            elapsed = (utcnow() - buffer["last_analysis"]).total_seconds()
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
            elapsed = (utcnow() - buffer["last_analysis"]).total_seconds()
            if elapsed < self.BUFFER_COOLDOWN:
                return

        # 清空缓冲区并保存到 Redis
        buffer["messages"] = []
        buffer["last_analysis"] = utcnow()
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

        except Exception:
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
            status=TaskStatus.IN_PROGRESS.value,
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
                        content = f"""📅 会议通知

主题: {title}
时间: {time}
"""
                        if location:
                            content += f"地点: {location}\n"
                        content += "\n请准时参加！"
                        await wechat_bot.smart_send(m, content, msg_type="text")
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
        user_id = msg.get("_resolved_user_id") or msg.get("FromUserName", "")

        if msg_type == "text":
            content = msg.get("Content", "").strip()
            if not content:
                return
            if await self._try_handle_task_reply(content, member, user_id, db, msg):
                return
            await self._handle_general_chat(content, member, user_id, db, is_external, msg)

        elif msg_type == "image":
            await self._handle_image(msg, member, db, is_external)

        elif msg_type == "voice":
            await self._handle_voice(msg, member, db, is_external)

        else:
            await self._reply_text(user_id, f"暂不支持 {msg_type} 类型消息。", is_external, msg=msg)

    # ==================== 群聊 Agent 对话 ====================

    async def _handle_group_chat(self, content: str, member: Member,
                                   user_id: str, chat_id: str, db: AsyncSession,
                                   is_external: bool = False) -> None:
        """群聊中 @机器人 的对话（回复到群里）"""
        session_id = f"wechat_group_{chat_id}"
        # 立即发送思考中消息，不阻塞
        try:
            await wechat_bot.smart_send_to_group(chat_id, "🤔 收到，让我思考一下...")
        except Exception as e:
            logger.warning(f"发送思考中消息失败: {e}")
        # 后台异步处理 agent 对话
        asyncio.create_task(self._process_group_chat_async(content, member, session_id, db, chat_id))

    async def _process_group_chat_async(self, content: str, member: Member,
                                         session_id: str, db: AsyncSession,
                                         chat_id: str) -> None:
        """异步处理群聊 agent 对话"""
        try:
            enriched_msg = f"[群聊, 用户: {member.name}, 角色: {member.role}] {content}"
            result = await agent.chat(message=enriched_msg, session_id=session_id, db=db, user_id=member.id)
            reply = result.get("content", "抱歉，处理失败了。")
            await self._reply_long_text_to_group(chat_id, reply)
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
            return

        # ASR 回退：下载语音并用 Whisper 识别
        media_id = msg.get("MediaId", "")
        if not media_id:
            return
        try:
            from app.voice.asr import asr_service
            voice_data = await vision_service.download_voice(media_id)
            if not voice_data:
                return
            result = await asr_service.transcribe_wechat_voice(voice_data)
            text = result.get("text", "")
            if text:
                await self._handle_group_chat(text, member, msg.get("FromUserName", ""), chat_id, db, is_external)
        except Exception as e:
            logger.error(f"群聊语音ASR失败: {e}", exc_info=True)

    # ==================== 图片/语音处理 ====================

    async def _handle_image(self, msg: dict, member: Member, db: AsyncSession,
                             is_external: bool = False) -> None:
        """私聊图片处理"""
        user_id = msg.get("FromUserName", "")
        media_id = msg.get("MediaId", "")

        await self._reply_text(user_id, "📷 收到图片，正在分析...", is_external, msg=msg)
        try:
            image_data = await vision_service.download_image(media_id)
            if not image_data:
                await self._reply_text(user_id, "图片下载失败。", is_external, msg=msg)
                return

            task = await self._get_active_task(member.id, db)
            if task:
                analysis = await vision_service.analyze_task_screenshot(image_data)
                await self._reply_text(user_id, f"📷 图片分析：\n{analysis}", is_external, msg=msg)
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
                await self._reply_text(user_id, f"📷 图片内容：\n{analysis}", is_external, msg=msg)
        except Exception as e:
            logger.error(f"图片处理失败: {e}", exc_info=True)
            await self._reply_text(user_id, "图片处理出错了。", is_external, msg=msg)

    async def _handle_voice(self, msg: dict, member: Member, db: AsyncSession,
                             is_external: bool = False) -> None:
        """私聊语音处理"""
        user_id = msg.get("FromUserName", "")
        recognition = msg.get("Recognition", "")

        if recognition:
            msg_copy = dict(msg)
            msg_copy["MsgType"] = "text"
            msg_copy["Content"] = recognition
            msg_copy["_skip_thinking"] = True  # 语音已有反馈，跳过思考中消息
            await self._handle_private_message(msg_copy, member, "text", db, is_external)
            return

        await self._reply_text(user_id, "🎤 收到语音，正在识别...", is_external, msg=msg)
        try:
            from app.voice.asr import asr_service
            media_id = msg.get("MediaId", "")
            voice_data = await vision_service.download_voice(media_id)
            if not voice_data:
                await self._reply_text(user_id, "语音下载失败。", is_external, msg=msg)
                return

            result = await asr_service.transcribe_wechat_voice(audio_data=voice_data)
            text = result.get("text", "")
            if text:
                msg_copy = dict(msg)
                msg_copy["MsgType"] = "text"
                msg_copy["Content"] = text
                msg_copy["_skip_thinking"] = True  # 语音已有反馈，跳过思考中消息
                await self._handle_private_message(msg_copy, member, "text", db, is_external)
            else:
                await self._reply_text(user_id, "语音识别失败，请改用文字。", is_external, msg=msg)
        except Exception as e:
            logger.error(f"语音处理失败: {e}", exc_info=True)
            await self._reply_text(user_id, "语音处理出错了。", is_external, msg=msg)

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
                               is_external: bool = False, from_user: str = None) -> Member:
        """多信号识别用户

        插件消息特殊处理：
        - user_id = 'wwd...'（agent ID，仅用于回复路由，不用于身份识别）
        - from_user = 用户的真实 WeChat ID（如 'DuTongHe'）或 agent ID（如 'xiaoqi'）
        - 绝对不能把 agent ID 绑定为 external_userid，否则所有插件用户会被识别为同一人
        """
        # 外部用户优先用 external_userid 查询
        if is_external:
            member = await identity_resolver.resolve_by_external_userid(user_id, db)
            if member:
                print(f"[WECHAT] 通过 external_userid 识别: user_id={user_id}, member={member.name}", flush=True)
                return member

        # 普通企业微信用户：用 wechat_id 查询
        if not is_external and not user_id.startswith("wwd"):
            member = await identity_resolver.resolve(user_id, db)
            if member:
                print(f"[WECHAT] 通过 wechat_id 识别: user_id={user_id}, member={member.name}", flush=True)
                return member

        # 插件消息：from_user 是用户的真实 WeChat ID（如 'DuTongHe'），尝试匹配
        # 但如果 from_user 就是 agent ID（如 'xiaoqi'），说明无法区分用户，跳过
        if from_user and from_user != user_id and not from_user.startswith("wwd"):
            member = await identity_resolver.resolve(from_user, db)
            if member:
                print(f"[WECHAT] 通过插件 from_user 识别: from_user={from_user}, member={member.name}", flush=True)
                return member

        pending = await self._get_pending_user(user_id)
        if pending:
            print(f"[WECHAT] 用户有 pending 状态: user_id={user_id}", flush=True)
            return None

        # 通过昵称匹配（支持重名消歧）
        nickname = msg.get("NickName", "")
        print(f"[WECHAT] 尝试昵称匹配: user_id={user_id}, nickname='{nickname}'", flush=True)
        if nickname:
            members = await identity_resolver.resolve_by_nickname(nickname, db)
            if len(members) == 1:
                member = members[0]
                print(f"[WECHAT] 通过昵称识别: user_id={user_id}, member={member.name}", flush=True)
                if is_external:
                    await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                    await self._save_verified_user(user_id, member.id)
                elif from_user and user_id.startswith("wwd") and not from_user.startswith("wwd"):
                    # 插件用户：绑定真实 UserId
                    # 如果 wechat_id 为空，或者是昵称（含中文/emoji/特殊字符），则更新为真实 userid
                    import re
                    wechat_id_is_valid = member.wechat_id and re.match(r'^[a-zA-Z0-9._-]+$', member.wechat_id)
                    if not wechat_id_is_valid:
                        await identity_resolver.bind_identity(member, wechat_userid=from_user, db=db, force=True)
                        print(f"[WECHAT] 插件用户绑定UserId: member={member.name}, wechat_id={member.wechat_id}->{from_user}", flush=True)
                return member
            elif len(members) > 1:
                candidates = "、".join(f"{m.name}({m.grade or '未知'})" for m in members[:5])
                await self._set_pending_user(user_id, {
                    "awaiting": "disambiguation", "attempts": 0,
                    "candidates": [m.id for m in members[:5]], "nickname": nickname,
                })
                print(f"[WECHAT] 昵称匹配有歧义: {nickname} -> {[m.name for m in members]}", flush=True)
                await self._reply_text(user_id,
                    f"找到多个匹配：{candidates}，请回复更精确的信息（如全名+年级）来确认身份。",
                    is_external, msg=msg)
                return None

        # 兜底：通过 Redis 验证记录识别已验证用户
        if is_external or user_id.startswith("wwd"):
            cache_key = self._get_plugin_cache_key(msg, user_id) if user_id.startswith("wwd") else user_id
            if cache_key:
                verified_member_id = await self._get_verified_user(cache_key)
                if verified_member_id:
                    from sqlalchemy import select
                    result = await db.execute(
                        select(Member).where(Member.id == verified_member_id, Member.is_active == True)
                    )
                    member = result.scalar_one_or_none()
                    if member:
                        print(f"[WECHAT] 通过验证记录识别: cache_key={cache_key}, member={member.name}", flush=True)
                        if is_external:
                            await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                        elif from_user and from_user != user_id and not from_user.startswith("wwd"):
                            # 插件用户：绑定真实 UserId 到 wechat_id，用于后续消息推送
                            if not member.wechat_id or member.wechat_id == member.name:
                                await identity_resolver.bind_identity(member, wechat_userid=from_user, db=db)
                                print(f"[WECHAT] 插件用户绑定UserId: member={member.name}, wechat_id={from_user}", flush=True)
                        return member

        print(f"[WECHAT] 用户识别失败: user_id={user_id}, is_external={is_external}", flush=True)
        return None

    async def _handle_unknown_user(self, user_id: str, msg_type: str,
                                     msg: dict, db: AsyncSession,
                                     is_external: bool = False) -> None:
        """未知用户自引导绑定"""
        pending = await self._get_pending_user(user_id)

        # 有 pending 状态 → 验证流程
        if pending:
            # 重名消歧流程
            if pending.get("awaiting") == "disambiguation":
                if msg_type != "text":
                    await self._reply_text(user_id, "请发送文字消息来确认身份。", is_external, msg=msg)
                    return
                content = msg.get("Content", "").strip()
                if not content:
                    await self._reply_text(user_id, "请发送文字消息来确认身份。", is_external, msg=msg)
                    return
                candidate_ids = pending.get("candidates", [])
                matched = None
                for cid in candidate_ids:
                    result = await db.execute(select(Member).where(Member.id == cid, Member.is_active == True))
                    m = result.scalar_one_or_none()
                    if m and (content in m.name or content == m.phone or content == m.grade or content == m.username):
                        matched = m
                        break
                if matched:
                    await self._delete_pending_user(user_id)
                    cache_key = self._get_plugin_cache_key(msg, user_id)
                    if cache_key:
                        await self._save_verified_user(cache_key, matched.id)
                    await self._reply_text(user_id,
                        f"✅ 已确认身份：{matched.name}！现在可以直接发消息给我。", is_external, msg=msg)
                    return
                pending["attempts"] = pending.get("attempts", 0) + 1
                if pending["attempts"] >= 3:
                    await self._delete_pending_user(user_id)
                    await self._reply_text(user_id, "多次匹配未成功，请联系管理员。", is_external, msg=msg)
                else:
                    await self._set_pending_user(user_id, pending)
                    await self._reply_text(user_id,
                        f"未能确认身份（{pending['attempts']}/3），请回复更精确的信息。", is_external, msg=msg)
                return

            if msg_type != "text":
                await self._reply_text(user_id, "请发送文字消息来验证身份。", is_external, msg=msg)
                return

            content = msg.get("Content", "").strip()
            if not content:
                await self._reply_text(user_id, "请发送文字消息来验证身份。", is_external, msg=msg)
                return

            pending["attempts"] += 1
            member = await identity_resolver.resolve_multi_signal(
                nickname=content, mobile=content, db=db)

            if member:
                try:
                    if user_id.startswith("wwd"):
                        # 插件用户：绑定真实 UserId 到 wechat_id
                        real_user_id = msg.get("_reply_to")
                        if real_user_id and real_user_id != user_id and not real_user_id.startswith("wwd"):
                            await identity_resolver.bind_identity(member, wechat_userid=real_user_id, db=db)
                    elif is_external:
                        await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                    else:
                        await identity_resolver.bind_identity(member, wechat_userid=user_id, db=db)
                    print(f"[WECHAT] 身份绑定成功: user_id={user_id}, member={member.name}", flush=True)
                except Exception as e:
                    logger.error(f"身份绑定失败: user_id={user_id}, member={member.name}, error={e}", exc_info=True)
                    await self._reply_text(user_id, "身份绑定失败，请稍后重试。", is_external, msg=msg)
                    return
                await self._delete_pending_user(user_id)
                from app.core.redis import invalidate_verified_cache_for_member
                await invalidate_verified_cache_for_member(member.id)
                cache_key = self._get_plugin_cache_key(msg, user_id)
                if cache_key:
                    await self._save_verified_user(cache_key, member.id)
                await self._reply_text(user_id,
                    f"✅ 身份验证成功！你好，{member.name}！\n\n现在可以直接发消息给我。", is_external, msg=msg)
                return

            attempts = pending["attempts"]
            if attempts >= 3:
                await self._delete_pending_user(user_id)
                await self._reply_text(user_id, "多次匹配未成功，请联系管理员。", is_external, msg=msg)
            else:
                await self._set_pending_user(user_id, pending)
                await self._reply_text(user_id,
                    f"未找到匹配信息（{attempts}/3），请确认后重试。", is_external, msg=msg)
            return

        # 无 pending 状态 → 首次接触
        # 先检查是否是已验证用户换了设备/会话（通过姓名匹配已绑定的成员）
        if is_external and msg_type == "text":
            content = msg.get("Content", "").strip()
            if content:
                member = await identity_resolver.resolve_by_name_or_mobile(content, db)
                if member and member.external_userid:
                    print(f"[WECHAT] 已验证用户换设备识别: user_id={user_id}, member={member.name}", flush=True)
                    await identity_resolver.bind_identity(member, external_userid=user_id, db=db)
                    await self._reply_text(user_id,
                        f"✅ 识别到你了，{member.name}！现在可以直接发消息给我。", is_external, msg=msg)
                    return

        # 真正的首次用户
        await self._set_pending_user(user_id, {"awaiting": True, "attempts": 0})
        if is_external:
            await self._reply_text(user_id,
                "你好！👋 我是小气，课题组的AI助手。\n\n"
                "首次使用需要验证身份，请回复以下任一信息：\n"
                "• 你的姓名\n• 你的手机号", is_external, msg=msg)
        else:
            await self._reply_text(user_id,
                "你好！👋 我是小气，课题组的AI助手。\n\n"
                "首次使用需要验证身份，请回复以下任一信息：\n"
                "• 你的姓名\n• 你的手机号\n• 你的企业微信昵称", is_external, msg=msg)

    async def _handle_event(self, msg: dict, db: AsyncSession) -> None:
        """事件处理"""
        event = msg.get("Event", "")
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        agent_id = msg.get("AgentID", "")
        if agent_id and not from_user.startswith("wm") and not from_user.startswith("wwd"):
            user_id = to_user
            msg["_reply_to"] = from_user
        else:
            user_id = from_user
            msg["_reply_to"] = from_user
        is_external = user_id.startswith("wm")
        if event in ("subscribe", "enter_session"):
            await self._reply_text(user_id,
                "欢迎使用小气！👋\n\n我是课题组的AI助手，可以帮你管理任务、查询信息、搜索知识库。\n\n首次使用请回复你的姓名来验证身份。", is_external, msg=msg)

    async def _try_handle_task_reply(self, content: str, member: Member,
                                      user_id: str, db: AsyncSession,
                                      msg: dict = None) -> bool:
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
            task.completed_at = utcnow()
            await db.commit()
            if teacher:
                await notifier.notify_task_completed(teacher, task.title, member.name)
            await self._check_all_completed(task, db)
            await self._reply_text(user_id, "✅ 已记录完成！辛苦了！", msg=msg)
            return True

        if content_lower in ("收到", "ok", "好的", "知道了", "了解"):
            await self._reply_text(user_id, "👍 收到确认，加油！", msg=msg)
            return True

        progress_match = re.search(r"进度\s*(\d+)\s*%", content)
        if progress_match:
            progress = int(progress_match.group(1))
            task.progress = min(progress, 100)
            task.status = TaskStatus.DONE.value if progress >= 100 else TaskStatus.IN_PROGRESS.value
            if progress >= 100:
                task.completed_at = utcnow()
            await db.commit()
            if teacher:
                await notifier.notify_progress_update(teacher, task.title, member.name, content)
            if progress >= 100:
                await self._check_all_completed(task, db)
            await self._reply_text(user_id, f"📝 已更新进度为 {progress}%！", msg=msg)
            return True

        if content_lower in ("进行中", "做了一半", "在做了", "正在做"):
            task.status = TaskStatus.IN_PROGRESS.value
            task.progress = 50
            await db.commit()
            if teacher:
                await notifier.notify_progress_update(teacher, task.title, member.name, "进行中")
            await self._reply_text(user_id, "📝 已更新为进行中，加油！", msg=msg)
            return True

        problem_keywords = ("遇到问题", "问题：", "问题:", "卡住了", "有困难", "求助")
        if any(kw in content_lower for kw in problem_keywords):
            task.status = TaskStatus.BLOCKED.value
            await db.commit()
            if teacher:
                await notifier.notify_task_problem(teacher, task.title, member.name, content)
            await self._reply_text(user_id, "⚠️ 已记录问题并通知老师，请稍候。", msg=msg)
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
                                    is_external: bool = False, msg: dict = None) -> None:
        """私聊通用对话"""
        session_id = f"wechat_{user_id}"
        # 如果语音/图片处理已经发送过反馈（如"🎤 收到语音..."），则跳过思考中消息
        skip_thinking = msg.get("_skip_thinking") if msg else False
        if not skip_thinking:
            try:
                await self._reply_text(user_id, "🤔 收到，让我思考一下...", is_external, msg=msg)
            except Exception as e:
                logger.warning(f"发送思考中消息失败: {e}")
        # 后台异步处理 agent 对话
        asyncio.create_task(self._process_general_chat_async(content, member, session_id, db, is_external, msg))

    async def _process_general_chat_async(self, content: str, member: Member,
                                         session_id: str, db: AsyncSession,
                                         is_external: bool, msg: dict) -> None:
        """异步处理 agent 对话"""
        user_id = msg.get("_resolved_user_id") or msg.get("FromUserName", "")
        try:
            enriched_msg = f"[用户: {member.name}, 角色: {member.role}] {content}"
            result = await agent.chat(message=enriched_msg, session_id=session_id, db=db, user_id=member.id)
            reply = result.get("content", "抱歉，处理失败了。")
            await self._reply_long_text(user_id, reply, is_external, msg=msg)
        except Exception as e:
            logger.error(f"Agent 调用失败: {e}", exc_info=True)
            await self._reply_text(user_id, "处理消息时出错了，请稍后再试。", is_external, msg=msg)

    async def _reply_text(self, user_id: str, content: str,
                           is_external: bool = False, msg: dict = None) -> None:
        """私聊回复（自动区分内部/外部用户）"""
        target = (msg or {}).get("_reply_to", user_id)
        try:
            if is_external:
                await wechat_bot.send_to_external_user(target, content, msg_type="text")
            else:
                await wechat_bot.send_message(target, content, msg_type="text")
        except Exception as e:
            logger.warning(f"回复消息失败: target={target}, {e}")

    async def _reply_long_text(self, user_id: str, content: str,
                                is_external: bool = False, msg: dict = None,
                                max_len: int = 2000) -> None:
        """长回复自动分段发送（微信单条消息上限约 2048 字符）

        Args:
            user_id: 用户ID
            content: 回复内容
            is_external: 是否为外部用户
            msg: 原始消息
            max_len: 每段最大字符数
        """
        parts = _split_long_text(content, max_len)
        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(0.5)
            await self._reply_text(user_id, part, is_external, msg=msg)

    async def _reply_long_text_to_group(self, chat_id: str, content: str,
                                         max_len: int = 2000) -> None:
        """群聊长回复自动分段发送"""
        parts = _split_long_text(content, max_len)
        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(0.5)
            await wechat_bot.smart_send_to_group(chat_id, part, msg_type="text")

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
            await self._call_agent_for_kf(user_id, content, member, db, open_kfid=open_kfid)
        elif msg_type == "voice":
            # 语音消息处理
            media_id = msg.get("MediaId", "")
            if media_id:
                try:
                    from app.voice.asr import asr_service
                    voice_data = await vision_service.download_voice(media_id)
                    if voice_data:
                        result = await asr_service.transcribe_wechat_voice(voice_data)
                        text = result.get("text", "")
                        if text:
                            await self._call_agent_for_kf(user_id, text, member, db, open_kfid=open_kfid)
                        else:
                            await self._reply_text(user_id, "语音识别失败，请改用文字。", is_external)
                except Exception as e:
                    logger.error(f"客服语音处理失败: {e}", exc_info=True)
                    await self._reply_text(user_id, "语音处理出错了。", is_external)
        elif msg_type == "image":
            media_id = msg.get("MediaId", "")
            if media_id:
                await self._handle_image(msg, member, db, is_external)
        else:
            await self._reply_text(user_id, f"暂不支持 {msg_type} 类型的消息，请发送文字或图片。", is_external)

    async def _call_agent_for_kf(self, user_id: str, content: str, member: Member,
                                   db: AsyncSession, open_kfid: str = "") -> None:
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

            from app.wechat.kf_service import kf_service
            # 长回复分段发送
            parts = _split_long_text(reply)
            for i, part in enumerate(parts):
                if i > 0:
                    await asyncio.sleep(0.5)
                await kf_service.send_msg(
                    open_kfid=open_kfid,
                    external_userid=user_id,
                    msg_type="text",
                    content=part
                )
        except Exception as e:
            logger.error(f"Agent 调用失败: {e}", exc_info=True)
            from app.wechat.kf_service import kf_service
            await kf_service.send_msg(
                open_kfid=open_kfid,
                external_userid=user_id,
                msg_type="text",
                content="处理消息时出错了，请稍后再试。"
            )


# 全局实例
message_handler = MessageHandler()

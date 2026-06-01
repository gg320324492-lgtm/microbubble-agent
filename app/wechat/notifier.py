"""企业微信主动通知模块"""

import logging
from typing import TYPE_CHECKING

from app.wechat.bot import wechat_bot

if TYPE_CHECKING:
    from app.models.member import Member

logger = logging.getLogger("microbubble.wechat")


class WeChatNotifier:
    """企业微信通知器"""

    async def notify_task_assigned(self, member: "Member", task_title: str, due_date: str,
                                    priority: str, description: str, assigner: str) -> dict:
        """私发：你有一个新任务（自动区分内部/外部用户）"""
        priority_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
        content = f"""📋 新任务通知

任务: {task_title}
指派人: {assigner}
截止: {due_date}
优先级: {priority_map.get(priority, priority)}
说明: {description or '无'}

收到请回复"收到"，完成后请回复"已完成"。如有问题可直接说明。"""
        return await wechat_bot.smart_send(member, content, msg_type="text")

    async def notify_task_assigned_to_creator(self, creator: "Member", task_title: str,
                                               assignee_name: str, due_date: str,
                                               priority: str) -> dict:
        """通知创建人：任务已成功派发"""
        priority_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
        content = f"""📋 任务派发确认

任务: {task_title}
负责人: {assignee_name}
截止: {due_date}
优先级: {priority_map.get(priority, priority)}

已通知该成员，请留意回复。"""
        return await wechat_bot.smart_send(creator, content, msg_type="text")

    async def notify_due_soon_to_creator(self, creator: "Member", task_title: str,
                                          assignee_name: str, due_date: str,
                                          time_left: str, progress: int) -> dict:
        """通知创建人：某人负责的任务即将到期"""
        content = f"""⏰ 任务即将到期

任务: {task_title}
负责人: {assignee_name}
截止: {due_date}
剩余: {time_left}
进度: {progress}%

请关注进展。"""
        return await wechat_bot.smart_send(creator, content, msg_type="text")

    async def notify_task_completed(self, teacher: "Member", task_title: str,
                                     member_name: str, summary: str = "") -> dict:
        """通知老师：某人完成了任务"""
        content = f"""✅ 任务完成通知

任务: {task_title}
完成人: {member_name}
{f'备注: {summary}' if summary else ''}"""
        return await wechat_bot.smart_send(teacher, content, msg_type="text")

    async def notify_all_completed(self, teacher: "Member", task_title: str,
                                    summary_text: str) -> dict:
        """通知老师：全员完成，附汇总"""
        content = f"""🎉 任务全员完成

任务: {task_title}

{summary_text}

所有负责人均已完成！"""
        return await wechat_bot.smart_send(teacher, content, msg_type="text")

    async def notify_progress_update(self, teacher: "Member", task_title: str,
                                      member_name: str, progress_text: str) -> dict:
        """通知老师：某人更新了进度"""
        content = f"""📝 进度更新

任务: {task_title}
汇报人: {member_name}
内容: {progress_text}"""
        return await wechat_bot.smart_send(teacher, content, msg_type="text")

    async def notify_task_problem(self, teacher: "Member", task_title: str,
                                   member_name: str, problem: str) -> dict:
        """通知老师：某人遇到问题"""
        content = f"""⚠️ 任务问题反馈

任务: {task_title}
反馈人: {member_name}
问题: {problem}

请及时处理。"""
        return await wechat_bot.smart_send(teacher, content, msg_type="text")

    async def send_task_to_group(self, chat_id: str, task_title: str,
                                  assignees: str, due_date: str) -> dict:
        """在群里通知任务已派发"""
        content = f"""📋 任务已派发

任务: {task_title}
负责人: {assignees}
截止: {due_date}

已私信通知各负责人。"""
        return await wechat_bot.smart_send_to_group(chat_id, content, msg_type="text")


# 全局实例
notifier = WeChatNotifier()


async def notify_meeting_reminder(
    member_wechat_id: str,
    meeting_info: dict,
    remind_minutes: int,
) -> bool:
    """
    推送会议提醒到企业微信（Wave 3a 任务 12）。
    meeting_info: {title, start_time, location, meeting_url, participants}
    """
    from app.wechat.bot import wechat_bot

    start_time_str = meeting_info.get("start_time", "")
    if hasattr(start_time_str, "strftime"):
        start_time_str = start_time_str.strftime("%Y-%m-%d %H:%M")

    participants = meeting_info.get("participants", []) or []
    participants_str = ", ".join(participants) if participants else "（未指定）"
    location = meeting_info.get("location", "线上") or "线上"
    meeting_url = meeting_info.get("meeting_url", "") or ""
    url_line = f"\n会议链接: {meeting_url}" if meeting_url else ""

    content = f"""📅 会议即将开始
会议: {meeting_info.get('title', '未命名')}
时间: {start_time_str or '未指定'}
地点: {location}
参与人: {participants_str}
{url_line}

{remind_minutes} 分钟后开始，请准时参会。"""

    return await wechat_bot.smart_send(member_wechat_id, content, msg_type="text")

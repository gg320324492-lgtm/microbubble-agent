"""企业微信主动通知模块"""

import logging
from datetime import datetime
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
        content = f"""📋 **新任务通知**

**任务**: {task_title}
**指派人**: {assigner}
**截止**: {due_date}
**优先级**: {priority_map.get(priority, priority)}
**说明**: {description or '无'}

收到请回复"收到"，完成后请回复"已完成"。如有问题可直接说明。"""
        return await wechat_bot.smart_send(member, content, msg_type="markdown")

    async def notify_task_completed(self, teacher: "Member", task_title: str,
                                     member_name: str, summary: str = "") -> dict:
        """通知老师：某人完成了任务"""
        content = f"""✅ **任务完成通知**

**任务**: {task_title}
**完成人**: {member_name}
{f'**备注**: {summary}' if summary else ''}"""
        return await wechat_bot.smart_send(teacher, content, msg_type="markdown")

    async def notify_all_completed(self, teacher: "Member", task_title: str,
                                    summary_text: str) -> dict:
        """通知老师：全员完成，附汇总"""
        content = f"""🎉 **任务全员完成**

**任务**: {task_title}

{summary_text}

所有负责人均已完成！"""
        return await wechat_bot.smart_send(teacher, content, msg_type="markdown")

    async def notify_progress_update(self, teacher: "Member", task_title: str,
                                      member_name: str, progress_text: str) -> dict:
        """通知老师：某人更新了进度"""
        content = f"""📝 **进度更新**

**任务**: {task_title}
**汇报人**: {member_name}
**内容**: {progress_text}"""
        return await wechat_bot.smart_send(teacher, content, msg_type="markdown")

    async def notify_task_problem(self, teacher: "Member", task_title: str,
                                   member_name: str, problem: str) -> dict:
        """通知老师：某人遇到问题"""
        content = f"""⚠️ **任务问题反馈**

**任务**: {task_title}
**反馈人**: {member_name}
**问题**: {problem}

请及时处理。"""
        return await wechat_bot.smart_send(teacher, content, msg_type="markdown")

    async def send_task_to_group(self, chat_id: str, task_title: str,
                                  assignees: str, due_date: str) -> dict:
        """在群里通知任务已派发"""
        content = f"""📋 **任务已派发**

**任务**: {task_title}
**负责人**: {assignees}
**截止**: {due_date}

已私信通知各负责人。"""
        return await wechat_bot.smart_send_to_group(chat_id, content, msg_type="markdown")


# 全局实例
notifier = WeChatNotifier()

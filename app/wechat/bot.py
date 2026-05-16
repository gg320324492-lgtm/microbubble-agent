"""企业微信机器人模块"""

import httpx
import json
from typing import Optional
from datetime import datetime

from app.config import settings


class WeChatBot:
    """企业微信机器人"""

    def __init__(self):
        self.corp_id = settings.WECHAT_CORP_ID
        self.agent_id = settings.WECHAT_AGENT_ID
        self.secret = settings.WECHAT_SECRET
        self._access_token = None
        self._token_expires = None

    async def _get_access_token(self) -> str:
        """获取access_token"""
        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={
                    "corpid": self.corp_id,
                    "corpsecret": self.secret
                }
            )
            data = response.json()

            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                # 提前5分钟过期
                self._token_expires = datetime.utcnow().timestamp() + data["expires_in"] - 300
                return self._access_token
            else:
                raise Exception(f"获取access_token失败: {data}")

    async def send_message(
        self,
        user_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息给用户

        Args:
            user_id: 用户ID
            content: 消息内容
            msg_type: 消息类型（text/markdown）

        Returns:
            发送结果
        """
        token = await self._get_access_token()

        if msg_type == "text":
            data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {
                    "content": content
                }
            }
        elif msg_type == "markdown":
            data = {
                "touser": user_id,
                "msgtype": "markdown",
                "agentid": self.agent_id,
                "markdown": {
                    "content": content
                }
            }
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
                json=data
            )
            return response.json()

    async def send_task_reminder(
        self,
        user_id: str,
        task_title: str,
        due_date: str,
        status: str
    ) -> dict:
        """
        发送任务提醒

        Args:
            user_id: 用户ID
            task_title: 任务标题
            due_date: 截止日期
            status: 状态描述

        Returns:
            发送结果
        """
        content = f"""📋 **任务提醒**

**任务**: {task_title}
**截止**: {due_date}
**状态**: {status}

请及时处理！"""

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_meeting_notification(
        self,
        user_id: str,
        meeting_title: str,
        meeting_time: str,
        location: Optional[str] = None
    ) -> dict:
        """
        发送会议通知

        Args:
            user_id: 用户ID
            meeting_title: 会议主题
            meeting_time: 会议时间
            location: 会议地点

        Returns:
            发送结果
        """
        content = f"""📅 **会议通知**

**主题**: {meeting_title}
**时间**: {meeting_time}
"""
        if location:
            content += f"**地点**: {location}\n"

        content += "\n请准时参加！"

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_meeting_minutes(
        self,
        user_id: str,
        meeting_title: str,
        summary: str
    ) -> dict:
        """
        发送会议纪要

        Args:
            user_id: 用户ID
            meeting_title: 会议主题
            summary: 会议摘要

        Returns:
            发送结果
        """
        content = f"""📝 **会议纪要**

**会议**: {meeting_title}

**摘要**:
{summary}

详细内容请登录系统查看。"""

        return await self.send_message(user_id, content, msg_type="markdown")

    async def send_to_group(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "text"
    ) -> dict:
        """
        发送消息到群聊

        Args:
            chat_id: 群聊ID
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        token = await self._get_access_token()

        if msg_type == "text":
            data = {
                "chatid": chat_id,
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
        else:
            data = {
                "chatid": chat_id,
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}",
                json=data
            )
            return response.json()

    async def reply_to_user(self, user_id: str, content: str, msg_type: str = "text") -> dict:
        """
        回复用户消息（别名，与 send_message 功能相同）

        Args:
            user_id: 用户ID
            content: 消息内容
            msg_type: 消息类型

        Returns:
            发送结果
        """
        return await self.send_message(user_id, content, msg_type)


# 全局实例
wechat_bot = WeChatBot()
